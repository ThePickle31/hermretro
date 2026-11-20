"""Where the clean install and update checks put their throwaway folder (tools/ci/clean_install_check.py
work_parent): HERMRETRO_CLEAN_INSTALL_TMP, else TMPDIR, else /tmp, never inside the real Hermes home."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ci"))

import clean_install_check  # noqa: E402 - tools/ci goes on sys.path first

REAL = Path("/nonexistent-home/.hermes")


class WorkParent(unittest.TestCase):
    def parent(self, **env):
        return clean_install_check.work_parent(env, REAL)

    def test_tmpdir_is_used_when_short_and_the_own_variable_comes_first(self):
        self.assertEqual(self.parent(), Path("/tmp"))
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp, tempfile.TemporaryDirectory(dir="/tmp") as own:
            short = Path(tmp).resolve()
            self.assertEqual(self.parent(TMPDIR=tmp), short)
            self.assertEqual(self.parent(TMPDIR=tmp, HERMRETRO_CLEAN_INSTALL_TMP=own), Path(own).resolve())

    def test_a_tmpdir_inside_the_real_home_or_too_long_is_passed_over(self):
        self.assertEqual(self.parent(TMPDIR=str(REAL / "cache" / "scratch")), Path("/tmp"))
        self.assertEqual(self.parent(TMPDIR="/tmp/" + "x" * 60), Path("/tmp"))

    def test_the_own_variable_inside_the_real_home_or_too_long_is_refused_with_a_fix(self):
        for value in (str(REAL / "scratch"), "/tmp/" + "x" * 60):
            with self.assertRaises(ValueError) as raised:
                self.parent(HERMRETRO_CLEAN_INSTALL_TMP=value)
            self.assertIn("FIX:", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
