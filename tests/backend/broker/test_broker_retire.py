"""An update, reload or Repair under a running broker: the first call after it runs on the new code (real socket
server in-process, fake engine workers).

The broker of the code before keeps its pinned tool contracts in memory, while a worker it starts runs the engine
now on disk: every new chat's first calls failed with ENGINE_PIN_MISMATCH while an idle worker (an emulator left
open hours before) kept that broker from being replaced. Now it makes way: at once when nothing runs in it, and
otherwise as soon as its work has ended (a call's answer written, the page's install, engine work whose outcome is
unknown, a recording, a preview someone records in), admitting nothing new meanwhile.
"""

import json
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker import client, lifecycle, server  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.engine import EngineError, EngineProcess  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.lane import Denied, Lane  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.lifecycle import UPDATE_NOTICE, Notices  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.bare import bare_broker  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.test_broker_fingerprint import NEW_BUILD, Running, launched  # noqa: E402 - the repository root goes on sys.path first

POSIX = sys.platform.startswith("linux") or sys.platform == "darwin"
CHAT = {"profile": "/profiles/hermretro", "conversation_id": "chat-a"}
OTHER_CHAT = {"profile": "/profiles/hermretro", "conversation_id": "chat-b"}
CLOSED = {"structuredContent": {"closed": True}}
IN_USE = {"structuredContent": {"closed": False, "error": "A person is recording or saving in this preview."}}


class Worker:
    """An engine worker that answers session_status (holding the answer while ``hold`` is clear) and closes its
    preview as ``previews`` says, taking a moment to close as a real one does."""

    pid = os.getpid()

    def __init__(self, hold: threading.Event | None = None, previews=()):
        self.hold, self.entered, self.closed, self.waiting = hold, threading.Event(), False, False
        self.previews, self.asked = list(previews), []

    def alive(self):
        return not self.closed

    def unconfirmed(self):
        return self.waiting and not self.closed

    def close(self, grace=None):
        time.sleep(0.2)  # its grace: main() still holds the socket and the election meanwhile
        self.closed = True

    def call_tool(self, tool, arguments, timeout=None):
        self.asked.append(tool)
        if tool == "web_preview_close":
            return self.previews.pop(0) if self.previews else CLOSED
        self.entered.set()
        if self.hold is not None:
            self.hold.wait(10)
        return {"content": [], "structuredContent": {"selected": False, "emulatorActive": True}}


def with_worker(broker, owner: dict, worker: Worker) -> Lane:
    lane = broker.lane_for((owner["profile"], owner["conversation_id"]), create=True)
    lane.engine = worker
    return lane


def stopped(broker, seconds=5.0) -> bool:
    return broker.stopping.wait(seconds)


@unittest.skipUnless(POSIX, "Linux and macOS only")
class BrokerOfOlderCode(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="hr-", dir="/tmp")).resolve()  # short: socket paths are capped
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.state = self.base / "run"
        self.state.mkdir(mode=0o700)
        for patch in (
            mock.patch.dict(os.environ, {"HERMRETRO_HOME": str(self.base / "home")}),
            mock.patch.object(paths, "verify_engine", lambda: {"verified": True}),
            mock.patch.object(paths, "find_node", lambda: {"ok": True, "path": "node"}),
            mock.patch.object(lifecycle, "RETIRE_RECHECK", 0.05),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.started: list[Running] = []

    def start(self) -> Running:
        running = Running(self.state)
        self.addCleanup(running.close)
        return running

    def spawn(self, _state, _node, *, deadline):
        """What the client starts after the old broker has gone: a broker of the new files."""
        return launched(self.start, self.started)

    def newer_client(self):
        """The plugin's code after the update: the files on disk are another build than the running broker's."""
        return (
            mock.patch.object(paths, "code_fingerprint", lambda: NEW_BUILD),
            mock.patch.object(client, "spawn_broker", self.spawn),
        )

    def test_an_idle_worker_with_its_emulator_open_does_not_keep_it(self):
        old = self.start()
        lane = with_worker(old.broker, CHAT, Worker())
        fingerprint, spawn = self.newer_client()
        with fingerprint, spawn:
            with client.ensure_broker(self.state, wait=10) as connection:
                self.assertEqual(len(self.started), 1, "the broker of the older code was kept")
                self.assertEqual(connection.hello["broker_generation"], self.started[0].broker.generation)
        self.assertTrue(old.stopped.wait(5))
        self.assertEqual(self.started[0].broker.notices.get(lane.key), UPDATE_NOTICE)  # for its next call
        self.assertIn({"event": "broker_retired", "workers": 1}, self.trace(old.broker.generation))

    def test_a_notice_is_kept_across_brokers_until_a_call_has_carried_it(self):
        key = Lane((CHAT["profile"], CHAT["conversation_id"])).key
        (self.state / "notices.json").write_text(json.dumps({key: UPDATE_NOTICE, "other": "Told later."}))
        first = self.start()
        first.broker.stopping.set()  # it stops (idle) before the conversation calls again
        self.assertTrue(first.stopped.wait(5))
        second = self.start()
        with_worker(second.broker, CHAT, Worker())
        with client.BrokerClient(self.state) as connection:
            answer = connection.call(CHAT, "session_status")
            again = connection.call(CHAT, "session_status")
        self.assertEqual((answer["notice"], again["notice"]), (UPDATE_NOTICE, None))
        self.assertEqual(json.loads((self.state / "notices.json").read_text()), {"other": "Told later."})
        self.assertEqual(Notices(self.state).get("other"), "Told later.")

    def test_a_running_call_is_finished_first_and_nothing_new_starts_meanwhile(self):
        old = self.start()
        hold = threading.Event()
        self.addCleanup(hold.set)
        worker = Worker(hold)
        with_worker(old.broker, CHAT, worker)
        answers = []

        def build():  # chat A's call, running when the update lands
            with client.BrokerClient(self.state) as connection:
                answers.append(connection.call(CHAT, "session_status"))

        running = threading.Thread(target=build)
        running.start()
        self.assertTrue(worker.entered.wait(5))
        fingerprint, spawn = self.newer_client()
        with fingerprint, spawn:
            with self.assertRaisesRegex(client.BrokerRestarting, "chromatic_session_status call running now"):
                client.ensure_broker(self.state, wait=10)
            self.assertEqual(self.started, [], "a broker was started while the old one still runs a call")
            with client.BrokerClient(self.state) as other:  # a client that did not ask: still nothing new starts
                refused = other.call(OTHER_CHAT, "session_status")
            self.assertEqual((refused["denied"]["code"], refused["dispatched"]), ("RESTARTING", False))
            hold.set()
            running.join(5)
            self.assertTrue(answers and answers[0]["ok"], answers)  # the running call answered in full
            self.assertTrue(stopped(old.broker), "the broker did not stop after its last call")
            # It still closes its worker holding the socket and the election: the client waits that out.
            with client.ensure_broker(self.state, wait=10) as connection:
                self.assertEqual(connection.hello["broker_generation"], self.started[-1].broker.generation)
        self.assertTrue(old.stopped.wait(5))
        events = [record["event"] for record in self.trace(old.broker.generation)]
        self.assertEqual(events.count("broker_retiring"), 1)
        self.assertEqual(events[-1], "broker_retired")

    def test_a_finished_call_is_counted_until_its_answer_is_written(self):
        old = self.start()
        with_worker(old.broker, CHAT, Worker())
        writing, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        dumps = json.dumps

        def slow_answer(value, *args, **kwargs):  # the call's answer is being written when the update lands
            if isinstance(value, dict) and value.get("dispatched") is True:
                writing.set()
                release.wait(10)
            return dumps(value, *args, **kwargs)

        answers = []

        def build():
            with client.BrokerClient(self.state) as connection:
                answers.append(connection.call(CHAT, "session_status"))

        with mock.patch.object(server.json, "dumps", slow_answer):
            running = threading.Thread(target=build)
            running.start()
            self.assertTrue(writing.wait(5))
            with self.assertRaises(Denied) as retiring:
                old.broker.retire()
            self.assertEqual(retiring.exception.code, "RETIRING")
            self.assertFalse(stopped(old.broker, 0.3), "it stopped while a finished call's answer was unwritten")
            release.set()
            running.join(5)
        self.assertTrue(answers and answers[0]["ok"], answers)
        self.assertTrue(stopped(old.broker))

    def test_a_broker_that_goes_away_while_asked_is_looked_for_again(self):
        old = self.start()
        with_worker(old.broker, CHAT, Worker())
        real = client._shutdown_for_replacement
        lost = []

        def stops_mid_answer(connection, *, replace=False):  # it stopped before its answer reached the client
            if not lost:
                lost.append(True)
                old.broker.stopping.set()
                raise client.ConnectionLost("Broker closed the connection")
            return real(connection, replace=replace)

        fingerprint, spawn = self.newer_client()
        with fingerprint, spawn, mock.patch.object(client, "_shutdown_for_replacement", stops_mid_answer):
            with client.ensure_broker(self.state, wait=10) as connection:
                self.assertEqual(connection.hello["broker_generation"], self.started[-1].broker.generation)

    def test_a_broker_from_before_retirement_that_answers_busy_gets_nothing_dispatched(self):
        old = self.start()
        with_worker(old.broker, CHAT, Worker())
        control = old.broker.control
        old.broker.control = lambda request: control({k: v for k, v in request.items() if k != "replace"})
        fingerprint, spawn = self.newer_client()
        with fingerprint, spawn:
            with self.assertRaises(client.BrokerRestarting) as refused:
                client.ensure_broker(self.state, wait=10)
        self.assertFalse(refused.exception.waits)
        self.assertEqual(str(refused.exception), client.LEGACY_BUSY)
        self.assertEqual(self.started, [])
        self.assertFalse(old.broker.stopping.is_set())
        self.assertNotIn("dispatch", [record["event"] for record in self.trace(old.broker.generation)])

    def test_a_plain_shutdown_still_refuses_a_live_worker(self):
        old = self.start()
        with_worker(old.broker, CHAT, Worker())
        with client.BrokerClient(self.state) as connection:
            self.assertFalse(client.request_shutdown(connection))
        self.assertFalse(old.broker.stopping.is_set())
        self.assertFalse(old.broker.retiring)

    def trace(self, generation: str) -> list[dict]:
        records = [json.loads(line) for line in (self.state / "trace.jsonl").read_text().splitlines()]
        return [
            {key: value for key, value in record.items() if key not in ("t", "broker_generation")}
            for record in records
            if record["broker_generation"] == generation
        ]


class Retirement(unittest.TestCase):
    """The decision itself, on a broker without sockets."""

    def setUp(self):
        self.state = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.state, ignore_errors=True)
        patch = mock.patch.object(lifecycle, "RETIRE_RECHECK", 0.05)
        patch.start()
        self.addCleanup(patch.stop)
        self.installing = False

    def broker(self):
        return bare_broker(state_dir=self.state, install_busy=lambda: self.installing)

    def test_with_nothing_to_finish_it_stops_at_once(self):
        broker = self.broker()
        self.assertEqual(broker.retire(), {"ok": True})
        self.assertTrue(broker.stopping.is_set())

    def test_the_page_install_is_waited_for_and_none_starts_meanwhile(self):
        broker = self.broker()
        self.installing = True
        with self.assertRaises(Denied):
            broker.retire()
        with self.assertRaises(Denied) as refused:
            broker.admit({"op": "install_start"})
        self.assertEqual(refused.exception.code, "RESTARTING")
        self.assertFalse(stopped(broker, 0.2))
        self.installing = False
        self.assertTrue(stopped(broker))

    def test_an_install_start_admitted_before_counts_until_answered(self):
        broker = self.broker()
        self.assertTrue(broker.admit({"op": "install_start"}))
        with self.assertRaises(Denied):
            broker.retire()
        self.installing = True  # the start went through: the install now runs
        broker.answered({"ok": True}, delivered=True)
        self.assertFalse(stopped(broker, 0.2), "it stopped under the install it had admitted")
        self.installing = False
        self.assertTrue(stopped(broker))

    def test_a_plain_shutdown_refuses_while_admitted_work_has_no_worker_yet(self):
        broker = self.broker()
        broker.admit({"op": "call"})  # admitted, still starting its worker
        with self.assertRaises(Denied) as refused:
            broker.shutdown(force=False)
        self.assertEqual(refused.exception.code, "BUSY")
        broker.answered({"ok": True}, delivered=True)
        self.assertEqual(broker.shutdown(force=False), {"ok": True})
        with self.assertRaises(Denied) as late:
            broker.admit({"op": "call"})
        self.assertEqual(late.exception.code, "BROKER_STOPPING")

    def test_engine_work_whose_outcome_is_unknown_is_waited_for(self):
        broker = self.broker()
        worker = Worker()
        worker.waiting = True  # a call timed out; the engine has not answered it yet
        with_worker(broker, CHAT, worker)
        with self.assertRaises(Denied):
            broker.retire()
        self.assertFalse(stopped(broker, 0.2), "it stopped under a compiler that may still run")
        worker.waiting = False  # the engine answered at last
        self.assertTrue(stopped(broker))

    def test_a_recording_a_call_started_runs_to_its_end(self):
        broker = self.broker()
        lane = with_worker(broker, CHAT, Worker())
        lane.note_surface("web_preview", {"action": "start_recording", "recordingDurationMs": 60_000})
        with self.assertRaises(Denied):
            broker.retire()
        self.assertFalse(stopped(broker, 0.2))
        lane.recording_until = time.monotonic()  # its time is up
        self.assertTrue(stopped(broker))

    def test_a_preview_closes_itself_first_and_one_a_person_records_in_is_waited_for(self):
        broker = self.broker()
        worker = Worker(previews=[IN_USE, IN_USE])
        lane = with_worker(broker, CHAT, worker)
        lane.preview_url, lane.live_surface = "http://127.0.0.1:1/", True
        with self.assertRaises(Denied):
            broker.retire()
        self.assertTrue(stopped(broker))
        self.assertEqual(worker.asked, ["web_preview_close"] * 3)
        self.assertEqual((lane.preview_url, lane.live_surface), (None, False))
        self.assertEqual([e["event"] for e in broker.events].count("preview_in_use"), 1)

    def test_a_hung_worker_does_not_hold_it_for_ever(self):
        broker = self.broker()
        worker = Worker(previews=[IN_USE] * 1000)
        worker.waiting = True
        lane = with_worker(broker, CHAT, worker)
        lane.preview_url = "http://127.0.0.1:1/"
        with mock.patch.object(lifecycle, "RETIRE_PATIENCE", 0.3):
            with self.assertRaises(Denied):
                broker.retire()
            self.assertTrue(stopped(broker))

    def test_its_conversations_keep_their_notices_with_what_they_were_not_told_yet(self):
        broker = self.broker()
        idle = with_worker(broker, CHAT, Worker())
        untold = broker.lane_for(("p", "chat-b"), create=True)
        untold.pending_notice = "The project is no longer selected."
        broker.notices.keep({"chat-c": "Told later."})
        self.assertEqual(broker.retire(), {"ok": True})
        self.assertEqual(
            json.loads((self.state / "notices.json").read_text()),
            {"chat-c": "Told later.", idle.key: UPDATE_NOTICE, untold.key: "The project is no longer selected."},
        )

    def test_a_notice_whose_answer_never_reached_the_chat_is_told_again(self):
        broker = self.broker()
        broker.notices.keep({Lane(("p", "chat-a")).key: UPDATE_NOTICE})
        lane = broker.lane_for(("p", "chat-a"), create=True)
        lane.pending_notice = None  # taken into an answer
        broker.admit({"op": "call"})
        broker.answered({"ok": True, "notice": UPDATE_NOTICE, "lane": {"owner_key": lane.key}}, delivered=False)
        self.assertEqual(lane.pending_notice, UPDATE_NOTICE)
        self.assertEqual(Notices(self.state).get(lane.key), UPDATE_NOTICE)
        self.assertEqual(broker.running, 0)

    def test_unreadable_notices_are_dropped(self):
        self.assertEqual(Notices(self.state).kept, {})
        for text in ("not json", "[1]", '{"key": 3, "other": "told"}'):
            (self.state / "notices.json").write_text(text)
            self.assertEqual(Notices(self.state).kept, {"other": "told"} if "other" in text else {})

    def test_a_broker_nobody_asked_never_stops_this_way(self):
        broker = self.broker()
        broker.admit({"op": "call"})
        broker.answered({"ok": True}, delivered=True)
        self.assertFalse(broker.stopping.is_set())


class Recordings(unittest.TestCase):
    def test_a_started_recording_has_its_length_and_time_to_save(self):
        lane = Lane(("p", "c"))
        before = time.monotonic()
        lane.note_surface("device_capture", {"action": "start_recording", "durationMs": 10_000})
        self.assertGreaterEqual(lane.recording_until, before + 10 + 30)
        lane.note_surface("device_capture", {"action": "stop_recording"})
        self.assertEqual(lane.recording_until, 0.0)
        lane.note_surface("web_preview", {"action": "start_recording"})  # the engine's default length
        self.assertGreaterEqual(lane.recording_until, before + 180 + 30)
        lane.note_surface("web_preview_close", {})
        self.assertEqual((lane.recording_until, lane.live_surface), (0.0, False))


class UnconfirmedEngineWork(unittest.TestCase):
    def engine(self):
        engine = EngineProcess.__new__(EngineProcess)
        engine._pending, engine._unanswered, engine._lock, engine._seq = {}, set(), threading.Lock(), 0
        engine.stderr_tail, engine.output_lines, engine.notifications = [], 0, []
        engine._send = lambda obj: None
        engine._proc = mock.Mock()
        engine._proc.poll.return_value = None
        return engine

    def test_a_timed_out_request_is_unconfirmed_until_the_engine_answers_it(self):
        engine = self.engine()
        with self.assertRaisesRegex(EngineError, "outcome unknown"):
            engine.call_tool("rom_build", {}, timeout=0.05)
        self.assertTrue(engine.unconfirmed())
        engine._proc.stdout = [json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}) + "\n"]
        engine._read_stdout()
        self.assertFalse(engine.unconfirmed())

    def test_a_worker_that_exited_has_nothing_unconfirmed(self):
        engine = self.engine()
        with self.assertRaises(EngineError):
            engine.request("tools/call", {}, timeout=0.05)
        engine._proc.poll.return_value = 0
        self.assertFalse(engine.unconfirmed())

    def test_an_answered_request_leaves_nothing_unconfirmed(self):
        engine = self.engine()
        answers: queue.Queue = queue.Queue()

        def send(obj):
            answers.put(obj["id"])

        engine._send = send
        result = []
        thread = threading.Thread(target=lambda: result.append(engine.request("tools/call", {}, timeout=5)))
        thread.start()
        engine._proc.stdout = [json.dumps({"jsonrpc": "2.0", "id": answers.get(timeout=5), "result": {"ok": 1}}) + "\n"]
        engine._read_stdout()
        thread.join(5)
        self.assertEqual(result, [{"ok": 1}])
        self.assertFalse(engine.unconfirmed())


class Client(unittest.TestCase):
    def test_a_retiring_answer_is_restarting_not_unconfirmed(self):
        connected = mock.Mock()
        connected.request.return_value = {
            "ok": False,
            "dispatched": False,
            "denied": {"code": "RETIRING", "message": "hermretro was updated."},
        }
        with self.assertRaisesRegex(client.BrokerRestarting, "hermretro was updated.") as raised:
            client._shutdown_for_replacement(connected, replace=True)
        self.assertTrue(raised.exception.waits)
        connected.request.assert_called_with({"op": "shutdown", "replace": True})

    def test_setup_still_asks_for_a_plain_shutdown(self):
        connected = mock.Mock()
        connected.request.return_value = {"ok": False, "denied": {"code": "BUSY", "message": "live workers"}}
        self.assertFalse(client.request_shutdown(connected))
        connected.request.assert_called_with({"op": "shutdown"})


if __name__ == "__main__":
    unittest.main()
