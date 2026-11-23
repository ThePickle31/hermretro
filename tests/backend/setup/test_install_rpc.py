"""The `install` RPC across reloads and restarts: the last install from its journal, cancel through the broker."""

import os
import time
import unittest
from unittest import mock

from backend.broker import BrokerNotRunning, BrokerUnavailable, BrokenBroker, LegacyBrokerHello
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
        with mock.patch.object(hermes_host, "try_connect", return_value=(None, BrokerNotRunning("missing socket"))):
            self.assertEqual(self.rpc({"action": "status"})["install"], {"state": "idle"})
            cancel = self.rpc({"action": "cancel", "run_id": "run-a"})
        self.assertEqual((cancel["ok"], cancel["code"]), (False, "UNAVAILABLE"))

    def test_install_status_and_cancel_are_unavailable_when_the_handshake_times_out(self):
        recovery.write_journal({"state": "running", "started_at": 100.0, "broker": "unknown"})
        error = BrokerUnavailable("Broker did not answer hello before its deadline")
        with mock.patch.object(hermes_host, "try_connect", return_value=(None, error)):
            for action in ("status", "cancel"):
                with self.subTest(action=action):
                    answer = self.rpc({"action": action, "run_id": "run-a"})
                    self.assertEqual((answer["ok"], answer["code"]), (False, "UNAVAILABLE"))
                    self.assertIn("hello", answer["error"])
                    self.assertIn("manifest", answer)
                    self.assertNotIn("install", answer)

    def test_install_status_and_cancel_are_unavailable_when_the_request_times_out(self):
        connected = FakeBrokerClient({})
        with mock.patch.object(hermes_host, "try_connect", return_value=(connected, None)):
            for action in ("status", "cancel"):
                with (
                    self.subTest(action=action),
                    mock.patch.object(connected, "request", side_effect=BrokerUnavailable("Broker request timed out")),
                ):
                    answer = self.rpc({"action": action, "run_id": "run-a"})
                    self.assertEqual((answer["ok"], answer["code"]), (False, "UNAVAILABLE"))
                    self.assertNotIn("install", answer)

    def test_start_timeout_is_unconfirmed_and_status_can_find_the_started_install(self):
        connected = FakeBrokerClient({"ok": True, "install": {"state": "running", "run_id": "run-a"}})
        connected.control_timeout = 3
        expires_at = (time.time() + 60) * 1000
        with (
            mock.patch.object(hermes_host, "ensure_broker", return_value=connected),
            mock.patch.object(
                connected,
                "request",
                side_effect=BrokerUnavailable("Broker did not answer install_start"),
            ),
        ):
            start = self.rpc({"action": "start_fenced", "expires_at": expires_at})
        self.assertEqual((start["ok"], start["code"]), (False, "UNAVAILABLE"))
        self.assertLess(start["start_expires_at"], expires_at)
        self.assertIn("Install start was unconfirmed", start["error"])
        self.assertNotIn("install", start)

        with mock.patch.object(hermes_host, "try_connect", return_value=(connected, None)):
            status = self.rpc({"action": "status"})
        self.assertEqual(status["install"], {"state": "running", "run_id": "run-a"})
        self.assertEqual(connected.asked, [{"op": "install_status"}])

    def test_expired_page_start_never_connects_or_spawns(self):
        with mock.patch.object(hermes_host, "ensure_broker") as connect:
            result = self.rpc({"action": "start_fenced", "expires_at": 1})

        self.assertEqual((result["ok"], result["code"]), (False, "START_EXPIRED"))
        connect.assert_not_called()

    def test_admission_uses_gateway_monotonic_time_and_is_confirmed_before_reading_status(self):
        client = FakeBrokerClient({"ok": True, "install": {"state": "running", "run_id": "run-a"}})
        now = mock.Mock(return_value=100)
        with (
            mock.patch.object(setup_rpcs.time, "monotonic", now),
            mock.patch.object(setup_rpcs.time, "time", return_value=9_999_999_999),
            mock.patch.object(hermes_host, "ensure_broker", return_value=client) as ensure,
        ):
            given = self.rpc({"action": "prepare_start"})
            ensure.assert_not_called()
            self.assertEqual(given, {"ok": True, "admission": 160.0})
            admission = given["admission"]
            result = self.rpc({"action": "start_admitted", "admission": admission})
            self.assertEqual(result["admission"], admission)
            self.assertEqual(result["install"]["run_id"], "run-a")
            ensure.assert_called_once_with(deadline=admission)
            self.assertEqual(client.asked, [{"op": "install_start", "admit_until": admission}])

            def absent(_run):
                now.return_value = admission + 1
                return None, BrokerNotRunning("missing socket")

            with mock.patch.object(hermes_host, "try_connect", side_effect=absent):
                status = {"action": "status", "admission": admission}
                self.assertNotIn("expired_admission", self.rpc(status), "status began before the expiry")
                self.assertEqual(self.rpc(status)["expired_admission"], admission)
            ensure.reset_mock()
            expired = self.rpc({"action": "start_admitted", "admission": admission})
            self.assertEqual(expired["code"], "START_EXPIRED")
            ensure.assert_not_called()

    def test_known_legacy_status_can_be_retired_only_by_an_explicit_action(self):
        hello = {"ok": False, "error": "FileNotFoundError: adapter/../plugin.yaml"}
        stopped = (None, BrokenBroker(hello, True))
        missing = (None, BrokerNotRunning("missing socket"))
        with (
            mock.patch.object(hermes_host, "try_connect") as connect,
            mock.patch.object(hermes_host, "ensure_broker") as spawn,
            mock.patch.object(setup_rpcs, "_broker_lock") as lock,
        ):
            connect.return_value = None, LegacyBrokerHello(hello["error"])
            status = self.rpc({"action": "status"})
            self.assertEqual((status["ok"], status["code"]), (False, "BROKER_LEGACY"))
            self.assertEqual(connect.call_args.kwargs, {})
            lock.assert_not_called()

            connect.return_value = None, BrokenBroker(hello, False)
            fresh = {"action": "status", "retire_legacy": True}
            busy = self.rpc(fresh)
            self.assertEqual((busy["ok"], busy["code"]), (False, "BUSY"))
            self.assertTrue(connect.call_args.kwargs["retire_broken"])
            self.assertGreater(connect.call_args.kwargs["deadline"], time.monotonic())
            lock.assert_not_called()

            connect.side_effect = [stopped, missing]
            lock.return_value.__enter__.return_value = True
            answer = self.rpc(fresh)
            self.assertTrue(answer["ok"])
            self.assertEqual(answer["install"], {"state": "idle"})
            self.assertNotIn("retire_broken", connect.call_args.kwargs)
            lock.assert_called_once()
            spawn.assert_not_called()

    def test_bad_acknowledgements_are_unavailable_for_all_install_actions(self):
        replies = (
            {"ok": True},
            {"ok": True, "install": []},
            {"ok": True, "install": {"state": "unknown"}},
            {"ok": True, "install": {"state": ["idle"]}},
            {"ok": True, "install": {"state": "running"}},
            {"ok": False, "dispatched": None, "error": "unexpected broker error"},
        )
        for reply in replies:
            for action in ("start", "status", "cancel"):
                connected = FakeBrokerClient(reply)
                connected.control_timeout = 3
                with (
                    self.subTest(reply=reply, action=action),
                    mock.patch.object(hermes_host, "ensure_broker", return_value=connected),
                    mock.patch.object(hermes_host, "try_connect", return_value=(connected, None)),
                ):
                    answer = self.rpc({"action": action})
                    self.assertEqual((answer["ok"], answer["code"]), (False, "UNAVAILABLE"))
                    self.assertNotIn("install", answer)

    def test_a_start_cannot_acknowledge_idle_but_preserves_an_explicit_denial(self):
        connected = FakeBrokerClient({"ok": True, "install": {"state": "idle"}})
        connected.control_timeout = 3
        with mock.patch.object(hermes_host, "ensure_broker", return_value=connected):
            self.assertEqual(self.rpc({"action": "start"})["code"], "UNAVAILABLE")
            connected.answer = {
                "ok": False,
                "dispatched": False,
                "denied": {"code": "NO_SPACE", "message": "Out of room"},
            }
            denied = self.rpc({"action": "start"})
        self.assertEqual((denied["ok"], denied["code"], denied["error"]), (False, "NO_SPACE", "Out of room"))

    def test_cancel_goes_to_the_broker_with_its_run_and_never_starts_one(self):
        client = FakeBrokerClient({"ok": True, "install": {"state": "running", "run_id": "run-a", "cancelling": True}})
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
