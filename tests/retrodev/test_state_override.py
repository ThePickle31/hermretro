"""A RETRODEV_STATE_DIR left set (leaked from another shell or agent) is named by status and doctor.

These tests change the process environment, so this module runs alone: after the package's pool, never during it.
Run alone: python -m unittest tests.retrodev.test_state_override
"""

import os
import unittest
from unittest import mock

from tests.retrodev.fixture import RepoCase, alone

load_tests = alone


class Override(RepoCase):
    def test_status_and_doctor_name_the_override(self):
        elsewhere = self.base / "elsewhere"
        for command in ("status", "doctor"):
            code, out = self.run_cli(command)
            self.assertNotIn("RETRODEV_STATE_DIR", out, command)
            with mock.patch.dict(os.environ, {"RETRODEV_STATE_DIR": str(elsewhere)}):
                code, out = self.run_cli(command)
                code, data = self.run_cli(command, as_json=True)
            self.assertIn(f"warning: RETRODEV_STATE_DIR={elsewhere} moves retrodev's records", out, command)
            self.assertIn("unset RETRODEV_STATE_DIR", out, command)
            self.assertEqual(data["state_override"], str(elsewhere), command)


if __name__ == "__main__":
    unittest.main()
