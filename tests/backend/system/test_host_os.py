"""Linux and macOS behave the same; Windows is refused cleanly. CI runs these on Linux and on macOS
(Apple Silicon and Intel), so each system's own branch is exercised for real."""

import importlib.util
import os
import shutil
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first
from backend.system import host as host_os  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

POSIX = host_os.LINUX or host_os.MACOS


class HostOs(unittest.TestCase):
    @unittest.skipUnless(POSIX, "Linux and macOS only")
    def test_the_kernel_names_the_peer_of_a_unix_socket(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        with left, right:
            pid, uid = host_os.peer_credentials(left)
        self.assertEqual(uid, os.getuid())
        self.assertEqual(pid, os.getpid())

    def test_a_short_trusted_temp_parent_needs_no_replacement(self):
        with tempfile.TemporaryDirectory(prefix="hr-", dir="/tmp") as base:
            self.assertIsNone(host_os.engine_tempdir({"TMPDIR": str(Path(base).resolve())}))

    def test_a_short_symlink_to_a_deep_temp_parent_gets_a_private_replacement(self):
        with tempfile.TemporaryDirectory(prefix="hr-", dir="/tmp") as base:
            parent = Path(base).resolve()
            deep = parent / ("x" * 120)
            deep.mkdir()
            link = parent / "short"
            link.symlink_to(deep, target_is_directory=True)
            replacement = host_os.engine_tempdir({"TMPDIR": str(link)})
            assert replacement is not None
            with replacement as directory:
                path = Path(directory)
                self.assertEqual(path, path.resolve())
                self.assertEqual(path.parent, Path("/tmp").resolve())
                self.assertTrue(path.name.startswith(f"hrt-{os.getpid()}-"), "named for the broker that owns it")
                self.assertLessEqual(len(os.fsencode(path)), 64)
                self.assertEqual(path.stat().st_uid, os.getuid())
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertFalse(path.exists())
            self.assertTrue(link.is_symlink())
            self.assertTrue(deep.is_dir())

    def test_an_owner_only_folder_under_a_replaceable_ancestor_is_never_a_fallback(self):
        # Another user who can write the non-sticky ancestor could rename the private folder away and put their
        # own in its place after a worker was given its name.
        with tempfile.TemporaryDirectory(prefix="hr-", dir="/tmp") as base:
            shared = Path(base).resolve() / "shared"
            shared.mkdir()
            shared.chmod(0o777)  # writable by everyone, no sticky bit
            leaf = shared / "run"
            leaf.mkdir(mode=0o700)
            deep = Path(base).resolve() / ("x" * 120)
            deep.mkdir()
            self.assertEqual(leaf.stat().st_mode & 0o777, 0o700, "the leaf alone looks private")
            self.assertIsNone(host_os._short_temp_parent(str(leaf)))
            replacement = host_os.engine_tempdir({"TMPDIR": str(deep), "XDG_RUNTIME_DIR": str(leaf)})
            assert replacement is not None
            with replacement as directory:
                self.assertEqual(Path(directory).parent, Path("/tmp").resolve(), "the environment's folder was used")
            with mock.patch.object(host_os, "SYSTEM_TEMP", str(leaf)):
                self.assertFalse(host_os.engine_temp_ready({"TMPDIR": str(deep)}))
                with self.assertRaises(OSError):
                    host_os.engine_tempdir({"TMPDIR": str(deep)})
            self.assertEqual(list(leaf.iterdir()), [])

    def test_temp_unavailable_reports_the_fix(self):
        with mock.patch.object(host_os, "_short_temp_parent", return_value=None):
            with self.assertRaisesRegex(OSError, "short, writable temporary directory.*TMPDIR"):
                host_os.engine_tempdir({"TMPDIR": "/does-not-exist"})

    def test_inherited_temp_does_not_keep_a_parent_or_alias_that_others_can_replace(self):
        with tempfile.TemporaryDirectory(prefix="hr-", dir="/tmp") as base:
            root = Path(base).resolve()
            shared = root / "shared"
            shared.mkdir()
            shared.chmod(0o777)
            leaf = shared / "leaf"
            leaf.mkdir(mode=0o700)
            stable = root / "stable"
            stable.mkdir(mode=0o700)
            link = shared / "link"
            link.symlink_to(stable, target_is_directory=True)
            for inherited in (leaf, link):
                with self.subTest(inherited=inherited):
                    replacement = host_os.engine_tempdir({"TMPDIR": str(inherited)})
                    assert replacement is not None, "the worker should not inherit a replaceable path"
                    with replacement as directory:
                        self.assertEqual(Path(directory).parent, Path("/tmp").resolve())

    def test_linux_and_macos_are_supported_and_windows_is_not(self):
        for name in ("linux", "darwin"):
            with (
                mock.patch.object(host_os, "LINUX", name == "linux"),
                mock.patch.object(host_os, "MACOS", name == "darwin"),
            ):
                self.assertIsNone(host_os.unsupported_reason())
        with (
            mock.patch.object(host_os, "LINUX", False),
            mock.patch.object(host_os, "MACOS", False),
            mock.patch.object(host_os.sys, "platform", "win32"),
        ):
            self.assertIn("Windows is not supported", host_os.unsupported_reason() or "")

    def test_the_cli_download_matches_the_nodejs_that_runs_it(self):
        from backend.setup import provision

        with (
            mock.patch.object(provision, "_node_platform", return_value=("darwin", "x64")),
            mock.patch.object(host_os, "native_arch", return_value="arm64"),
        ):
            self.assertEqual(provision.host_target()["target"], "darwin-x64")
        with mock.patch.object(provision, "_node_platform", return_value=("darwin", "arm64")):
            self.assertEqual(provision.host_target()["target"], "darwin-arm64")

    def test_architecture_is_the_computers_own_even_under_rosetta(self):
        self.assertIn(host_os.native_arch(), ("arm64", "x64"))
        with (
            mock.patch.object(host_os.platform, "machine", return_value="x86_64"),
            mock.patch.object(host_os, "MACOS", True),
            mock.patch.object(host_os, "rosetta", return_value=True),
        ):
            self.assertEqual(host_os.native_arch(), "arm64")
        with (
            mock.patch.object(host_os.platform, "machine", return_value="x86_64"),
            mock.patch.object(host_os, "MACOS", False),
        ):
            self.assertEqual(host_os.native_arch(), "x64")

    def test_windows_gets_one_sentence_from_register_and_imports_nothing(self):
        spec = importlib.util.spec_from_file_location(
            "hermretro_on_windows", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        with (
            mock.patch.object(host_os, "LINUX", False),
            mock.patch.object(host_os, "MACOS", False),
            mock.patch.object(host_os.sys, "platform", "win32"),
            mock.patch.dict(sys.modules, {"hermretro_on_windows.backend.system.host": host_os}),
        ):
            spec.loader.exec_module(module)
        self.assertNotIn("hermretro_on_windows.backend.hermes.host", sys.modules)
        with self.assertRaises(RuntimeError) as caught:
            module.register(object())
        self.assertIn("Linux and macOS", str(caught.exception))


@unittest.skipUnless(POSIX, "Linux and macOS only")
class RealBroker(unittest.TestCase):
    """Starts the real broker (no engine work) and completes its handshake: the peer check, the private run
    folder and the socket path must all work on this system."""

    def test_a_broker_starts_answers_and_stops(self):
        if not paths.find_node().get("ok"):
            self.skipTest("Node.js 22 or newer is not installed")
        base = Path(tempfile.mkdtemp(prefix="hr-", dir="/tmp"))  # short: socket paths are capped
        self.addCleanup(shutil.rmtree, base, True)
        state = base / "run"
        with mock.patch.dict(
            os.environ, {"HERMRETRO_HOME": str(base / "home"), "HERMRETRO_BROKER_IDLE_SECONDS": "5"}
        ):  # a leaked one exits soon
            broker = client.ensure_broker(state, wait=30)
        try:
            self.assertTrue(broker.hello.get("ok"), broker.hello)
            self.assertEqual(os.path.realpath(broker.hello["plugin_root"]), os.path.realpath(paths.PLUGIN_ROOT))
            self.assertEqual(state.stat().st_mode & 0o777, 0o700)
            self.assertEqual((state / "broker.sock").stat().st_mode & 0o777, 0o600)
            pid = broker.hello["pid"]
        finally:
            try:
                broker.request({"op": "shutdown", "force": True})
            finally:
                broker.close()
        for _ in range(100):
            try:  # this test started it, so reap it (an exited child stays visible until reaped)
                if os.waitpid(pid, os.WNOHANG)[0] == pid:
                    break
            except ChildProcessError:  # not ours to reap: another process started it
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
            time.sleep(0.1)
        else:
            self.fail(f"broker {pid} did not stop")
        self.assertFalse((state / "broker.sock").exists())


if __name__ == "__main__":
    unittest.main()
