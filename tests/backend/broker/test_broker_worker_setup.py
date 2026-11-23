"""A running broker whose new workers cannot start is replaced when idle (real socket server in-process, no engine).

Every worker inherits the broker's Node.js and temporary folder. A versioned Node replaced at another path, or a
TMPDIR fixed and Hermes restarted, leaves a broker that survived the restart (Linux keeps it in its own scope)
failing every new worker: its handshake says so, and the client replaces it unless it still runs someone's game.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker import client, server  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.lane import Denied  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.test_broker_fingerprint import Running  # noqa: E402 - the repository root goes on sys.path first

POSIX = sys.platform.startswith("linux") or sys.platform == "darwin"


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\necho v24.1.0\n")
    path.chmod(0o755)
    return path


@unittest.skipUnless(POSIX, "Linux and macOS only")
class StaleWorkerSetup(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="hw-", dir="/tmp")).resolve()  # short: socket paths are capped
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.state = self.base / "run"
        self.state.mkdir(mode=0o700)
        self.old_node = executable(self.base / "node-24.0.0" / "bin" / "node")
        self.new_node = executable(self.base / "node-24.1.0" / "bin" / "node")
        self.found = {"ok": True, "path": str(self.new_node)}
        self.temp_broken = False
        for patch in (
            mock.patch.dict(os.environ, {"HERMRETRO_HOME": str(self.base / "home"), "TMPDIR": str(self.base)}),
            mock.patch.object(paths, "verify_engine", lambda: {"verified": True}),
            mock.patch.object(paths, "find_node", lambda: self.found),
            # The broker reads its workers' environment (sanitized_environment), the client the one it would pass.
            mock.patch.object(server, "sanitized_environment", lambda: {"TMPDIR": "/broker-temp"}),
            mock.patch.object(
                server.host_os,
                "engine_temp_ready",
                lambda env: not (self.temp_broken and env.get("TMPDIR") == "/broker-temp"),
            ),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.started: list[Running] = []

    def start(self, node: Path) -> Running:
        running = Running(self.state)
        running.broker.node = str(node)
        self.addCleanup(running.close)
        return running

    def spawn(self, _state, node, *, deadline):  # what ensure_broker starts: a broker of the Node it found now
        self.temp_broken = False  # a fresh broker inherits the client's (fixed) TMPDIR
        self.started.append(self.start(Path(node)))
        process = mock.Mock()
        process.poll.return_value = None
        return process

    def connect(self) -> client.BrokerClient:
        with mock.patch.object(client, "spawn_broker", self.spawn):
            return client.ensure_broker(self.state, wait=10)

    def test_the_handshake_names_the_node_and_whether_temp_works(self):
        self.start(self.old_node)
        with client.BrokerClient(self.state) as connection:
            self.assertEqual(connection.hello["node"], str(self.old_node))
            self.assertIs(connection.hello["temp_ok"], True)

    def test_an_idle_broker_whose_node_was_removed_is_replaced_by_one_of_the_new_node(self):
        old = self.start(self.old_node)
        shutil.rmtree(self.old_node.parent.parent)  # the versioned install replaced at another path
        with self.connect() as connection:
            self.assertEqual(len(self.started), 1, "the broker of the deleted Node was kept")
            self.assertEqual(connection.hello["node"], str(self.new_node))
        self.assertTrue(old.stopped.wait(5))

    def test_a_broker_whose_node_is_still_installed_is_kept(self):
        old = self.start(self.old_node)  # an older Node still on disk works: no reason to replace it
        with self.connect() as connection:
            self.assertEqual(self.started, [])
            self.assertEqual(connection.hello["broker_generation"], old.broker.generation)

    def test_a_busy_broker_keeps_its_games_and_its_next_worker_says_what_to_do(self):
        old = self.start(self.old_node)
        shutil.rmtree(self.old_node.parent.parent)
        with mock.patch.object(old.broker, "install_running", return_value=True):  # busy: shutdown is refused
            with self.connect() as connection:
                self.assertEqual(self.started, [])
                self.assertEqual(connection.hello["broker_generation"], old.broker.generation)
        self.assertFalse(old.stopped.is_set())
        with (
            mock.patch.object(
                paths, "select_engine", return_value={"check": {"verified": True}, "root": paths.ENGINE_ROOT}
            ),
            self.assertRaises(Denied) as denied,
        ):
            old.broker.new_engine("chromatic-studio-dev")
        self.assertEqual(denied.exception.code, "NODE_MISSING")
        self.assertIn(str(self.old_node), str(denied.exception))
        self.assertIn("close the chats that are running games", str(denied.exception))

    def test_an_idle_broker_whose_temp_folder_cannot_work_is_replaced_once_the_clients_can(self):
        old = self.start(self.new_node)
        self.temp_broken = True  # TMPDIR fixed and Hermes restarted; the broker survived with the old one
        with client.BrokerClient(self.state) as probe:
            self.assertIs(probe.hello["temp_ok"], False)
        with self.connect() as connection:
            self.assertEqual(len(self.started), 1, "the broker with the unusable temp folder was kept")
            self.assertIs(connection.hello["temp_ok"], True)
        self.assertTrue(old.stopped.wait(5))

    def test_a_temp_folder_no_new_broker_could_fix_keeps_the_broker(self):
        old = self.start(self.new_node)
        self.temp_broken = True
        with mock.patch.object(client.host_os, "engine_temp_ready", return_value=False):  # the client's is bad too
            with self.connect() as connection:
                self.assertEqual(self.started, [])
                self.assertEqual(connection.hello["broker_generation"], old.broker.generation)


if __name__ == "__main__":
    unittest.main()
