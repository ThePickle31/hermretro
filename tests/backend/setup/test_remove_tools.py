"""Setup's "Remove downloaded tools": deletes only hermretro's download folder, never games or anything else."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tests/, for support

from backend.hermes import host as hermes_host  # noqa: E402
from backend.setup import rpcs as host_setup  # noqa: E402
from backend.system import paths  # noqa: E402
from backend.setup import provision  # noqa: E402
from backend.setup import rpcs as setup_rpcs  # noqa: E402

CLEAN = {k: v for k, v in os.environ.items() if k not in ("HERMRETRO_DEPS_ROOT", "GB_STUDIO_SETUP_ROOT")}


class RemoveDownloads(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve() / "hr"
        self.cache = self.home / ".cache"
        (self.cache / "toolchain" / "bin").mkdir(parents=True)
        (self.cache / "toolchain" / "bin" / "gbdk").write_bytes(b"x" * 1000)
        (self.cache / f"engine-{paths.ENGINE_VERSION}").mkdir()
        (self.cache / "device-cli.json").write_text("{}")
        (self.home / "games" / "Frog").mkdir(parents=True)
        (self.home / "games" / "Frog" / "frog.gbsproj").write_text("{}")
        (self.home / "library").mkdir()
        self.env = mock.patch.dict(os.environ, {**CLEAN, "HERMRETRO_HOME": str(self.home)}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.deps = mock.patch.object(paths, "DEPS_ROOT", self.cache)
        self.deps.start()
        self.addCleanup(self.deps.stop)

    def test_it_empties_the_download_folder_and_keeps_games_and_library(self):
        answer = provision.remove_downloads()
        self.assertTrue(answer["ok"])
        self.assertGreaterEqual(answer["removed_bytes"], 1000)
        self.assertEqual([p.name for p in self.cache.iterdir() if p.name != ".provision.lock"], [])
        self.assertTrue((self.home / "games" / "Frog" / "frog.gbsproj").is_file())
        self.assertTrue((self.home / "library").is_dir())
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), [".cache", "games", "library"])

    def test_a_folder_the_user_configured_is_never_deleted(self):
        for variable in ("HERMRETRO_DEPS_ROOT", "GB_STUDIO_SETUP_ROOT"):
            with mock.patch.dict(os.environ, {variable: str(self.cache)}):
                with self.assertRaises(provision.ProvisionError) as caught:
                    provision.remove_downloads()
            self.assertEqual(caught.exception.code, "CUSTOM_LOCATION")
        self.assertTrue((self.cache / "toolchain" / "bin" / "gbdk").is_file())

    def test_anything_but_the_hermretro_cache_is_refused(self):
        with mock.patch.object(paths, "DEPS_ROOT", self.home / "games"):
            with self.assertRaises(provision.ProvisionError) as caught:
                provision.remove_downloads()
        self.assertEqual(caught.exception.code, "UNEXPECTED_LOCATION")
        self.assertTrue((self.home / "games" / "Frog").is_dir())

    def test_links_inside_are_removed_not_followed_and_an_earlier_failed_run_is_finished(self):
        (self.cache / "games-link").symlink_to(self.home / "games")
        stale = self.cache / ".removing-old"
        (stale / "x").mkdir(parents=True)
        (stale / "x" / "f").write_bytes(b"y" * 10)
        os.chmod(stale / "x", 0o500)  # read-only, as extracted archives can be
        answer = provision.remove_downloads()
        self.assertTrue(answer["ok"], answer)
        self.assertEqual([p.name for p in self.cache.iterdir()], [".provision.lock"])
        self.assertTrue((self.home / "games" / "Frog" / "frog.gbsproj").is_file())

    def test_a_cache_folder_that_is_a_link_is_refused(self):
        elsewhere = self.home / "elsewhere"
        os.replace(self.cache, elsewhere)
        self.cache.symlink_to(elsewhere)
        with self.assertRaises(provision.ProvisionError) as caught:
            provision.remove_downloads()
        self.assertEqual(caught.exception.code, "UNEXPECTED_LOCATION")
        self.assertTrue((elsewhere / "toolchain" / "bin" / "gbdk").is_file())

    def test_nothing_is_deleted_while_a_broker_still_holds_its_lock(self):
        import fcntl

        run = self.home / "run"
        run.mkdir()
        with open(run / "broker.lock", "a+") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            with (
                mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None)),
                mock.patch.object(paths, "runtime_dir", lambda: run),
                mock.patch.object(host_setup, "BROKER_STOP_WAIT", 0.3),
            ):
                answer = setup_rpcs.rpc_remove_tools(None)({})
        self.assertEqual((answer["ok"], answer["code"]), (False, "BUSY"))
        self.assertTrue((self.cache / "toolchain" / "bin" / "gbdk").is_file())

    def test_the_rpc_stops_an_idle_broker_first_and_refuses_a_busy_one(self):
        class Client:
            hello = {"pid": -1}

            def __init__(self, answer):
                self.answer, self.asked = answer, []

            def request(self, payload):
                self.asked.append(payload)
                return self.answer

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        (self.home / "run").mkdir()
        rpc = setup_rpcs.rpc_remove_tools(None)
        busy = Client({"ok": False, "denied": {"code": "BUSY"}})
        with (
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (busy, None)),
            mock.patch.object(paths, "runtime_dir", lambda: self.home / "run"),
        ):
            answer = rpc({})
        self.assertEqual((answer["ok"], answer["code"]), (False, "BUSY"))
        self.assertEqual(busy.asked, [{"op": "shutdown"}])  # never forced
        self.assertTrue((self.cache / "toolchain").is_dir())
        idle = Client({"ok": True})
        with (
            mock.patch.object(hermes_host, "try_connect", lambda _dir: (idle, None)),
            mock.patch.object(paths, "runtime_dir", lambda: self.home / "run"),
        ):
            answer = rpc({})
        self.assertTrue(answer["ok"])
        self.assertFalse((self.cache / "toolchain").exists())


if __name__ == "__main__":
    unittest.main()
