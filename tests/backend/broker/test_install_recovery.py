"""The page's toolchain install recovers: MCP cancellation, a journal that outlives the broker, specific failures
and a stall that is judged by any change in the toolchain folder, not bytes alone."""

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.broker import broker as broker_module, install as control
from backend.broker.broker import Broker, Denied
from backend.broker.engine import EngineCancelled, EngineProcess
from backend.setup import recovery


class CancellableEngine:
    """Like a real worker after a cancel: the call raises EngineCancelled once cancel is set (EngineProcess does
    that after telling the engine), and the engine lets go of its setup lock a moment later."""

    def __init__(self, root: Path, release_lock=True):
        self.root, self.release_lock = root, release_lock
        self.calls, self.closed, self.cancel = [], False, None
        self.output_lines = 0

    def call_tool(self, tool, arguments, timeout, cancel=None):
        self.calls.append(tool)
        self.cancel = cancel
        lock = recovery.lock_path(self.root)
        lock.mkdir(parents=True)
        cancel.wait(5)

        def wind_down():
            time.sleep(0.2)
            if self.release_lock:
                lock.rmdir()

        threading.Thread(target=wind_down, daemon=True).start()
        raise EngineCancelled(cancel.reason)

    def alive(self):
        return not self.closed

    def close(self, grace=None):
        self.closed = True


class QuietEngine:
    """A worker whose tool never answers and whose folder never changes."""

    output_lines = 0

    def __init__(self):
        self.closed = False

    def call_tool(self, tool, arguments, timeout, cancel=None):
        cancel.wait(5)
        raise EngineCancelled(cancel.reason)

    def alive(self):
        return not self.closed

    def close(self, grace=None):
        self.closed = True


def bare_broker(engine, generation="this-broker"):
    broker = Broker.__new__(Broker)
    broker.stopping = threading.Event()
    broker.install, broker.install_lock = {"state": "idle"}, threading.Lock()
    broker.prepare_lock = threading.Lock()
    broker.events = []
    broker.trace = lambda **record: broker.events.append(record)
    broker.new_engine = lambda name: engine
    broker.install_engine = None
    broker.last_activity = 0
    broker.generation = generation
    return broker


class Recovery(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.base = Path(scratch.name)
        self.root = self.base / ".cache" / "toolchain"
        for item in (
            mock.patch.object(broker_module.paths, "setup_root", return_value=self.root),
            mock.patch.object(broker_module.paths, "DEPS_ROOT", self.base / ".cache"),
            mock.patch.object(broker_module.setup, "seed_toolchain_cache", return_value={"seeded": False}),
            mock.patch.object(broker_module.setup, "free_space", return_value={"enough": True}),
            mock.patch.object(control, "CANCEL_SETTLE", 5.0),
            mock.patch.object(control, "WATCH_EVERY", 0.05),
            mock.patch.object(control, "SETTLE_QUIET", 0.1),
        ):
            item.start()
            self.addCleanup(item.stop)

    def wait_finished(self, broker):
        for _ in range(400):
            if not broker.install_running():
                return
            time.sleep(0.02)
        self.fail("install did not finish")

    def wait_called(self, engine):
        for _ in range(200):
            if engine.calls:
                return
            time.sleep(0.01)
        self.fail("toolchain_prepare was not called")

    def test_idle_read_before_a_delayed_handler_cannot_be_followed_by_expired_admission(self):
        broker = bare_broker(None)
        request = {"op": "install_start", "admit_before": 1000}

        with mock.patch.object(control.time, "time", return_value=2):
            self.assertEqual(broker.control({"op": "install_status"})["install"]["state"], "idle")
            with self.assertRaises(Denied) as rejected:
                broker.control(request)

        self.assertEqual(rejected.exception.code, "START_EXPIRED")
        self.assertEqual(broker.install["state"], "idle")
        self.assertFalse(broker.prepare_lock.locked())
        self.assertIsNone(recovery.read_journal())

    def test_start_checks_its_deadline_again_after_preflight(self):
        broker = bare_broker(None)
        with mock.patch.object(control.time, "time", side_effect=[1, 3]):
            with self.assertRaises(Denied) as rejected:
                broker.control({"op": "install_start", "admit_before": 2000})

        self.assertEqual(rejected.exception.code, "START_EXPIRED")
        self.assertEqual(broker.install["state"], "idle")
        self.assertFalse(broker.prepare_lock.locked())
        self.assertIsNone(recovery.read_journal())

    def test_an_older_clients_unfenced_start_is_denied(self):
        broker = bare_broker(None)
        for request in ({"op": "install_start"}, {"op": "install_start", "admit_before": None}):
            with self.subTest(request=request), self.assertRaises(Denied) as rejected:
                broker.control(request)
            self.assertEqual(rejected.exception.code, "START_EXPIRED")
        self.assertEqual(broker.install["state"], "idle")

    def test_cancel_uses_the_engine_cancellation_and_waits_for_its_lock(self):
        engine = CancellableEngine(self.root)
        broker = bare_broker(engine)
        broker.start_install()
        self.wait_called(engine)
        answer = broker.control({"op": "install_cancel", "run_id": broker.install["run_id"]})["install"]
        self.assertTrue(answer["cancelling"], "the page shows it is stopping, not that it stopped")
        self.wait_finished(broker)
        self.assertTrue(engine.cancel.is_set(), "the request was cancelled through the event the engine call watches")
        self.assertEqual(broker.install["state"], "cancelled")
        self.assertEqual(broker.install["code"], "CANCELLED")
        self.assertTrue(engine.closed)
        self.assertFalse(recovery.lock_path(self.root).exists())
        self.assertFalse(broker.prepare_lock.locked(), "retry is possible: the setup lock is free")
        self.assertEqual(recovery.read_journal()["state"], "cancelled", "the end is recorded for a reload")

    def test_a_lock_the_engine_keeps_is_reported_never_removed(self):
        engine = CancellableEngine(self.root, release_lock=False)
        broker = bare_broker(engine)
        with mock.patch.object(control, "CANCEL_SETTLE", 0.5):
            broker.start_install()
            self.wait_called(engine)
            broker.cancel_install(broker.install["run_id"])
            self.wait_finished(broker)
        self.assertEqual(broker.install["state"], "failed")
        self.assertEqual(broker.install["code"], "SETUP_LOCK_KEPT")
        self.assertIn(str(recovery.lock_path(self.root)), broker.install["hint"])
        self.assertTrue(recovery.lock_path(self.root).exists(), "the engine's lock is left alone")

    def test_a_quiet_install_stops_only_after_nothing_changed(self):
        engine = QuietEngine()
        broker = bare_broker(engine)
        with mock.patch.object(control, "STALL_AFTER", 0.3):
            broker.start_install()
            self.wait_finished(broker)
        self.assertEqual(broker.install["code"], "STALLED")
        self.assertEqual(broker.install["state"], "failed")

    def test_activity_in_the_toolchain_folder_keeps_it_going(self):
        self.root.mkdir(parents=True)
        engine = QuietEngine()
        broker = bare_broker(engine)
        stop = threading.Event()

        def busy():
            n = 0
            while not stop.is_set():
                (self.root / f"step-{n % 3}").write_text(str(n))
                n += 1
                time.sleep(0.05)

        worker = threading.Thread(target=busy, daemon=True)
        worker.start()
        with mock.patch.object(control, "STALL_AFTER", 0.4):
            broker.start_install()
            time.sleep(1.0)
            self.assertTrue(broker.install_running(), "a folder that keeps changing is not a stall")
            stop.set()
            worker.join()
            broker.cancel_install(broker.install["run_id"])
            self.wait_finished(broker)
        self.assertEqual(broker.install["state"], "cancelled")

    def test_a_running_install_from_a_broker_that_ended_reads_as_interrupted(self):
        recovery.write_journal({"state": "running", "started_at": 100.0, "broker": "old-broker"})
        status = bare_broker(None, generation="new-broker").install_status()
        self.assertEqual(status["state"], "interrupted")
        self.assertIn("Finished parts are kept", status["hint"])
        self.assertEqual(recovery.read_journal()["state"], "running", "status must not overwrite the broker's journal")

    def test_invalid_journal_state_is_ignored(self):
        recovery.write_journal({"state": ["running"]})
        self.assertIsNone(recovery.read_journal())

    def test_close_failure_is_reported_and_cannot_start_a_second_live_installer(self):
        engine = QuietEngine()
        engine.call_tool = mock.Mock(return_value={"structuredContent": {"success": True}})
        engine.close = mock.Mock(side_effect=OSError("worker did not exit"))
        broker = bare_broker(engine)
        broker.start_install()
        self.wait_finished(broker)
        self.assertEqual(broker.install["code"], "WORKER_STILL_RUNNING")
        self.assertFalse(broker.prepare_lock.locked())
        self.assertIs(broker.install_engine, engine)
        with self.assertRaises(Denied) as refused:
            broker.start_install()
        self.assertEqual(refused.exception.code, "WORKER_STILL_RUNNING")

    def test_the_hint_names_a_lock_left_by_an_interrupted_install(self):
        recovery.lock_path(self.root).mkdir(parents=True)
        recovery.write_journal({"state": "running", "started_at": 100.0, "broker": "old-broker"})
        found = recovery.recovered(self.root, None)
        self.assertIn(str(recovery.lock_path(self.root)), found["hint"])
        self.assertTrue(recovery.lock_path(self.root).exists())

    def test_the_last_failure_is_shown_after_the_broker_restarts(self):
        recovery.write_journal({"state": "failed", "code": "NETWORK", "error": "cli: ENOTFOUND", "hint": "x"})
        status = bare_broker(None).install_status()
        self.assertEqual((status["state"], status["error"]), ("failed", "cli: ENOTFOUND"))

    def test_the_broker_own_running_install_is_not_called_interrupted(self):
        recovery.write_journal({"state": "running", "started_at": 100.0, "broker": "this-broker"})
        self.assertEqual(recovery.recovered(self.root, "this-broker")["state"], "running")

    def test_a_chat_preparing_the_tools_is_reported_as_elsewhere(self):
        broker = bare_broker(None)
        broker.prepare_lock.acquire()
        self.assertTrue(broker.install_status()["elsewhere"])
        broker.prepare_lock.release()
        self.assertFalse(broker.install_status()["elsewhere"])

    def test_too_little_disk_space_refuses_before_any_download(self):
        broker = bare_broker(None)
        short = {"enough": False, "free_bytes": 100_000_000, "needed_bytes": 2_300_000_000}
        with mock.patch.object(broker_module.setup, "free_space", return_value=short):
            with self.assertRaises(Denied) as refused:
                broker.start_install()
        self.assertEqual(refused.exception.code, "NO_SPACE")
        self.assertIn("2,300 MB", str(refused.exception))
        self.assertFalse(broker.prepare_lock.locked())
        self.assertEqual(broker.install["state"], "idle")


class Explain(unittest.TestCase):
    def test_specific_failures_get_their_next_step(self):
        root = Path("/t/toolchain")
        self.assertEqual(
            recovery.explain("INCOMPLETE", "cli: getaddrinfo EAI_AGAIN registry.npmjs.org", root)[0], "NETWORK"
        )
        self.assertEqual(recovery.explain("INCOMPLETE", "gbdk: ENOSPC: no space left on device", root)[0], "NO_SPACE")
        code, hint = recovery.explain("ENGINE_ERROR", "Another setup owns /t/toolchain/.setup-lock.", root)
        self.assertEqual(code, "SETUP_LOCKED")
        self.assertIn("checked that the recorded owner has stopped", hint)
        self.assertEqual(recovery.explain("INCOMPLETE", "cli: exit 1", root), ("INCOMPLETE", None))


class McpCancellation(unittest.TestCase):
    def test_a_cancelled_request_sends_notifications_cancelled_for_its_id(self):
        engine = EngineProcess.__new__(EngineProcess)
        engine._pending, engine._lock, engine._seq = {}, threading.Lock(), 6
        sent = []
        engine._send = sent.append
        cancel = control._Cancel()
        cancel.reason = "Cancelled by the user."
        threading.Timer(0.1, cancel.set).start()
        with self.assertRaises(EngineCancelled):
            engine.call_tool("toolchain_prepare", {"components": ["build"]}, timeout=10, cancel=cancel)
        self.assertEqual(sent[0]["id"], 7)
        self.assertEqual(
            sent[1],
            {
                "jsonrpc": "2.0",
                "method": "notifications/cancelled",
                "params": {"requestId": 7, "reason": "Cancelled by the user."},
            },
        )
        self.assertEqual(engine._pending, {}, "no answer is waited for after the cancel")

    def test_without_cancel_a_timeout_is_still_outcome_unknown(self):
        engine = EngineProcess.__new__(EngineProcess)
        engine._pending, engine._lock, engine._seq = {}, threading.Lock(), 0
        engine._send = lambda obj: None
        with self.assertRaisesRegex(Exception, "outcome unknown"):
            engine.request("tools/call", {}, timeout=0.05, cancel=threading.Event())


if __name__ == "__main__":
    unittest.main()
