"""tools/check.py's acceptance run hands its suite, which runs from the checkout root, the toolchain folders this
process resolved from the caller's folder, never the relative text."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check  # noqa: E402 - tools/check.py is imported from its own folder
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first


class AcceptanceEnvironment(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        for name in ("HERMRETRO_DEPS_ROOT", "GB_STUDIO_SETUP_ROOT"):
            os.environ.pop(name, None)

    def test_relative_toolchain_folders_reach_the_suite_absolute(self):
        resolved = self.home.base / "deps"
        environ = {"HERMRETRO_DEPS_ROOT": "deps", "GB_STUDIO_SETUP_ROOT": "setup/toolchain"}
        with mock.patch.dict(os.environ, environ), mock.patch.object(paths, "DEPS_ROOT", resolved):
            env = check.acceptance_env(paths)
        self.assertEqual(env["HERMRETRO_DEPS_ROOT"], str(resolved))
        self.assertEqual(env["GB_STUDIO_SETUP_ROOT"], str(Path("setup/toolchain").absolute()))
        self.assertEqual(env["TMPDIR"], check.short_tmp())

    def test_unset_folders_stay_unset(self):
        env = check.acceptance_env(paths)
        self.assertNotIn("HERMRETRO_DEPS_ROOT", env)
        self.assertNotIn("GB_STUDIO_SETUP_ROOT", env)


if __name__ == "__main__":
    unittest.main()
