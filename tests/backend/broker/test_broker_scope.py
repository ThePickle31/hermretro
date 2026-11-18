"""The broker starts in its own systemd scope only where that is proven to work (backend/broker/client.py)."""

import os
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
