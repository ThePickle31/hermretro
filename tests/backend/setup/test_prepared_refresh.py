"""The prepared engine copy is rebuilt, with no download, when the bundled engine changed under it."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.setup import provision  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import throwaway_deps  # noqa: E402 - the repository root goes on sys.path first

EXE, NOTICE = b"cli build", b"cli notice"
PINS = {
    "version": "1.2.1",
    "package": {"name": "@modretro/chromatic-cli-x", "url": "https://registry.npmjs.org/@modretro/x", "sha256": "0"},
    "executable": {"path": "linux-x64-gnu/bin/chromatic-cli", "sha256": hashlib.sha256(EXE).hexdigest()},
    "notice": {"path": "linux-x64-gnu/NOTICE", "sha256": hashlib.sha256(NOTICE).hexdigest()},
}


class PreparedRefresh(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        deps = throwaway_deps(Path(tmp.name))
        deps.__enter__()
        self.addCleanup(deps.__exit__, None, None, None)
        for patcher in (
            mock.patch.object(provision, "host_target", return_value={"target": "linux-x64-gnu", "reason": None}),
            mock.patch.object(provision, "_pins", return_value=PINS),
            mock.patch.object(paths, "find_node", return_value={"ok": True, "path": "node"}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        provision._REFRESH_FAILED.clear()
        self.built = []
        prepare = mock.patch.object(provision, "_prepare", side_effect=self.record)
        prepare.start()
        self.addCleanup(prepare.stop)

    def record(self, *args, **dates):
        self.built.append((args, dates))

    def earlier_copy(self, version: str, executable: bytes = EXE) -> Path:
        copy = paths.DEPS_ROOT / f"engine-{version}"
        for pin, data in ((PINS["executable"], executable), (PINS["notice"], NOTICE)):
            (copy / provision.CLI_DIR / pin["path"]).parent.mkdir(parents=True, exist_ok=True)
            (copy / provision.CLI_DIR / pin["path"]).write_bytes(data)
        receipt = {
            "engine_version": version,
            "target": "linux-x64-gnu",
            "vendor_terms_accepted": True,
            "installed_at": "2026-01-01T00:00:00Z",
        }
        (paths.DEPS_ROOT / f"device-cli-{version}.json").write_text(json.dumps(receipt))
        return copy

    def test_another_versions_copy_gives_its_cli_and_is_removed(self):
        old = self.earlier_copy("0.9.0")
        self.assertTrue(provision.refresh_prepared_engine())
        ((args, dates),) = self.built
        self.assertEqual(args, ("linux-x64-gnu", PINS, EXE, NOTICE))
        self.assertEqual(dates["installed_at"], "2026-01-01T00:00:00Z")
        self.assertTrue(dates["refreshed_at"])
        self.assertFalse(old.exists())
        self.assertFalse((paths.DEPS_ROOT / "device-cli-0.9.0.json").exists())

    def test_the_same_versions_copy_is_rebuilt_in_place(self):
        copy = self.earlier_copy(paths.ENGINE_VERSION)
        self.assertEqual(copy, paths.PREPARED_ENGINE)
        self.assertTrue(provision.refresh_prepared_engine())
        self.assertEqual(len(self.built), 1)
        self.assertTrue(copy.exists(), "_prepare swaps it; refresh does not delete the current copy")

    def test_a_cli_the_engine_does_not_pin_is_not_reused(self):
        self.earlier_copy("0.9.0", executable=b"another cli build")
        self.assertFalse(provision.refresh_prepared_engine())
        self.assertEqual(self.built, [])

    def test_never_installed_asks_nothing(self):
        with mock.patch.object(provision, "host_target", side_effect=AssertionError("asked the host")):
            self.assertFalse(provision.refresh_prepared_engine())

    def test_a_failed_rebuild_is_not_tried_again(self):
        self.earlier_copy("0.9.0")
        with mock.patch.object(
            provision, "_prepare", side_effect=provision.ProvisionError("ENGINE_REFUSED", "no")
        ) as failing:
            self.assertFalse(provision.refresh_prepared_engine())
            self.assertFalse(provision.refresh_prepared_engine())
        self.assertEqual(failing.call_count, 1)
        self.assertTrue((paths.DEPS_ROOT / "engine-0.9.0").exists(), "a failed rebuild keeps the copy it read")

    def test_select_engine_chooses_again_after_a_rebuild(self):
        answers = iter(
            [
                {"root": paths.ENGINE_ROOT, "prepared": False, "check": {"verified": True}},
                {"root": paths.PREPARED_ENGINE, "prepared": True, "check": {"verified": True}},
            ]
        )
        self.earlier_copy("0.9.0")
        with mock.patch.object(paths, "select_engine", side_effect=lambda: next(answers)):
            self.assertTrue(provision.select_engine()["prepared"])

    def test_an_unverified_bundled_engine_is_never_copied(self):
        self.earlier_copy("0.9.0")
        unverified = {"root": paths.ENGINE_ROOT, "prepared": False, "check": {"verified": False}}
        with mock.patch.object(paths, "select_engine", return_value=unverified):
            self.assertFalse(provision.select_engine()["prepared"])
        self.assertEqual(self.built, [])


if __name__ == "__main__":
    unittest.main()
