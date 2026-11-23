"""The broker starts in its own systemd scope only where that is proven to work (backend/broker/client.py)."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first


class BrokerScope(unittest.TestCase):
    def setUp(self):
        client._SCOPE_RUNNER = None

    def tearDown(self):
        client._SCOPE_RUNNER = None

    def test_outside_a_systemd_unit_the_broker_starts_as_before(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INVOCATION_ID", None)
            self.assertEqual(client.own_scope({"PATH": os.environ.get("PATH", "")}), [])

    def test_a_failing_probe_falls_back_to_a_plain_start(self):
        failed = subprocess.CompletedProcess([], 1, b"", b"Failed to connect to bus")
        with (
            mock.patch.dict(os.environ, {"INVOCATION_ID": "x"}),
            mock.patch.object(client.shutil, "which", return_value="/usr/bin/systemd-run"),
            mock.patch.object(client.subprocess, "run", return_value=failed),
        ):
            self.assertEqual(client.own_scope({"PATH": "/usr/bin"}), [])

    def test_inside_a_unit_each_broker_gets_its_own_scope(self):
        ok = subprocess.CompletedProcess([], 0, b"", b"")
        with (
            mock.patch.dict(os.environ, {"INVOCATION_ID": "x"}),
            mock.patch.object(client.shutil, "which", return_value="/usr/bin/systemd-run"),
            mock.patch.object(client.subprocess, "run", return_value=ok) as probe,
        ):
            first = client.own_scope({"PATH": "/usr/bin"})
            second = client.own_scope({"PATH": "/usr/bin"})
        self.assertEqual(first[:5], ["/usr/bin/systemd-run", "--user", "--scope", "--quiet", "--collect"])
        self.assertTrue(first[5].startswith("--unit=hermretro-broker-"))
        self.assertNotEqual(first[5], second[5])  # unit names never collide
        self.assertEqual(probe.call_count, 1)  # probed once per process

    def test_the_startup_budget_bounds_the_probe_without_caching_a_short_timeout(self):
        with (
            mock.patch.dict(os.environ, {"INVOCATION_ID": "x"}),
            mock.patch.object(client.shutil, "which", return_value="/usr/bin/systemd-run"),
            mock.patch.object(
                client.subprocess, "run", side_effect=subprocess.TimeoutExpired("systemd-run", 0.05)
            ) as probe,
            mock.patch.object(client.subprocess, "Popen") as popen,
            tempfile.TemporaryDirectory() as run,
        ):
            with self.assertRaisesRegex(TimeoutError, "scope probe timed out"):
                client.spawn_broker(Path(run), "node", deadline=time.monotonic() + 0.05)
        self.assertGreater(probe.call_args.kwargs["timeout"], 0.0)
        self.assertLessEqual(probe.call_args.kwargs["timeout"], 0.05)
        self.assertIsNone(client._SCOPE_RUNNER)
        popen.assert_not_called()

    def test_the_broker_does_not_spawn_if_the_scope_probe_used_the_budget(self):
        clock = mock.Mock()
        clock.monotonic.return_value = 0.05
        with (
            mock.patch.object(client, "time", clock),
            mock.patch.object(client, "own_scope", return_value=[]) as scope,
            mock.patch.object(client.subprocess, "Popen") as popen,
            tempfile.TemporaryDirectory() as run,
            self.assertRaisesRegex(TimeoutError, "deadline expired"),
        ):
            client.spawn_broker(Path(run), "node", deadline=0.05)
        scope.assert_called_once_with(mock.ANY, deadline=0.05)
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
