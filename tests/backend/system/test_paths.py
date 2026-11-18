"""Where hermretro keeps things: one folder in the Hermes home, shared by every profile."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

CLEAN = {
    key: value
    for key, value in os.environ.items()
    if not key.startswith("HERMRETRO_") and key not in ("HERMES_HOME", "GB_STUDIO_SETUP_ROOT")
}


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
        with (
            mock.patch.dict(sys.modules, no_hermes),
            mock.patch.dict(os.environ, {**CLEAN, "HERMES_HOME": str(hermes / "profiles" / "hermretro")}, clear=True),
        ):
            self.assertEqual(paths.hermretro_home(), hermes / "hermretro")
        with (
            mock.patch.dict(sys.modules, no_hermes),
            mock.patch.dict(os.environ, {**CLEAN, "HERMES_HOME": str(hermes)}, clear=True),
        ):
            self.assertEqual(paths.hermretro_home(), hermes / "hermretro")
        with (
            mock.patch.dict(sys.modules, no_hermes),
            mock.patch.dict(os.environ, CLEAN, clear=True),
            mock.patch.object(Path, "home", return_value=self.base),
        ):
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
        with (
            mock.patch.dict(os.environ, CLEAN, clear=True),
            mock.patch.object(paths, "hermretro_home", return_value=Path(expected)),
            mock.patch.object(client, "own_scope", return_value=[]),
            mock.patch.object(client.subprocess, "Popen") as popen,
        ):
            client.spawn_broker(state, "node")
        self.assertEqual(popen.call_args.kwargs["env"]["HERMRETRO_HOME"], expected)


class HermesHomeHandOver(unittest.TestCase):
    """backend.system never imports Hermes: the Hermes layer hands over how to ask (system/hermes_home.py).
    Where hermretro's home resolves must not change: Hermes's answer when the plugin runs inside Hermes,
    HERMRETRO_HOME when set, HERMES_HOME otherwise."""

    def run_plugin(self, env: dict) -> dict:
        """Load the plugin as Hermes does, with a stand-in hermes_constants naming ``<tmp>/hroot``."""
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp).resolve()
            (fake / "hermes_constants.py").write_text(
                f"def get_default_hermes_root():\n    return {str(fake / 'hroot')!r}\n"
            )
            code = (
                "import importlib.util, json, sys; sys.path.insert(0, sys.argv[2]); "
                "spec = importlib.util.spec_from_file_location('hr', sys.argv[1] + '/__init__.py', "
                "submodule_search_locations=[sys.argv[1]]); m = importlib.util.module_from_spec(spec); "
                "sys.modules['hr'] = m; spec.loader.exec_module(m); p = sys.modules['hr.backend.system.paths']; "
                "print(json.dumps([str(p.hermretro_home()), str(p.DEPS_ROOT)]))"
            )
            done = subprocess.run(
                [sys.executable, "-c", code, str(ROOT), str(fake)],
                capture_output=True,
                text=True,
                env={"PATH": os.environ.get("PATH", ""), "HOME": tmp, **env},
                timeout=60,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            home, deps = json.loads(done.stdout)
            return {"home": home.replace(str(fake), "<fake>"), "deps": deps.replace(str(fake), "<fake>")}

    def test_inside_hermes_the_home_is_what_hermes_says(self):
        for hermes_home in ("", "/y/.hermes/profiles/p"):
            env = {"HERMES_HOME": hermes_home} if hermes_home else {}
            self.assertEqual(
                self.run_plugin(env), {"home": "<fake>/hroot/hermretro", "deps": "<fake>/hroot/hermretro/.cache"}
            )

    def test_hermretro_home_still_wins(self):
        self.assertEqual(self.run_plugin({"HERMRETRO_HOME": "/x/hh"}), {"home": "/x/hh", "deps": "/x/hh/.cache"})

    def test_the_handed_over_answer_is_used_and_none_falls_back(self):
        from backend.system import hermes_home

        saved = hermes_home._ask
        try:
            asked = Path(tempfile.gettempdir()) / "asked-hermes"
            hermes_home.provide(lambda: asked)
            with mock.patch.dict(os.environ, CLEAN, clear=True):
                self.assertEqual(paths.hermretro_home(), asked / "hermretro")
            hermes_home.provide(lambda: None)
            with mock.patch.dict(os.environ, {**CLEAN, "HERMES_HOME": "/z/.hermes"}, clear=True):
                self.assertEqual(paths.hermretro_home(), Path("/z/.hermes/hermretro"))
        finally:
            hermes_home._ask = saved

    def test_importing_the_hermes_layer_hands_it_over(self):
        import backend.hermes  # noqa: F401 - importing it is what the test checks
        from backend.hermes import api
        from backend.system import hermes_home

        self.assertIs(hermes_home._ask, api.default_hermes_root)


if __name__ == "__main__":
    unittest.main()
