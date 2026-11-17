"""Where hermretro keeps things: one folder in the Hermes home, shared by every profile."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.broker import client  # noqa: E402
from backend.system import paths  # noqa: E402

CLEAN = {key: value for key, value in os.environ.items()
         if not key.startswith("HERMRETRO_") and key not in ("HERMES_HOME", "GB_STUDIO_SETUP_ROOT")}


class HermretroHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_folder_sits_in_the_hermretro_home_and_nothing_is_created_by_asking(self):
        home = self.base / "hr"
        with mock.patch.dict(os.environ, {**CLEAN, "HERMRETRO_HOME": str(home)}, clear=True):
            self.assertEqual(paths.hermretro_home(), home)
            self.assertEqual(paths.games_dir(), home / "games")
            self.assertEqual(paths.library_dir(), home / "library")
            self.assertEqual(paths.default_runtime_dir(), home / "run")
        self.assertFalse(home.exists())
        with mock.patch.dict(os.environ, {**CLEAN, "HERMRETRO_HOME": "relative/hr"}, clear=True):
            self.assertTrue(paths.hermretro_home().is_absolute())  # the broker runs from another folder

    def test_without_an_override_it_is_the_hermes_root_even_from_a_profile(self):
        hermes = self.base / "dot-hermes"
        no_hermes = {"hermes_constants": None}  # importing it then fails, as in CI and in the broker
        with mock.patch.dict(sys.modules, no_hermes), \
                mock.patch.dict(os.environ, {**CLEAN, "HERMES_HOME": str(hermes / "profiles" / "hermretro")},
                                clear=True):
            self.assertEqual(paths.hermretro_home(), hermes / "hermretro")
        with mock.patch.dict(sys.modules, no_hermes), \
                mock.patch.dict(os.environ, {**CLEAN, "HERMES_HOME": str(hermes)}, clear=True):
            self.assertEqual(paths.hermretro_home(), hermes / "hermretro")
        with mock.patch.dict(sys.modules, no_hermes), mock.patch.dict(os.environ, CLEAN, clear=True), \
                mock.patch.object(Path, "home", return_value=self.base):
            self.assertEqual(paths.hermretro_home(), self.base / ".hermes" / "hermretro")

    def test_a_socket_path_too_long_for_macos_falls_back_to_a_short_per_user_folder(self):
        deep = self.base / ("d" * 120)
        with mock.patch.dict(os.environ, {**CLEAN, "HERMRETRO_HOME": str(deep)}, clear=True):
            folder = paths.default_runtime_dir()
        self.assertEqual(folder, Path("/tmp") / f"hermretro-{os.getuid()}")
        self.assertLessEqual(len(os.fsencode(folder / "broker.sock")), paths.SOCKET_PATH_LIMIT)

    def test_the_run_folder_is_private_and_never_a_link(self):
        run = self.base / "run"
        with mock.patch.dict(os.environ, {**CLEAN, "HERMRETRO_RUNTIME_DIR": str(run)}, clear=True):
            self.assertEqual(paths.runtime_dir(), run)
            self.assertEqual(run.stat().st_mode & 0o777, 0o700)
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        (self.base / "link").symlink_to(elsewhere)
        with mock.patch.dict(os.environ, {**CLEAN, "HERMRETRO_RUNTIME_DIR": str(self.base / "link")}, clear=True):
            with self.assertRaises(PermissionError):
                paths.runtime_dir()

    def test_the_broker_is_told_where_the_hermretro_home_is(self):
        # The broker runs with a minimal environment and cannot ask Hermes, so the client passes it on.
        home = self.base / "hr"
        state = self.base / "run"
        state.mkdir()
        with mock.patch.dict(os.environ, {**CLEAN, "HERMRETRO_HOME": str(home)}, clear=True):
            expected = str(paths.hermretro_home())
        with mock.patch.dict(os.environ, CLEAN, clear=True), \
                mock.patch.object(paths, "hermretro_home", return_value=Path(expected)), \
                mock.patch.object(client, "own_scope", return_value=[]), \
                mock.patch.object(client.subprocess, "Popen") as popen:
            client.spawn_broker(state, "node")
        self.assertEqual(popen.call_args.kwargs["env"]["HERMRETRO_HOME"], expected)


if __name__ == "__main__":
    unittest.main()
