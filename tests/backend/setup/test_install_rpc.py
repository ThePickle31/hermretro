"""The `install` RPC across reloads and restarts: the last install from its journal, cancel through the broker."""

import unittest
from unittest import mock

from backend.hermes import host as hermes_host
from backend.setup import recovery, rpcs as setup_rpcs
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

    def test_cancel_goes_to_the_broker_and_never_starts_one(self):
        client = FakeBrokerClient({"ok": True, "install": {"state": "running", "cancelling": True}})
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (client, None)):
            answer = self.rpc({"action": "cancel"})
        self.assertEqual(client.asked, [{"op": "install_cancel"}])
        self.assertTrue(answer["install"]["cancelling"])

    def test_a_broker_that_predates_cancel_is_named(self):
        client = FakeBrokerClient({"ok": False, "denied": {"code": "UNKNOWN_OP", "message": "install_cancel"}})
        with mock.patch.object(hermes_host, "try_connect", lambda _dir: (client, None)):
            answer = self.rpc({"action": "cancel"})
        self.assertEqual((answer["ok"], answer["code"]), (False, "BROKER_OUTDATED"))


if __name__ == "__main__":
    unittest.main()
