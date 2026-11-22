"""The `install` RPC across reloads and restarts: the last install from its journal, cancel through the broker."""

import os
import unittest
from unittest import mock

from backend.broker.broker import Broker, Denied
from backend.hermes import host as hermes_host
from backend.setup import recovery, rpcs as setup_rpcs
from backend.system import paths
from tests.support import FakeBrokerClient, isolated_home, throwaway_deps


class InstallRpc(unittest.TestCase):
    def setUp(self):
        found = isolated_home(self)
        deps = throwaway_deps(found.base)
        self.cache = deps.__enter__()
        self.addCleanup(deps.__exit__, None, None, None)
        self.rpc = setup_rpcs.rpc_install(None)

    def test_with_no_broker_a_running_install_from_the_journal_reads_as_interrupted(self):
        recovery.write_journal({"state": "running", "started_at": 100.0, "broker": "gone"})
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)):
            answer = self.rpc({"action": "status"})
        self.assertTrue(answer["ok"])
        self.assertEqual(answer["install"]["state"], "interrupted")
        self.assertIn("Install again", answer["install"]["hint"])
        self.assertIn("free_bytes", answer["space"], "the page can check the space before it starts")

    def test_with_no_broker_and_no_journal_it_is_idle(self):
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)):
            self.assertEqual(self.rpc({"action": "status"})["install"], {"state": "idle"})

    def test_cancel_goes_to_the_broker_with_its_run_and_never_starts_one(self):
        client = FakeBrokerClient({"ok": True, "install": {"state": "running", "cancelling": True}})
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (client, None)):
            answer = self.rpc({"action": "cancel", "run_id": "run-a"})
        self.assertEqual(client.asked, [{"op": "install_cancel", "run_id": "run-a"}])
        self.assertTrue(answer["install"]["cancelling"])

    def test_a_broker_from_before_cancel_is_named_from_its_actual_denial(self):
        # What the pre-cancel broker answers: no install_cancel op, so the request falls through to the lane ops,
        # whose owner check (unchanged since) refuses it before the unknown-op branch. Built from that same check.
        try:
            Broker.owner_of({"op": "install_cancel", "run_id": "run-a"})
        except Denied as denial:
            old = {"ok": False, "dispatched": False, "denied": {"code": denial.code, "message": str(denial)}}
        self.assertEqual(old["denied"]["code"], "IDENTITY_REQUIRED")
        client = FakeBrokerClient(old)
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (client, None)):
            answer = self.rpc({"action": "cancel", "run_id": "run-a"})
        self.assertEqual((answer["ok"], answer["code"]), (False, "CANCEL_UNSUPPORTED"))
        self.assertIn("still running", answer["error"])
        self.assertNotIn("conversation identity", answer["error"], "the page names the old broker, not a lane rule")

    def test_remove_tools_waits_for_a_recorded_installer_worker(self):
        (self.cache / "toolchain").mkdir(parents=True, exist_ok=True)
        recovery.write_journal({"state": "failed", "code": "WORKER_STILL_RUNNING", "worker_pgid": os.getpgid(0)})
        run = self.cache.parent / "run"
        run.mkdir(exist_ok=True)
        with (
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)),
            mock.patch.object(paths, "runtime_dir", lambda: run),
        ):
            answer = setup_rpcs.rpc_remove_tools(None)({})
        self.assertEqual((answer["ok"], answer["code"]), (False, "WORKER_STILL_RUNNING"))
        self.assertTrue((self.cache / "toolchain").is_dir(), "nothing deleted while the worker may use it")


if __name__ == "__main__":
    unittest.main()
