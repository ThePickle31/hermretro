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

    def __init__(self, state: Path, busy: bool = False):
        self.busy, self.requests, self.socket_path = busy, [], state / "broker.sock"
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
                        elif self.busy:
                            answer = {"ok": False, "denied": {"code": "BUSY", "message": "live workers"}}
                        else:
                            answer = {"ok": True}
                        stream.write((json.dumps(answer) + "\n").encode())
                        stream.flush()
                if "shutdown" in self.requests and not self.busy:  # stopped, as the real one does
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

    def old(self, busy: bool = False) -> OldBroker:
        broker = OldBroker(self.state, busy)
        self.addCleanup(broker.close)
        return broker

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

        def spawn(state, _node):  # the old one has stopped; the new one starts
            started.append(state)
            process = mock.Mock()
            process.poll.return_value = None
            return process

        new = mock.Mock(
            hello={
                "ok": True,
                "code_fingerprint": client.paths.code_fingerprint(),
                "plugin_root": str(client.paths.PLUGIN_ROOT),
            }
        )
        real = client.try_connect

        def connect(state, retire_broken=False):  # the real socket until the new broker has been started
            return (new, None) if started else real(state, retire_broken)

        with (
            mock.patch.object(client.paths, "find_node", lambda: node),
            mock.patch.object(client, "spawn_broker", spawn),
            mock.patch.object(client, "try_connect", connect),
        ):
            self.assertIs(client.ensure_broker(self.state, wait=5), new)
        self.assertEqual(broker.requests, ["hello", "shutdown"])
        self.assertEqual(started, [self.state])


if __name__ == "__main__":
    unittest.main()
