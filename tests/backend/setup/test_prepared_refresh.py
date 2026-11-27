"""A new prepared engine copy is made, with no download, when the bundled engine changed under the old one."""

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.setup import copy_lease, provision  # noqa: E402 - the repository root goes on sys.path first
from backend.system import engine_tree, paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import throwaway_deps  # noqa: E402 - the repository root goes on sys.path first

EXE, NOTICE = b"cli build", b"cli notice"
TARGET = "linux-x64-gnu"


def pin(rel: str, data: bytes, mode: str) -> dict:
    return {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "mode": mode}


PINS = {
    "version": "1.2.1",
    "package": {"name": "@modretro/chromatic-cli-x", "url": "https://registry.npmjs.org/@modretro/x", "sha256": "0"},
    "executable": pin(f"{TARGET}/bin/chromatic-cli", EXE, "0755"),
    "notice": pin(f"{TARGET}/NOTICE", NOTICE, "0644"),
}


class Refresh(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        deps = throwaway_deps(self.base)
        deps.__enter__()
        self.addCleanup(deps.__exit__, None, None, None)
        paths.DEPS_ROOT.mkdir(parents=True)
        for patcher in (
            mock.patch.object(provision, "host_target", return_value={"target": TARGET, "reason": None}),
            mock.patch.object(provision, "_pins", return_value=PINS),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        provision._NOT_REUSABLE.clear()
        self.addCleanup(provision._NOT_REUSABLE.clear)

    def earlier_copy(self, name: str, executable: bytes = EXE, **receipt) -> Path:
        copy = paths.DEPS_ROOT / f"engine-{name}"
        for entry, data in ((PINS["executable"], executable), (PINS["notice"], NOTICE)):
            (copy / provision.CLI_DIR / entry["path"]).parent.mkdir(parents=True, exist_ok=True)
            (copy / provision.CLI_DIR / entry["path"]).write_bytes(data)
        fields = {
            "target": TARGET,
            "cli_version": "1.2.1",
            "vendor_terms": provision.VENDOR_TERMS_URL,
            "vendor_terms_accepted": True,
            "installed_at": "2026-01-01T00:00:00Z",
            **receipt,
        }
        (paths.DEPS_ROOT / f"device-cli-{name}.json").write_text(json.dumps(fields))
        return copy


class ChoosingTheSource(Refresh):
    """Which earlier copy may give its CLI files (the build itself stubbed)."""

    def setUp(self):
        super().setUp()
        self.built, self.verified = [], iter([False, True])
        for patcher in (
            mock.patch.object(provision, "_prepare", side_effect=self.record),
            mock.patch.object(paths, "verify_prepared_engine", side_effect=lambda: {"verified": next(self.verified)}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def record(self, *args, **dates):
        self.built.append((args, dates))

    def test_the_newest_earlier_copy_gives_its_cli_and_every_copy_stays(self):
        oldest = self.earlier_copy("1.0.33")
        source = self.earlier_copy("1.0.34")
        self.assertTrue(provision.refresh_prepared_engine("/usr/bin/node"))
        ((args, dates),) = self.built
        self.assertEqual(args, (TARGET, PINS, EXE, NOTICE))
        self.assertEqual(dates["node_path"], "/usr/bin/node")
        self.assertEqual(dates["installed_at"], "2026-01-01T00:00:00Z")
        # A worker of the running broker may still read any of them: only a starting broker removes them.
        self.assertTrue(source.exists())
        self.assertTrue(oldest.exists())
        self.assertTrue((paths.DEPS_ROOT / "device-cli-1.0.33.json").exists())

    def test_a_copy_made_meanwhile_is_not_made_again(self):
        self.earlier_copy("1.0.34")
        self.verified = iter([True])
        self.assertTrue(provision.refresh_prepared_engine())
        self.assertEqual(self.built, [])

    def test_only_a_cli_accepted_for_this_release_and_computer_is_reused(self):
        cases = {
            "1.0.30": {"executable": b"another cli build"},
            "1.0.31": {"cli_version": "1.2.0"},
            "1.0.32": {"vendor_terms": "https://example.invalid/terms"},
            "1.0.33": {"target": "darwin-arm64"},
            "1.0.34": {"vendor_terms_accepted": False},
        }
        for name, change in cases.items():
            executable = change.pop("executable", EXE)
            self.earlier_copy(name, executable, **change)
        self.assertFalse(provision.refresh_prepared_engine())
        self.assertEqual(self.built, [])

    def test_receipts_with_odd_names_or_shapes_are_ignored(self):
        self.earlier_copy("1.0.34")
        (paths.DEPS_ROOT / "device-cli-1.0.34.json").write_text("[]")
        (paths.DEPS_ROOT / "device-cli-..%2F..json").write_text("{}")
        self.assertFalse(provision.refresh_prepared_engine())
        self.assertEqual(self.built, [])

    def test_never_installed_asks_nothing(self):
        with mock.patch.object(provision, "host_target", side_effect=AssertionError("asked the host")):
            self.assertFalse(provision.refresh_prepared_engine())

    def test_a_failed_build_is_not_tried_again_and_keeps_its_source(self):
        source = self.earlier_copy("1.0.34")
        self.verified = iter([False, False])
        failing = mock.patch.object(provision, "_prepare", side_effect=provision.ProvisionError("ENGINE_REFUSED", "no"))
        with failing as build:
            self.assertFalse(provision.refresh_prepared_engine())
            self.assertFalse(provision.refresh_prepared_engine())
        self.assertEqual(build.call_count, 1)
        self.assertTrue(source.exists())

    def test_a_busy_lock_is_tried_again_later(self):
        self.earlier_copy("1.0.34")
        busy = mock.patch.object(provision, "lock", side_effect=provision.ProvisionError("BUSY", "busy"))
        with busy:
            self.assertFalse(provision.refresh_prepared_engine())
        self.assertTrue(provision.refresh_prepared_engine())

    def test_an_unverified_bundled_engine_is_never_copied(self):
        self.earlier_copy("1.0.34")
        unverified = {"root": paths.ENGINE_ROOT, "prepared": False, "check": {"verified": False}}
        with mock.patch.object(paths, "select_engine", return_value=unverified):
            self.assertFalse(provision.select_engine()["prepared"])
        self.assertEqual(self.built, [])


class Pruning(Refresh):
    """A starting broker removes the other engines' copies, once this engine's copy verifies."""

    def test_the_other_engines_copies_go_once_this_ones_verifies(self):
        older = [self.earlier_copy("1.0.33"), self.earlier_copy("1.0.34")]
        paths.PREPARED_ENGINE.mkdir()
        paths.DEVICE_CLI_RECEIPT.write_text("{}")
        with mock.patch.object(paths, "verify_prepared_engine", return_value={"verified": True}):
            self.assertEqual(provision.prune_prepared_copies(), 2)
        self.assertEqual([copy.exists() for copy in older], [False, False])
        self.assertEqual(
            sorted(p.name for p in paths.DEPS_ROOT.glob("device-cli-*.json")), [paths.DEVICE_CLI_RECEIPT.name]
        )
        self.assertTrue(paths.PREPARED_ENGINE.is_dir())

    def test_a_copy_that_does_not_all_go_keeps_its_receipt_for_the_next_try(self):
        older = self.earlier_copy("1.0.34")
        with (
            mock.patch.object(paths, "verify_prepared_engine", return_value={"verified": True}),
            mock.patch.object(provision, "remove_tree"),  # a file it could not delete
        ):
            self.assertEqual(provision.prune_prepared_copies(), 0)
        self.assertTrue(older.exists())
        self.assertTrue((paths.DEPS_ROOT / "device-cli-1.0.34.json").exists())

    def test_a_receipt_whose_copy_went_before_it_goes_too(self):
        (paths.DEPS_ROOT / "device-cli-1.0.34.json").write_text("{}")  # a removal stopped between the two
        with mock.patch.object(paths, "verify_prepared_engine", return_value={"verified": True}):
            provision.prune_prepared_copies()
        self.assertFalse((paths.DEPS_ROOT / "device-cli-1.0.34.json").exists())

    def test_nothing_goes_once_the_engine_on_disk_is_another(self):
        # This process's copy may be the older one now: a gateway may have just installed the newer.
        older = self.earlier_copy("1.0.34")
        with (
            mock.patch.object(paths, "verify_prepared_engine", return_value={"verified": True}),
            mock.patch.object(paths, "engine_identity", return_value="9.9.9-changed000000"),
        ):
            self.assertEqual(provision.prune_prepared_copies(), 0)
        self.assertTrue(older.exists())

    def test_nothing_goes_while_this_engines_copy_does_not_verify(self):
        older = self.earlier_copy("1.0.34")  # it still has to give its CLI
        with mock.patch.object(paths, "verify_prepared_engine", return_value={"verified": False}):
            self.assertEqual(provision.prune_prepared_copies(), 0)
        self.assertTrue(older.exists())

    def test_nothing_goes_while_another_setup_holds_the_lock(self):
        older = self.earlier_copy("1.0.34")
        busy = provision.ProvisionError("BUSY", "Another hermretro setup is running.")
        with (
            mock.patch.object(paths, "verify_prepared_engine", return_value={"verified": True}),
            mock.patch.object(provision, "lock", side_effect=busy),
        ):
            self.assertEqual(provision.prune_prepared_copies(), 0)
        self.assertTrue(older.exists())


class TheRealBuild(Refresh):
    """The whole path with only Node stubbed: a small bundled engine, an earlier copy, a new copy that verifies."""

    def setUp(self):
        super().setUp()
        bundled = self.base / "bundled"
        files = {
            "package.json": '{"name": "hermretro-engine", "version": "2.0.0"}',
            "dist/server.js": "edited",
            "scripts/start-mcp.mjs": "",
        }
        for rel, text in files.items():
            (bundled / rel).parent.mkdir(parents=True, exist_ok=True)
            (bundled / rel).write_text(text)
        (bundled / "scripts" / "start-mcp.mjs").chmod(0o755)  # one the engine runs
        (bundled / "assets" / "devices").mkdir(parents=True)
        self.manifest = self.base / "manifest.json"
        self.record_manifest(bundled, files)
        for patcher in (
            mock.patch.object(paths, "ENGINE_ROOT", bundled),
            mock.patch.object(paths, "ENGINE_MANIFEST", self.manifest),
            mock.patch.object(provision, "_node", return_value={}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        # This process loaded the engine above, as one started after it was bundled: its version, its identity and the
        # names of its copy and receipt.
        identity = paths.engine_identity()
        for name, value in (
            ("ENGINE_VERSION", "2.0.0"),
            ("ENGINE_IDENTITY", identity),
            ("PREPARED_ENGINE", paths.DEPS_ROOT / f"engine-{identity}"),
            ("DEVICE_CLI_RECEIPT", paths.DEPS_ROOT / f"device-cli-{identity}.json"),
        ):
            patcher = mock.patch.object(paths, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        paths.verify_engine.cache_clear()
        self.addCleanup(paths.verify_engine.cache_clear)

    def record_manifest(self, bundled: Path, files) -> None:
        """The bundled engine's manifest, as tools/engine/manifest.py writes one: its entries and their digest."""
        entries = [
            {
                "path": rel,
                "type": "file",
                "mode": oct(stat.S_IMODE((bundled / rel).stat().st_mode)),
                "sha256": hashlib.sha256((bundled / rel).read_bytes()).hexdigest(),
            }
            for rel in files
        ]
        self.manifest.write_text(
            json.dumps({"entries": entries, "aggregate_sha256": engine_tree.manifest_digest(entries)})
        )

    def assert_waits_for_the_restart(self):
        self.assertFalse(provision.refresh_prepared_engine("/usr/bin/node"))
        self.assertFalse(paths.PREPARED_ENGINE.exists(), "a copy named for the loaded engine, made from another")
        self.assertEqual(list(paths.DEPS_ROOT.glob("engine.*")), [], "no staging left")
        with self.assertRaises(provision.ProvisionError) as raised:
            provision._prepare(TARGET, PINS, EXE, NOTICE)
        self.assertEqual(raised.exception.code, "ENGINE_CHANGED")
        # Nothing was marked unusable: once Hermes restarts, the same earlier copy gives its CLI.
        self.assertEqual(provision._NOT_REUSABLE, set())

    def test_a_new_engine_version_waits_for_the_restart(self):
        self.earlier_copy("1.0.33")
        (paths.ENGINE_ROOT / "package.json").write_text('{"name": "hermretro-engine", "version": "2.0.1"}')
        self.record_manifest(paths.ENGINE_ROOT, ["package.json", "dist/server.js", "scripts/start-mcp.mjs"])
        self.assert_waits_for_the_restart()

    def test_a_rewritten_manifest_alone_waits_for_the_restart(self):
        self.earlier_copy("1.0.33")
        (paths.ENGINE_ROOT / "dist" / "server.js").write_text("rebuilt")
        self.record_manifest(paths.ENGINE_ROOT, ["package.json", "dist/server.js", "scripts/start-mcp.mjs"])
        self.assert_waits_for_the_restart()

    def test_entries_rewritten_under_the_old_digest_publish_nothing(self):
        # A manifest merged by hand: new entries, the digest (and so the identity) of the old ones.
        self.earlier_copy("1.0.33")
        old = json.loads(self.manifest.read_text())["aggregate_sha256"]
        (paths.ENGINE_ROOT / "dist" / "server.js").write_text("rebuilt")
        self.record_manifest(paths.ENGINE_ROOT, ["package.json", "dist/server.js", "scripts/start-mcp.mjs"])
        manifest = json.loads(self.manifest.read_text())
        self.manifest.write_text(json.dumps({**manifest, "aggregate_sha256": old}))
        self.assertFalse(provision.refresh_prepared_engine("/usr/bin/node"))
        self.assertFalse(paths.PREPARED_ENGINE.exists())

    def test_a_version_read_before_an_update_and_its_manifest_after_publish_nothing(self):
        # Loaded across an update: the old package.json, then the new manifest. The identity names the old version.
        self.earlier_copy("1.0.33")
        manifest = json.loads(self.manifest.read_text())
        with (
            mock.patch.object(paths, "ENGINE_VERSION", "1.9.9"),
            mock.patch.object(paths, "ENGINE_IDENTITY", paths._identity("1.9.9", manifest)),
        ):
            self.assertFalse(provision.refresh_prepared_engine("/usr/bin/node"))
            with self.assertRaises(provision.ProvisionError) as raised:
                provision._prepare(TARGET, PINS, EXE, NOTICE)
        self.assertEqual(raised.exception.code, "ENGINE_CHANGED")
        self.assertEqual(provision._NOT_REUSABLE, set())

    def test_an_engine_rebuilt_before_its_manifest_publishes_nothing(self):
        # tools/engine/bundle.mjs ran, manifest.py not yet: the identity is the same, the files are not.
        self.earlier_copy("1.0.33")
        paths.verify_engine()  # verified before the rebuild, and cached
        (paths.ENGINE_ROOT / "dist" / "server.js").write_text("rebuilt")
        self.assertFalse(provision.refresh_prepared_engine("/usr/bin/node"))
        self.assertFalse(paths.PREPARED_ENGINE.exists())
        with self.assertRaises(provision.ProvisionError) as raised:  # what is wrong is the manifest, not this process
            provision._prepare(TARGET, PINS, EXE, NOTICE)
        self.assertEqual(raised.exception.code, "ENGINE_NOT_VERIFIED")
        self.assertIn("changed dist/server.js", str(raised.exception))
        self.assertEqual(provision._NOT_REUSABLE, set())

    def test_a_script_that_lost_its_execute_bit_publishes_nothing(self):
        self.earlier_copy("1.0.33")
        (paths.ENGINE_ROOT / "scripts" / "start-mcp.mjs").chmod(0o644)
        self.assertFalse(provision.refresh_prepared_engine("/usr/bin/node"))
        self.assertFalse(paths.PREPARED_ENGINE.exists())

    def test_a_copy_made_before_an_engine_change_no_longer_verifies(self):
        # Left by a process that loaded the old engine, and checked by one that still names it.
        self.earlier_copy("1.0.33")
        self.assertTrue(provision.select_engine("/usr/bin/node")["prepared"])
        (paths.ENGINE_ROOT / "dist" / "server.js").write_text("rebuilt")
        self.record_manifest(paths.ENGINE_ROOT, ["package.json", "dist/server.js", "scripts/start-mcp.mjs"])
        self.assertEqual(paths.verify_prepared_engine()["detail"], "the engine changed since this process loaded it")

    def test_an_executable_package_json_is_still_a_prepared_copy(self):
        # The copy's package.json is written anew (0644): the source's recorded mode is not the copy's.
        self.earlier_copy("1.0.33")
        (paths.ENGINE_ROOT / "package.json").chmod(0o755)
        self.record_manifest(paths.ENGINE_ROOT, ["package.json", "dist/server.js", "scripts/start-mcp.mjs"])
        with mock.patch.object(paths, "ENGINE_IDENTITY", paths.engine_identity()):  # loaded after the chmod
            self.assertTrue(provision.refresh_prepared_engine("/usr/bin/node"))
            self.assertTrue(paths.verify_prepared_engine()["verified"])

    def test_a_copy_whose_script_lost_its_execute_bit_does_not_verify(self):
        self.earlier_copy("1.0.33")
        self.assertTrue(provision.select_engine("/usr/bin/node")["prepared"])
        (paths.PREPARED_ENGINE / "scripts" / "start-mcp.mjs").chmod(0o644)
        self.assertEqual(paths.verify_prepared_engine()["detail"], "changed mode of scripts/start-mcp.mjs")

    def test_an_edit_while_the_copy_is_made_publishes_nothing(self):
        self.earlier_copy("1.0.33")
        real = provision.shutil.copytree

        def copy_then_edit(source, stage, *args, **kwargs):
            done = real(source, stage, *args, **kwargs)
            if Path(source) == paths.ENGINE_ROOT:  # the whole engine, not one of the folders it copies on the way
                (paths.ENGINE_ROOT / "dist" / "server.js").write_text("rebuilt")
                (Path(stage) / "dist" / "server.js").write_text("rebuilt")  # copied mid-edit
            return done

        with mock.patch.object(provision.shutil, "copytree", copy_then_edit):
            self.assertFalse(provision.refresh_prepared_engine("/usr/bin/node"))
        self.assertFalse(paths.PREPARED_ENGINE.exists())
        self.assertEqual(provision._NOT_REUSABLE, set())

    def test_the_new_copy_verifies_and_is_chosen(self):
        source = self.earlier_copy("1.0.33")
        selection = provision.select_engine("/usr/bin/node")
        self.assertTrue(selection["prepared"], selection)
        self.assertEqual(selection["root"], paths.PREPARED_ENGINE)
        self.assertEqual((paths.PREPARED_ENGINE / "dist/server.js").read_text(), "edited")
        receipt = json.loads(paths.DEVICE_CLI_RECEIPT.read_text())
        self.assertEqual((receipt["installed_at"], receipt["vendor_terms_accepted"]), ("2026-01-01T00:00:00Z", True))
        self.assertFalse(source.exists(), "no worker ran in it, and this copy now gives its CLI")
        self.assertFalse((paths.DEPS_ROOT / "device-cli-1.0.33.json").exists())
        self.assertEqual(list(paths.DEPS_ROOT.glob("engine.*")), [], "no staging or old folder left")

    def test_a_copy_a_worker_runs_in_stays(self):
        source = self.earlier_copy("1.0.33")
        lease = copy_lease.hold(source)  # a worker of another broker, still running in it
        try:
            self.assertTrue(provision.select_engine("/usr/bin/node")["prepared"])
            self.assertTrue(source.exists())
        finally:
            os.close(lease)  # the worker exits
        self.assertEqual(provision.prune_prepared_copies(), 1, "gone once the worker has")
        self.assertFalse(source.exists())

    def test_the_copy_a_worker_runs_in_is_not_replaced(self):
        self.earlier_copy("1.0.33")
        self.assertTrue(provision.select_engine("/usr/bin/node")["prepared"])
        lease = copy_lease.hold(paths.PREPARED_ENGINE)
        self.addCleanup(os.close, lease)
        with self.assertRaises(provision.ProvisionError) as raised:
            provision._prepare(TARGET, PINS, EXE, NOTICE)  # a repair of the same engine's copy
        self.assertEqual(raised.exception.code, "IN_USE")
        self.assertEqual((paths.PREPARED_ENGINE / "dist/server.js").read_text(), "edited")

    def test_bytecode_beside_the_bundled_engine_stays_out_of_the_copy(self):
        self.earlier_copy("1.0.33")
        for rel in ("scripts/__pycache__/worker.cpython-314.pyc", "scripts/old.pyc"):
            (paths.ENGINE_ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            (paths.ENGINE_ROOT / rel).write_bytes(b"bytecode")
        self.assertTrue(provision.select_engine("/usr/bin/node")["prepared"])
        self.assertEqual(
            [p.name for p in paths.PREPARED_ENGINE.rglob("*") if p.name == "__pycache__" or p.suffix == ".pyc"], []
        )

    def test_a_bytecode_link_in_the_bundled_engine_is_refused_before_any_copy(self):
        self.earlier_copy("1.0.33")
        (paths.ENGINE_ROOT / "scripts" / "gone.pyc").symlink_to(self.base / "nowhere.pyc")
        selection = provision.select_engine("/usr/bin/node")
        self.assertFalse(selection["prepared"])
        self.assertIn("unexpected symlink scripts/gone.pyc", selection["check"]["detail"])
        self.assertFalse(paths.PREPARED_ENGINE.exists())


if __name__ == "__main__":
    unittest.main()
