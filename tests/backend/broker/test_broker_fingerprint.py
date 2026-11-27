"""A running broker names the build it LOADED, not the files on disk (real socket server in-process, no engine).

`hermes plugins update` rewrites the plugin folder under a running broker. When the broker read its fingerprint
from disk at each handshake, it claimed the new build's fingerprint after the update, so the new client kept it and
the old code went on serving every call. tools/ci/clean_install_check.py --update-from runs the real thing.
"""

import fcntl
import hashlib
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker import client, server  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.broker import Broker  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

POSIX = sys.platform.startswith("linux") or sys.platform == "darwin"
NEW_BUILD = "new-build-on-disk"


class Running:
    """A real Broker behind the real socket server, inside this process, in main()'s order: it holds the election lock
    (another raises BlockingIOError, a lost election), and once stopping it stops accepting, closes its workers, then
    removes its socket and token, and only then (the process's exit) closes the listener and lets the election go."""

    def __init__(self, state: Path):
        self.lock = open(state / "broker.lock", "a+")  # noqa: SIM115 - held until this broker has stopped
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise
        self.broker = Broker(state, "node")
        self.socket_path = state / "broker.sock"
        self.server = server.Server(str(self.socket_path), server.Handler)
        self.server.broker = self.broker  # type: ignore[attr-defined]
        (state / "broker.token").write_text(self.broker.token)
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.stopped = threading.Event()
        threading.Thread(target=self._stop_when_asked, daemon=True).start()

    def _stop_when_asked(self):
        self.broker.stopping.wait()
        self.server.shutdown()
        self.broker.close_all()
        self.socket_path.unlink(missing_ok=True)
        (self.socket_path.parent / "broker.token").unlink(missing_ok=True)
        self.server.server_close()
        self.lock.close()
        self.stopped.set()

    def close(self):
        self.broker.stopping.set()
        self.stopped.wait(5)


def launched(start, started: list) -> mock.Mock:
    """What spawn_broker returns after starting a broker of the new files: one that won the election, or one that
    lost it (exit 3) because the old broker still holds its lock while it closes its workers."""
    process = mock.Mock()
    try:
        started.append(start())
    except BlockingIOError:
        process.poll.return_value = 3
    else:
        process.poll.return_value = None
    return process


@unittest.skipUnless(POSIX, "Linux and macOS only")
class FingerprintOfTheLoadedBuild(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="hf-", dir="/tmp")).resolve()  # short: socket paths are capped
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.state = self.base / "run"
        self.state.mkdir(mode=0o700)
        for patch in (
            mock.patch.dict(os.environ, {"HERMRETRO_HOME": str(self.base / "home")}),
            mock.patch.object(paths, "verify_engine", lambda: {"verified": True}),
            mock.patch.object(paths, "find_node", lambda: {"ok": True, "path": "node"}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.loaded = paths.code_fingerprint()
        self.released = paths.release_fingerprint()

    def start(self) -> Running:
        running = Running(self.state)
        self.addCleanup(running.close)
        return running

    def test_the_handshake_names_the_loaded_build_after_the_files_change(self):
        self.start()
        rewritten = {"code_fingerprint": lambda: NEW_BUILD, "release_fingerprint": lambda: NEW_BUILD}
        with mock.patch.multiple(paths, **rewritten):  # the update rewrote the files
            with client.BrokerClient(self.state) as connection:
                self.assertEqual(connection.hello["code_fingerprint"], self.loaded)
                self.assertEqual(connection.hello["loaded_code_fingerprint"], self.loaded)
                self.assertEqual(connection.hello["loaded_fingerprint"], self.released)

    def test_an_update_replaces_it_even_with_an_idle_connection_open(self):
        old = self.start()
        held = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # the page, connected to the old broker
        held.connect(str(old.socket_path))
        self.addCleanup(held.close)
        started: list[Running] = []

        def spawn(state, _node, *, deadline):  # what the update's first call starts: a broker of the new files
            return launched(self.start, started)

        with (
            mock.patch.object(paths, "code_fingerprint", lambda: NEW_BUILD),
            mock.patch.object(client, "spawn_broker", spawn),
        ):
            with client.ensure_broker(self.state, wait=10) as connection:
                self.assertEqual(len(started), 1, "the old broker was kept instead of replaced")
                self.assertEqual(connection.hello["broker_generation"], started[0].broker.generation)
                self.assertEqual(connection.hello["code_fingerprint"], NEW_BUILD)
        self.assertTrue(old.stopped.wait(5), "the old broker did not stop with an idle connection open")
        # A client that held the old one reconnects to the new one.
        with mock.patch.object(paths, "code_fingerprint", lambda: NEW_BUILD):
            with client.BrokerClient(self.state) as again:
                self.assertEqual(again.hello["broker_generation"], started[0].broker.generation)

    def test_a_broker_of_an_older_build_is_replaced(self):
        # Such a broker (no loaded_code_fingerprint: a release's, or one that named the files on disk) may answer
        # with a fingerprint that matches this build's: only the missing field shows it runs older code.
        old = self.start()
        real = server.Handler.handle

        def handle(handler):
            write = handler.wfile.write

            def drop_loaded(data):
                return write(data.replace(b'"loaded_code_fingerprint":"' + self.loaded.encode() + b'",', b""))

            handler.wfile.write = drop_loaded
            return real(handler)

        started: list[Running] = []

        def spawn(state, _node, *, deadline):
            server.Handler.handle = real  # the new broker is of this build
            return launched(self.start, started)

        self.addCleanup(setattr, server.Handler, "handle", real)
        server.Handler.handle = handle
        with mock.patch.object(client, "spawn_broker", spawn):
            with client.BrokerClient(self.state) as probe:
                self.assertEqual(probe.hello["code_fingerprint"], self.loaded)
                self.assertNotIn("loaded_code_fingerprint", probe.hello)
            with client.ensure_broker(self.state, wait=10) as connection:
                self.assertEqual(len(started), 1, "a broker without loaded_code_fingerprint was kept")
                self.assertEqual(connection.hello["broker_generation"], started[0].broker.generation)
        self.assertTrue(old.stopped.wait(5))

    def test_loaded_fingerprint_follows_the_released_clients_rule(self):
        # The releases' code_fingerprint, which their clients compare loaded_fingerprint with: the protocol, the name
        # and bytes of each backend source and of ../plugin.yaml. A gateway of a release keeps this broker.
        digest = hashlib.sha256(f"protocol:{paths.PROTOCOL}".encode())
        released = [*paths.backend_sources(paths.BACKEND_ROOT), ("../plugin.yaml", paths.PLUGIN_ROOT / "plugin.yaml")]
        for name, path in released:
            digest.update(name.encode())
            digest.update(path.read_bytes())
        self.assertEqual(paths.release_fingerprint(), digest.hexdigest()[:24])
        self.start()
        with client.BrokerClient(self.state) as connection:
            self.assertEqual(connection.hello["loaded_fingerprint"], digest.hexdigest()[:24])

    def test_the_same_build_is_kept(self):
        old = self.start()
        with mock.patch.object(client, "spawn_broker") as spawn:
            with client.ensure_broker(self.state, wait=5) as connection:
                self.assertEqual(connection.hello["broker_generation"], old.broker.generation)
        spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
