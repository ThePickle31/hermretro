"""tools/check.py's acceptance run hands its suite, which runs from the checkout root, the toolchain folders this
process resolved from the caller's folder, never the relative text; with none named, the development toolchain when
there is one."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check  # noqa: E402 - tools/check.py is imported from its own folder
import dev_toolchain  # noqa: E402 - check puts tools/py/ on sys.path
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first


class AcceptanceEnvironment(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        for name in ("HERMRETRO_DEPS_ROOT", "GB_STUDIO_SETUP_ROOT"):
            os.environ.pop(name, None)
        self.dev = self.home.base / "dev-deps"
        patch = mock.patch.object(dev_toolchain, "DEPS_ROOT", self.dev)
        patch.start()
        self.addCleanup(patch.stop)

    def test_relative_toolchain_folders_reach_the_suite_absolute(self):
        resolved = self.home.base / "deps"
        environ = {"HERMRETRO_DEPS_ROOT": "deps", "GB_STUDIO_SETUP_ROOT": "setup/toolchain"}
        with mock.patch.dict(os.environ, environ), mock.patch.object(paths, "DEPS_ROOT", resolved):
            env, toolchain = check.acceptance_env(paths)
        self.assertEqual(env["HERMRETRO_DEPS_ROOT"], str(resolved))
        self.assertEqual(env["GB_STUDIO_SETUP_ROOT"], str(Path("setup/toolchain").absolute()))
        self.assertEqual(toolchain, Path("setup/toolchain"))
        self.assertEqual(env["TMPDIR"], check.short_tmp())

    def test_with_none_named_and_no_development_toolchain_the_installed_one_is_used(self):
        env, toolchain = check.acceptance_env(paths)
        self.assertNotIn("HERMRETRO_DEPS_ROOT", env)
        self.assertNotIn("GB_STUDIO_SETUP_ROOT", env)
        self.assertEqual(toolchain, paths.setup_root())

    def test_with_none_named_the_development_toolchain_wins_when_there_is_one(self):
        (self.dev / "toolchain").mkdir(parents=True)
        env, toolchain = check.acceptance_env(paths)
        self.assertEqual(env["HERMRETRO_DEPS_ROOT"], str(self.dev))
        self.assertEqual(toolchain, self.dev / "toolchain")

    def test_a_named_folder_wins_over_the_development_toolchain(self):
        (self.dev / "toolchain").mkdir(parents=True)
        with mock.patch.dict(os.environ, {"GB_STUDIO_SETUP_ROOT": "setup/toolchain"}):
            env, toolchain = check.acceptance_env(paths)
        self.assertNotIn("HERMRETRO_DEPS_ROOT", env)
        self.assertEqual(toolchain, Path("setup/toolchain"))


if __name__ == "__main__":
    unittest.main()
