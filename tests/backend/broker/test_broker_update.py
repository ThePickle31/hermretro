"""A broker of an older release still running after `hermes plugins update` (no engine, well under a second).

The broker of the releases before the backend/ layout reads its fingerprint from adapter/, which the update to the backend/ layout removes: from then on
its handshake fails with an error. The client must ask it to stop and start the new one instead of waiting on it
(every attempt also kept it from idling out). tools/ci/clean_install_check.py --update-from runs the real thing.
"""

import json
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first

POSIX = sys.platform.startswith("linux") or sys.platform == "darwin"
BROKEN_HELLO = {"ok": False, "dispatched": None, "error": "FileNotFoundError: adapter/../plugin.yaml"}


class OldBroker:
    """Answers like such a broker once its files are gone: the handshake errors (after accepting the token),
    and a shutdown is granted unless it is busy."""

    def __init__(self, state: Path, busy: bool = False, silent_shutdown: bool = False):
        self.busy, self.silent_shutdown = busy, silent_shutdown
        self.requests, self.socket_path = [], state / "broker.sock"
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
        (state / "broker.token").write_text("token")
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.socket_path))
        self.server.listen()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        try:
            while True:
                connection, _ = self.server.accept()
                with connection, connection.makefile("rwb") as stream:
                    for line in stream:
                        request = json.loads(line)
                        self.requests.append(request["op"])
                        if request["op"] == "hello":
                            answer = BROKEN_HELLO
                        elif self.silent_shutdown:
                            continue
                        elif self.busy:
                            answer = {"ok": False, "denied": {"code": "BUSY", "message": "live workers"}}
                        else:
                            answer = {"ok": True}
                        stream.write((json.dumps(answer) + "\n").encode())
                        stream.flush()
                if "shutdown" in self.requests and not (self.busy or self.silent_shutdown):
                    self.close()
                    return
        except OSError:
            return  # closed by the test

    def close(self):
        self.server.close()
        self.socket_path.unlink(missing_ok=True)


@unittest.skipUnless(POSIX, "Linux and macOS only")
class BrokerAfterUpdate(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="hu-", dir="/tmp")).resolve()  # short: socket paths are capped
        self.state = self.base / "run"
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def old(self, **kwargs) -> OldBroker:
        broker = OldBroker(self.state, **kwargs)
        self.addCleanup(broker.close)
        return broker

    def test_a_broker_that_never_answers_hello_obeys_the_startup_deadline(self):
        self.state.mkdir()
        (self.state / "broker.token").write_text("token")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(self.state / "broker.sock"))
            listener.listen()
            began = time.monotonic()
            found, error = client.try_connect(self.state, deadline=began + 0.05)
            self.assertLess(time.monotonic() - began, 1.0)
        self.assertIsNone(found)
        self.assertIsInstance(error, client.BrokerUnavailable)
        self.assertNotIsInstance(error, client.BrokerNotRunning)

    def test_silent_hello_does_not_start_another_broker(self):
        self.state.mkdir()
        (self.state / "broker.token").write_text("token")
        with (
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener,
            mock.patch.object(client.paths, "find_node", return_value={"ok": True, "path": "node"}),
            mock.patch.object(client, "spawn_broker") as spawn,
        ):
            listener.bind(str(self.state / "broker.sock"))
            listener.listen()
            began = time.monotonic()
            with self.assertRaisesRegex(client.BrokerUnavailable, "did not answer hello"):
                client.ensure_broker(self.state, wait=0.05)
            self.assertLess(time.monotonic() - began, 1.0)
        spawn.assert_not_called()

    def test_a_silent_legacy_shutdown_is_unconfirmed_and_obeys_the_startup_deadline(self):
        broker = self.old(silent_shutdown=True)
        with (
            mock.patch.object(client.paths, "find_node", return_value={"ok": True, "path": "node"}),
            mock.patch.object(client, "spawn_broker") as spawn,
        ):
            began = time.monotonic()
            with self.assertRaisesRegex(client.BrokerUnavailable, "did not confirm shutdown") as failure:
                client.ensure_broker(self.state, wait=0.05)
            self.assertLess(time.monotonic() - began, 1.0)
        self.assertNotIsInstance(failure.exception, client.OtherCopyBusy)
        self.assertEqual(broker.requests, ["hello", "shutdown"])
        spawn.assert_not_called()

    def test_install_start_has_a_control_deadline_and_engine_calls_keep_their_budget(
        self,
    ):
        connected = client.BrokerClient.__new__(client.BrokerClient)
        connected.startup_deadline = None
        connected.hello = {"install_start_deadline": True}
        connected.sock = mock.Mock()
        connected.sock.recv.side_effect = TimeoutError
        with self.assertRaisesRegex(client.BrokerUnavailable, "did not answer install_start"):
            connected.request({"op": "install_start"})
        wire = json.loads(connected.sock.sendall.call_args.args[0])
        self.assertGreater(wire["admit_before"], time.time() * 1000)
        self.assertLessEqual(wire["admit_before"], (time.time() + client.CONTROL_TIMEOUT) * 1000)
        for deadline in connected.sock.settimeout.call_args_list:
            self.assertGreater(deadline.args[0], 0)
            self.assertLessEqual(deadline.args[0], client.CONTROL_TIMEOUT)

        connected.sock.recv.side_effect = None
        connected.sock.recv.return_value = b'{"ok":true}\n'
        connected.call(None, "chromatic_toolchain_prepare", timeout=900)
        connected.sock.settimeout.assert_called_with(None)
        self.assertEqual(json.loads(connected.sock.sendall.call_args.args[0])["timeout"], 900)

    def test_an_older_broker_never_receives_an_unfenced_start(self):
        connected = client.BrokerClient.__new__(client.BrokerClient)
        connected.startup_deadline = None
        connected.hello = {"ok": True}
        connected.sock = mock.Mock()

        answer = connected.request({"op": "install_start"})

        self.assertEqual(
            (answer["ok"], answer["dispatched"], answer["denied"]["code"]), (False, False, "BROKER_OUTDATED")
        )
        connected.sock.sendall.assert_not_called()

    def test_a_malformed_shutdown_cannot_authorize_replacement(self):
        connected = mock.Mock()
        connected.request.return_value = {"ok": False, "denied": "invalid reply"}
        with self.assertRaisesRegex(client.BrokerUnavailable, "did not confirm shutdown"):
            client._shutdown_for_replacement(connected)

    def test_a_plain_connect_never_stops_it(self):
        broker = self.old()
        found, error = client.try_connect(self.state)
        self.assertIsNone(found)
        self.assertNotIsInstance(error, client.BrokenBroker)
        self.assertEqual(broker.requests, ["hello"])

    def test_the_client_asks_it_to_stop(self):
        broker = self.old()
        found, error = client.try_connect(self.state, retire_broken=True)
        self.assertIsNone(found)
        self.assertIsInstance(error, client.BrokenBroker)
        self.assertTrue(isinstance(error, client.BrokenBroker) and error.stopping)
        self.assertEqual(broker.requests, ["hello", "shutdown"])

    def test_a_busy_one_is_reported_not_waited_on(self):
        self.old(busy=True)
        node = {"ok": True, "path": "node"}
        with (
            mock.patch.object(client.paths, "find_node", lambda: node),
            mock.patch.object(client, "spawn_broker") as spawn,
        ):
            with self.assertRaisesRegex(client.BrokerUnavailable, "previous version"):
                client.ensure_broker(self.state, wait=5)
        spawn.assert_not_called()

    def test_a_stopped_one_is_replaced(self):
        broker = self.old()
        node = {"ok": True, "path": "node"}
        started = []

        def spawn(state, _node, *, deadline):  # the old one has stopped; the new one starts
            started.append(state)
            process = mock.Mock()
            process.poll.return_value = None
            return process

        new = mock.Mock(
            hello={
                "ok": True,
                "code_fingerprint": client.paths.code_fingerprint(),
                "loaded_fingerprint": client.paths.code_fingerprint(),
                "plugin_root": str(client.paths.PLUGIN_ROOT),
            }
        )
        real = client.try_connect

        def connect(state, retire_broken=False, **kwargs):  # the real socket until the new broker has been started
            return (new, None) if started else real(state, retire_broken, **kwargs)

        with (
            mock.patch.object(client.paths, "find_node", lambda: node),
            mock.patch.object(client, "spawn_broker", spawn),
            mock.patch.object(client, "try_connect", connect),
        ):
            self.assertIs(client.ensure_broker(self.state, wait=5), new)
        self.assertEqual(broker.requests, ["hello", "shutdown"])
        self.assertEqual(started, [self.state])

    def assert_retry_uses_remaining_budget(self, failure):
        now = 0.0

        def connect(*args, **kwargs):
            nonlocal now
            now = 0.04
            return None, failure

        def sleep(seconds):
            nonlocal now
            now += seconds

        clock = mock.Mock(monotonic=lambda: now, sleep=mock.Mock(side_effect=sleep))
        with (
            mock.patch.object(client, "time", clock),
            mock.patch.object(client.paths, "find_node", return_value={"ok": True, "path": "node"}),
            mock.patch.object(client, "try_connect", side_effect=connect),
            mock.patch.object(client, "spawn_broker"),
            self.assertRaises(client.BrokerUnavailable),
        ):
            client.ensure_broker(self.state, wait=0.05)
        clock.sleep.assert_called_once()
        self.assertAlmostEqual(clock.sleep.call_args.args[0], 0.01)

    def test_a_spawn_retry_uses_only_the_remaining_budget(self):
        self.assert_retry_uses_remaining_budget(client.BrokerNotRunning("missing socket"))

    def test_waiting_for_shutdown_uses_only_the_remaining_budget(self):
        self.assert_retry_uses_remaining_budget(client.BrokenBroker(BROKEN_HELLO, True))

    def test_a_failed_connect_that_uses_the_remaining_budget_does_not_spawn(self):
        clock = mock.Mock()
        clock.monotonic.side_effect = (0.0, 0.0, 0.05)
        with (
            mock.patch.object(client, "time", clock),
            mock.patch.object(client.paths, "find_node", return_value={"ok": True, "path": "node"}),
            mock.patch.object(client, "try_connect", return_value=(None, client.BrokerNotRunning("missing socket"))),
            mock.patch.object(client, "spawn_broker") as spawn,
            self.assertRaisesRegex(client.BrokerUnavailable, "deadline expired"),
        ):
            client.ensure_broker(self.state, wait=0.05)
        spawn.assert_not_called()
        clock.sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
