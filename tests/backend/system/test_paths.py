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


class WriteJsonAtomic(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)

    def test_writes_replaces_and_leaves_no_temp_file(self):
        path = self.folder / "state.json"
        paths.write_json_atomic(path, {"a": 1})
        paths.write_json_atomic(path, {"a": 2, "b": [1]})
        self.assertEqual(path.read_text(encoding="utf-8"), json.dumps({"a": 2, "b": [1]}, indent=2) + "\n")
        self.assertEqual([p.name for p in self.folder.iterdir()], ["state.json"])

    def test_a_failed_write_keeps_the_old_file_whole(self):
        path = self.folder / "state.json"
        paths.write_json_atomic(path, {"a": 1})
        with self.assertRaises(TypeError):
            paths.write_json_atomic(path, {"a": object()})
        with mock.patch.object(os, "replace", side_effect=OSError("disk")), self.assertRaises(OSError):
            paths.write_json_atomic(path, {"a": 3})
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1})
        self.assertEqual([p.name for p in self.folder.iterdir()], ["state.json"], "the temp file is removed")


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


class NodeDiscovery(unittest.TestCase):
    def test_custom_hermes_home_detects_node_installed_or_replaced_while_the_app_is_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "custom-hermes"
            node = root / "tools" / "node-24.1.0-platform" / "bin" / "node"
            env = {
                "HOME": tmp,
                "HERMES_HOME": str(root / "profiles" / "hermretro"),
                "PATH": "",
                "GB_STUDIO_SETUP_ROOT": str(base / "setup"),
            }
            real_stamp = paths._node_stamp
            with (
                mock.patch.dict(os.environ, env, clear=True),
                mock.patch.object(paths.hermes_home, "asked", return_value=None),
                mock.patch.object(
                    paths, "_node_stamp", side_effect=lambda p: real_stamp(p) if p == str(node) else None
                ),
                mock.patch.object(paths, "_node_version", wraps=paths._node_version) as probe,
            ):
                self.assertFalse(paths.find_node()["ok"])
                node.parent.mkdir(parents=True)
                node.write_text("#!/bin/sh\necho v24.1.0\n")
                node.chmod(0o755)
                first = paths.find_node()
                self.assertEqual((first["path"], first["version"], first["ok"]), (str(node), "24.1.0", True))
                self.assertEqual(paths.find_node(), first)
                self.assertEqual(probe.call_count, 1, "polling does not run another version probe")
                replacement = node.with_name("new-node")
                replacement.write_text("#!/bin/sh\necho v25.9.1\n")
                replacement.chmod(0o755)
                replacement.replace(node)
                self.assertEqual(paths.find_node()["version"], "25.9.1")
                self.assertEqual(probe.call_count, 2)

    def test_a_failed_candidate_before_a_working_one_is_not_probed_on_every_lookup(self):
        self.addCleanup(paths._failed_probes.clear)
        with tempfile.TemporaryDirectory() as tmp:
            stalled, working = Path(tmp) / "shim" / "node", Path(tmp) / "bin" / "node"
            for node, version in ((stalled, "stalls"), (working, "v24.1.0")):
                node.parent.mkdir()
                node.write_text(f"#!/bin/sh\necho {version}\n")
                node.chmod(0o755)
            probed: list[str] = []

            def probe(path):  # the stalled shim times out after 10 s in real life
                probed.append(path)
                return (24, 1, 0) if path == str(working) else None

            real_stamp = paths._node_stamp
            with (
                mock.patch.dict(os.environ, {"HERMRETRO_NODE": str(stalled), "PATH": str(working.parent), "HOME": tmp}),
                mock.patch.object(
                    paths,
                    "_node_stamp",
                    side_effect=lambda p: real_stamp(p) if p in (str(stalled), str(working)) else None,
                ),
                mock.patch.object(paths, "_node_version", side_effect=probe),
            ):
                for _ in range(3):
                    self.assertEqual(paths.find_node()["path"], str(working))
                self.assertEqual(probed.count(str(stalled)), 1, "the failed candidate was probed again at once")
                stalled.write_text("#!/bin/sh\necho v24.2.0 \n")  # changed: probe it now
                paths.find_node()
                self.assertEqual(probed.count(str(stalled)), 2)
                paths.find_node()
                self.assertEqual(probed.count(str(stalled)), 2)
                with mock.patch.object(paths, "PROBE_RETRY_SECONDS", 0):  # and again once the cooldown is over
                    paths.find_node()
                self.assertEqual(probed.count(str(stalled)), 3)
                self.assertEqual(probed.count(str(working)), 1, "the working one stays cached")


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


class PreparedEngine(unittest.TestCase):
    """The per-user engine copy verifies against the bundled engine as it is now, package.json included."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.bundled, self.prepared = base / "bundled", base / "prepared"
        self.manifest, receipt = base / "manifest.json", base / "receipt.json"
        for name, value in (
            ("ENGINE_ROOT", self.bundled),
            ("PREPARED_ENGINE", self.prepared),
            ("ENGINE_MANIFEST", self.manifest),
            ("DEVICE_CLI_RECEIPT", receipt),
        ):
            patcher = mock.patch.object(paths, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.release('{"name": "modretro-chromatic", "bundledChromaticFormat": "packed"}')
        receipt.write_text(json.dumps({"engine_version": paths.ENGINE_VERSION, "target": "linux-x64", "added": {}}))

    def release(self, package: str) -> None:
        """Ship a bundled engine with this package.json and prepare the copy from it, as provisioning does."""
        self.bundled.mkdir(exist_ok=True)
        (self.bundled / "package.json").write_text(package)
        digest = paths._file_sha256(self.bundled / "package.json")
        self.manifest.write_text(json.dumps({"entries": [{"path": "package.json", "sha256": digest}]}))
        self.prepared.mkdir(exist_ok=True)
        (self.prepared / "package.json").write_bytes(paths.prepared_package_json("linux-x64"))

    def test_the_copy_prepared_from_the_bundled_engine_verifies(self):
        self.assertEqual(paths.verify_prepared_engine(), {"present": True, "verified": True, "detail": ""})

    def test_an_edited_package_json_retires_the_old_copy(self):
        prepared_before = (self.prepared / "package.json").read_bytes()
        self.release('{"name": "modretro-chromatic", "edited": true}')
        (self.prepared / "package.json").write_bytes(prepared_before)
        self.assertEqual(paths.verify_prepared_engine()["detail"], "changed package.json")


class EngineEntries(unittest.TestCase):
    """The engine's files as its manifest and verification see them: Python's bytecode left out by name, links never."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for rel in (
            "package.json",
            "scripts/worker.py",
            "scripts/__pycache__/worker.cpython-314.pyc",
            "scripts/old.pyc",
        ):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(rel)
        self.expected = {rel: paths._file_sha256(self.root / rel) for rel in ("package.json", "scripts/worker.py")}

    def listed(self) -> list[str]:
        return [path.relative_to(self.root).as_posix() for path in paths.engine_entries(self.root)]

    def test_bytecode_is_left_out_and_never_stated(self):
        # A running script renames its bytecode into place: a .pyc listed and then stat'ed could be gone.
        def refusing_bytecode(real):
            def call(path, *args, **kwargs):
                if "__pycache__" in path.parts or path.name.endswith(".pyc"):
                    raise FileNotFoundError(path)
                return real(path, *args, **kwargs)

            return call

        with (
            mock.patch.object(Path, "lstat", refusing_bytecode(Path.lstat)),
            mock.patch.object(Path, "stat", refusing_bytecode(Path.stat)),
        ):
            self.assertEqual(self.listed(), ["package.json", "scripts/worker.py"])
            self.assertEqual(paths._compare_tree(self.root, self.expected), [])

    def test_the_engines_record_is_left_out_of_an_engine_folder_and_not_of_a_copy(self):
        (self.root / "contract").mkdir()
        (self.root / "contract" / "manifest.json").write_text("{}")
        self.assertEqual(self.listed(), ["package.json", "scripts/worker.py"])
        self.assertEqual(paths._compare_tree(self.root, self.expected), [])
        # A prepared copy holds no record, so one there is a file it should not have.
        self.assertEqual(
            paths._compare_tree(self.root, self.expected, engine_folder=False),
            ["unexpected file contract/manifest.json"],
        )

    def test_a_loaded_file_that_an_update_moved_still_gives_a_fingerprint(self):
        before = paths.code_fingerprint()
        with mock.patch.object(paths, "LOADED_FILES", (*paths.LOADED_FILES, "engine/contract/moved.json")):
            moved = paths.code_fingerprint()
        self.assertNotEqual(moved, before)

    def test_a_loaded_file_that_goes_between_its_stamp_and_its_read_is_stamped_again(self):
        gone = paths.PLUGIN_ROOT / "engine" / "contract" / "tools.json"
        real_stamp, real_read = paths._file_stamp, Path.read_bytes
        stamped = []

        def stamp(path):
            if path != gone:
                return real_stamp(path)
            stamped.append(path)
            return (1, 1) if len(stamped) == 1 else (-1, -1)  # there when first stamped, gone after

        def read(path):
            if path.name == gone.name:
                raise FileNotFoundError(path)
            return real_read(path)

        with mock.patch.object(paths, "_file_stamp", stamp), mock.patch.object(Path, "read_bytes", read):
            self.assertIsInstance(paths.code_fingerprint(), str)
        self.assertEqual(len(stamped), 2)

    def test_a_link_is_listed_and_refused_whatever_its_name(self):
        (self.root / "scripts" / "gone.pyc").symlink_to(self.root / "nowhere.pyc")
        (self.root / "scripts" / "linked").symlink_to(self.root / "scripts", target_is_directory=True)
        self.assertEqual(self.listed(), ["package.json", "scripts/gone.pyc", "scripts/linked", "scripts/worker.py"])
        self.assertEqual(
            paths._compare_tree(self.root, self.expected),
            ["unexpected symlink scripts/gone.pyc", "unexpected symlink scripts/linked"],
        )


if __name__ == "__main__":
    unittest.main()
