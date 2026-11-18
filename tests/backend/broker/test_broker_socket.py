"""The broker's socket protocol, end to end against a real broker process (no engine work, about a second).

The safety net for refactoring backend/broker/: every answer here comes over the real Unix socket, from the
handshake to a clean stop. The real engine's behaviour is the acceptance suite's job.
"""

import json
import os
import shutil
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

POSIX = sys.platform.startswith("linux") or sys.platform == "darwin"
OWNER = {"profile": "socket-test", "conversation_id": "conv-1"}


@unittest.skipUnless(POSIX, "Linux and macOS only")
class BrokerSocket(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not paths.find_node().get("ok"):
            raise unittest.SkipTest("Node.js 22 or newer is not installed")
        cls.base = Path(tempfile.mkdtemp(prefix="hs-", dir="/tmp")).resolve()  # short: socket paths are capped
        cls.state = cls.base / "run"
        environment = {k: v for k, v in os.environ.items() if k != "INVOCATION_ID"}  # no systemd scope in tests
        environment.update(
            {"HERMRETRO_HOME": str(cls.base / "home"), "HERMRETRO_BROKER_IDLE_SECONDS": "20"}
        )  # a leaked one exits soon
        try:
            with mock.patch.dict(os.environ, environment, clear=True):
                cls.broker = client.ensure_broker(cls.state, wait=30)
        except Exception:
            shutil.rmtree(cls.base, ignore_errors=True)
            raise
        cls.pid = cls.broker.hello["pid"]

    @classmethod
    def tearDownClass(cls):
        try:
            if not cls.stopped():
                cls.broker.request({"op": "shutdown", "force": True})
        except Exception:  # noqa: BLE001 - already gone
            pass
        cls.broker.close()
        cls.reap()
        shutil.rmtree(cls.base, ignore_errors=True)

    @classmethod
    def stopped(cls) -> bool:
        try:
            os.kill(cls.pid, 0)
        except ProcessLookupError:
            return True
        return False

    @classmethod
    def reap(cls) -> bool:
        for _ in range(100):
            try:
                if os.waitpid(cls.pid, os.WNOHANG)[0] == cls.pid:
                    return True
            except ChildProcessError:
                if cls.stopped():
                    return True
            time.sleep(0.1)
        return False

    def ask(self, payload: dict) -> dict:
        return self.broker.request(payload)

    def test_1_the_handshake_refuses_a_wrong_token_and_anything_before_hello(self):
        wrong = client.BrokerClient(self.state, token="0" * 64)
        try:
            self.assertEqual(wrong.hello.get("denied", {}).get("code"), "UNAUTHENTICATED")
        finally:
            wrong.close()
        self.assertTrue(self.broker.hello["ok"])
        self.assertEqual(self.broker.hello["protocol"], paths.PROTOCOL)
        self.assertEqual(self.broker.hello["code_fingerprint"], paths.code_fingerprint())
        self.assertEqual(self.broker.hello["loaded_fingerprint"], paths.code_fingerprint())

    def test_2_read_only_ops_answer_without_starting_a_worker(self):
        stats = self.ask({"op": "stats"})
        self.assertEqual((stats["ok"], stats["pid"], stats["lanes"]), (True, self.pid, []))
        self.assertEqual(
            self.ask({"op": "lane_status", "profile": "socket-test", "session_id": "nope"}), {"ok": True, "lane": None}
        )
        activity = self.ask({"op": "activity", "profile": "socket-test", "ids": ["nope"]})
        self.assertEqual((activity["ok"], activity["lane"]), (True, None))
        install = self.ask({"op": "install_status"})
        self.assertTrue(install["ok"])
        self.assertIn(install["install"]["state"], ("idle", "done", "failed"))
        self.assertEqual(self.ask({"op": "stats"})["lanes"], [])

    def test_3_identity_and_lanes_are_enforced(self):
        for owner in (None, {"profile": "socket-test", "conversation_id": ""}, {"conversation_id": "conv-1"}):
            answer = self.ask({"op": "call", "owner": owner, "tool": "session_status", "arguments": {}})
            self.assertEqual(
                (answer["ok"], answer["dispatched"], answer["denied"]["code"]),
                (False, False, "IDENTITY_REQUIRED"),
                owner,
            )
        for op in ("grant_lease", "release_project", "close_lane", "no_such_op"):
            answer = self.ask({"op": op, "owner": OWNER, "task_id": "t1"})
            self.assertEqual(answer["denied"]["code"], "NO_LANE", op)
        self.assertEqual(self.ask({"op": "stats"})["lanes"], [], "a denied call starts no worker")

    def test_4_denials_are_traced(self):
        self.ask({"op": "call", "owner": None, "tool": "session_status", "arguments": {}})
        events = [json.loads(line) for line in (self.state / "trace.jsonl").read_text().splitlines()]
        self.assertIn("broker_started", [event.get("event") for event in events])
        self.assertTrue(
            any(event.get("event") == "denied" and event.get("code") == "IDENTITY_REQUIRED" for event in events)
        )

    def test_5_an_idle_broker_stops_cleanly_when_asked(self):
        # Even with another connection open and silent: the update check (tools/ci/update_check.py) holds one so
        # the old broker cannot idle out, and relies on the new client's shutdown not waiting for it.
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as silent:
            silent.connect(str(self.state / "broker.sock"))
            self.assertEqual(self.ask({"op": "shutdown"}), {"ok": True})
            self.assertTrue(self.reap(), "the broker did not exit")
        self.assertFalse((self.state / "broker.sock").exists())
        self.assertFalse((self.state / "broker.token").exists())


if __name__ == "__main__":
    unittest.main()
