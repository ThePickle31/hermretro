"""Restoring a version requires an intact backup and an exclusive lock across processes.

Run alone: python -m unittest tests.backend.assets.test_asset_restore
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from backend.assets import rpcs as assets_rpcs
from backend.assets import versions as assets_versions
from backend.assets.writer_lock import project_writer_lock
from tests.backend.assets.test_asset_versions import PNG_A, PNG_B, documented_keep, path_digest
from tests.support import isolated_home, make_library_game


class AssetRestore(unittest.TestCase):
    def setUp(self):
        home = isolated_home(self)
        _game, self.game = make_library_game(home, "Cat Field")
        self.cover = self.game / "cover.png"
        self.data = home.data
        self.params = {"root": str(self.game), "path": str(self.cover)}
        self.asset = assets_rpcs.rpc_asset(None)
        self.info = assets_rpcs.rpc_asset_info(None)
        self.restore = assets_rpcs.rpc_asset_restore(None)

    def write(self, data, seconds):
        self.cover.write_bytes(data)
        os.utime(self.cover, ns=(seconds * 10**9, seconds * 10**9))

    def test_a_read_only_lock_directory_only_disables_history(self):
        self.write(PNG_A, 1000)
        old = self.asset(self.params)
        self.write(PNG_B, 2000)
        original_open = Path.open

        def read_only_lock(path, *args, **kwargs):
            if path.parent == self.data / "asset-version-locks":
                raise PermissionError("read-only lock directory")
            return original_open(path, *args, **kwargs)

        with (
            mock.patch.object(Path, "open", read_only_lock),
            mock.patch.object(assets_rpcs, "emit") as emit,
            mock.patch.object(assets_rpcs.logger, "exception"),
        ):
            live = self.asset(self.params)
            self.assertTrue(live["ok"], live)
            self.assertNotEqual(live["dataUrl"], old["dataUrl"])
            self.assertEqual(self.asset({**self.params, "at": 1_500_000}), live)
            self.assertEqual(self.asset({**self.params, "version": live["versionId"]}), live)
            self.assertFalse(self.asset({**self.params, "version": old["versionId"]})["ok"])
            info = self.info(self.params)
            self.assertTrue(info["ok"], info)
            self.assertEqual(info["kind"], "cover")
            self.assertEqual(info["versions"], [])
            self.assertFalse(self.restore({**self.params, "version": old["versionId"]})["ok"])
        self.assertEqual(self.cover.read_bytes(), PNG_B)
        emit.assert_not_called()

    def test_restore_reports_success_when_only_the_final_listing_fails(self):
        self.write(PNG_A, 1000)
        selected = self.asset(self.params)["versionId"]
        self.write(PNG_B, 2000)

        def fail_listing(real, folder):
            self.assertEqual(real.read_bytes(), PNG_A)
            self.assertEqual((folder / f"{2000 * 10**9}.png").read_bytes(), PNG_B)
            raise PermissionError("history listing unavailable")

        with (
            mock.patch.object(assets_versions, "_versions", side_effect=fail_listing),
            mock.patch.object(assets_rpcs, "emit") as emit,
            mock.patch.object(assets_rpcs.logger, "exception"),
        ):
            restored = self.restore({**self.params, "version": selected})
        self.assertEqual(restored, {"ok": True, "path": str(self.cover), "versions": []})
        emit.assert_called_once_with("assets.image_restored", path=str(self.cover))

    def test_preview_reconciles_an_interrupted_restore_at_the_cap(self):
        limit = documented_keep()
        for index in range(limit):
            self.write(PNG_A[:24] + index.to_bytes(2, "big"), 1001 + index)
            self.assertTrue(self.asset(self.params)["ok"])
        # The restore backed up an older live file and stopped before replacing it or pruning.
        self.write(PNG_B, 1000)
        with assets_versions._version_lock(self.cover):
            folder = assets_versions._versions_dir(self.cover, self.game)
            backup, added = assets_versions._save_version(self.cover, folder, required=True)
        self.assertTrue(added)
        self.assertEqual(len(list(folder.iterdir())), limit + 1)

        selected = str(1001 * 10**9)
        viewed = self.asset({**self.params, "version": selected})
        self.assertEqual(viewed["versionId"], selected)
        self.assertTrue(viewed["earlier"])
        self.assertEqual(len(list(folder.iterdir())), limit)
        self.assertEqual(backup.read_bytes(), PNG_B)
        self.assertTrue((folder / f"{selected}.png").is_file())
        self.assertFalse((folder / f"{1002 * 10**9}.png").exists())

    def test_reopening_history_after_live_replacement_keeps_both_protected_versions(self):
        limit = documented_keep()
        for index in range(limit):
            self.write(PNG_A[:24] + index.to_bytes(2, "big"), 1001 + index)
            self.assertTrue(self.asset(self.params)["ok"])
        selected = str(1001 * 10**9)
        outgoing = str(1000 * 10**9)
        self.write(PNG_B, 1000)
        write_image = assets_versions._write_image

        def stop_after_replace(path, data, suffix, **kwargs):
            write_image(path, data, suffix, **kwargs)
            if path == self.cover:
                raise SystemExit("stopped after replacing live bytes")

        with mock.patch.object(assets_versions, "_write_image", side_effect=stop_after_replace):
            with self.assertRaisesRegex(SystemExit, "stopped after replacing live bytes"):
                self.restore({**self.params, "version": selected})
        self.assertEqual(self.cover.read_bytes(), PNG_A[:24] + b"\x00\x00")

        info = self.info(self.params)
        self.assertTrue(info["ok"], info)
        self.assertEqual(len(info["versions"]), limit)
        self.assertIn(selected, [entry["id"] for entry in info["versions"]])
        self.assertIn(outgoing, [entry["id"] for entry in info["versions"]])
        folder = assets_versions._versions_dir(self.cover, self.game)
        self.assertEqual(len(list(folder.iterdir())), limit)

        undone = self.restore({**self.params, "version": outgoing})
        self.assertTrue(undone["ok"], undone)
        self.assertEqual(self.cover.read_bytes(), PNG_B)

    @mock.patch.object(assets_versions, "ASSET_KEEP_VERSIONS", 3)
    def test_a_later_preview_finishes_capture_and_pruning_without_losing_undo(self):
        self.write(PNG_A, 1001)
        selected = self.asset(self.params)["versionId"]
        for moment in (1002, 1003):
            self.write(PNG_A + moment.to_bytes(2, "big"), moment)
            self.assertTrue(self.asset(self.params)["ok"])
        self.write(PNG_B, 1000)
        folder = assets_versions._versions_dir(self.cover, self.game)
        outgoing = str(1000 * 10**9)
        backup = folder / f"{outgoing}.png"
        pending = folder / assets_versions._PENDING_RESTORE
        write_image = assets_versions._write_image

        def fail_capture(path, data, suffix, **kwargs):
            if path.parent == folder and data == PNG_A:
                raise OSError("could not capture the restored file")
            write_image(path, data, suffix, **kwargs)

        with mock.patch.object(assets_versions, "_write_image", side_effect=fail_capture):
            self.assertTrue(self.restore({**self.params, "version": selected})["ok"])
        self.assertEqual(self.cover.read_bytes(), PNG_A)
        self.assertTrue(pending.is_file())
        self.assertEqual(backup.read_bytes(), PNG_B)
        self.assertEqual(len(assets_versions._kept_versions(folder)), 4)

        unlink = Path.unlink
        evicted = folder / f"{1002 * 10**9}.png"

        def fail_pruning(path, *args, **kwargs):
            if path == evicted:
                raise PermissionError("could not prune history")
            return unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", fail_pruning):
            self.assertTrue(self.asset(self.params)["ok"])
        self.assertTrue(pending.is_file())
        self.assertEqual(backup.read_bytes(), PNG_B)

        self.assertTrue(self.asset(self.params)["ok"])
        self.assertFalse(pending.exists())
        self.assertEqual(len(assets_versions._kept_versions(folder)), 3)
        self.assertEqual(backup.read_bytes(), PNG_B)
        self.assertTrue(self.restore({**self.params, "version": outgoing})["ok"])
        self.assertEqual(self.cover.read_bytes(), PNG_B)

    def test_restore_leaves_current_bytes_in_place_if_the_restore_record_cannot_be_written(self):
        self.write(PNG_A, 1000)
        selected = self.asset(self.params)["versionId"]
        self.write(PNG_B, 2000)
        folder = assets_versions._versions_dir(self.cover, self.game)

        with (
            mock.patch.object(assets_versions, "write_json_atomic", side_effect=OSError("restore record disk full")),
            mock.patch.object(assets_rpcs, "emit") as emit,
            mock.patch.object(assets_rpcs.logger, "exception"),
        ):
            answer = self.restore({**self.params, "version": selected})
        self.assertFalse(answer["ok"], answer)
        self.assertIn("restore record disk full", answer["error"])
        self.assertEqual(self.cover.read_bytes(), PNG_B)
        self.assertEqual([item.name for item in folder.iterdir()], [f"{selected}.png"])
        emit.assert_not_called()

    def test_restore_leaves_current_bytes_in_place_if_the_backup_cannot_be_written(self):
        self.write(PNG_A, 1000)
        old_id = self.asset(self.params)["versionId"]
        self.write(PNG_B, 2000)
        folder = assets_versions._versions_dir(self.cover, self.game)
        original_replace = os.replace

        def fail_backup(source, destination):
            if Path(destination).parent == folder:
                raise OSError("backup disk full")
            return original_replace(source, destination)

        with (
            mock.patch.object(os, "replace", side_effect=fail_backup),
            mock.patch.object(assets_rpcs, "emit") as emit,
            mock.patch.object(assets_rpcs.logger, "exception"),
        ):
            answer = self.restore({**self.params, "version": old_id})
        self.assertFalse(answer["ok"], answer)
        self.assertIn("backup disk full", answer["error"])
        self.assertEqual(self.cover.read_bytes(), PNG_B)
        self.assertEqual([item.name for item in folder.iterdir()], [f"{old_id}.png"])
        emit.assert_not_called()

    @mock.patch.object(assets_versions, "ASSET_KEEP_VERSIONS", 2)
    def test_failed_live_replacement_preserves_history_at_the_cap(self):
        self.write(PNG_A, 1000)
        selected = self.asset(self.params)["versionId"]
        self.write(PNG_A + b"newer", 2000)
        self.assertTrue(self.asset(self.params)["ok"])
        self.write(PNG_B, 3000)
        folder = assets_versions._versions_dir(self.cover, self.game)
        history = {item.name: item.read_bytes() for item in folder.iterdir()}
        original_replace = os.replace

        def fail_live_replace(source, destination):
            if Path(destination) == self.cover:
                raise OSError("live replacement failed")
            return original_replace(source, destination)

        with (
            mock.patch.object(os, "replace", side_effect=fail_live_replace),
            mock.patch.object(assets_rpcs, "emit") as emit,
            mock.patch.object(assets_rpcs.logger, "exception"),
        ):
            answer = self.restore({**self.params, "version": selected})
        self.assertFalse(answer["ok"], answer)
        self.assertIn("live replacement failed", answer["error"])
        self.assertEqual(self.cover.read_bytes(), PNG_B)
        self.assertEqual({item.name: item.read_bytes() for item in folder.iterdir()}, history)
        emit.assert_not_called()

    @mock.patch.object(assets_versions, "ASSET_KEEP_VERSIONS", 2)
    def test_capture_keeps_the_live_version_with_an_older_mtime(self):
        self.write(PNG_A, 2000)
        evicted = self.asset(self.params)["versionId"]
        self.write(PNG_A + b"newer", 3000)
        latest = self.asset(self.params)["versionId"]
        self.write(PNG_B, 1000)
        captured = self.asset(self.params)
        self.assertTrue(captured["ok"], captured)

        folder = assets_versions._versions_dir(self.cover, self.game)
        self.assertEqual({item.stem for item in folder.iterdir()}, {captured["versionId"], latest})
        self.write(PNG_A, 4000)
        self.assertEqual(self.asset({**self.params, "version": captured["versionId"]})["dataUrl"], captured["dataUrl"])
        self.assertEqual(self.asset({**self.params, "version": evicted})["code"], "MISSING")

    def test_restore_keeps_an_exclusive_lock_until_the_live_file_is_replaced(self):
        self.write(PNG_A, 1000)
        old_id = self.asset(self.params)["versionId"]
        (lock,) = (self.data / "asset-version-locks").iterdir()
        self.write(PNG_B, 2000)
        original_replace = os.replace

        def check_before_replace(source, destination):
            if Path(destination) == self.cover:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import fcntl, sys\n"
                        "with open(sys.argv[1], 'ab') as lock:\n"
                        "    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                        "    except BlockingIOError: sys.exit(0)\n"
                        "    sys.exit('asset lock was available during restore')\n",
                        str(lock),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            return original_replace(source, destination)

        with mock.patch.object(os, "replace", side_effect=check_before_replace) as replace:
            answer = self.restore({**self.params, "version": old_id})
        self.assertTrue(answer["ok"], answer)
        self.assertTrue(any(Path(call.args[1]) == self.cover for call in replace.call_args_list))

    def test_restore_conflicts_if_an_engine_writer_holds_the_project_lock(self):
        self.write(PNG_A, 1000)
        selected = self.asset(self.params)["versionId"]
        self.write(PNG_B, 2000)
        folder = assets_versions._versions_dir(self.cover, self.game)

        with (
            project_writer_lock(self.game),
            mock.patch.object(assets_rpcs, "emit") as emit,
        ):
            answer = self.restore({**self.params, "version": selected})

        self.assertEqual(answer.get("code"), "CONFLICT", answer)
        self.assertEqual(self.cover.read_bytes(), PNG_B)
        self.assertEqual([item.name for item in folder.iterdir()], [f"{selected}.png"])
        emit.assert_not_called()

    def test_restore_detects_external_edits_after_writing_the_backup(self):
        original_mtime = 2000 * 10**9
        record = assets_versions.write_json_atomic

        def rewrite():
            self.write(PNG_A, 2000)  # An in-place edit of the same size, with mtime put back.

        def replace():
            replacement = self.cover.with_suffix(".replacement")
            replacement.write_bytes(PNG_B)
            os.utime(replacement, ns=(original_mtime, original_mtime))
            os.replace(replacement, self.cover)

        for edit in (rewrite, replace, lambda: self.cover.chmod(0o640)):
            with self.subTest(edit=edit):
                self.write(PNG_A, 1000)
                selected = self.asset(self.params)["versionId"]
                self.write(PNG_B, 2000)
                self.cover.chmod(0o600)
                folder = assets_versions._versions_dir(self.cover, self.game)
                history = {item.name: item.read_bytes() for item in folder.iterdir()}
                external = {}

                def edit_after_backup(path, data, *, folder=folder, edit=edit, external=external):
                    self.assertEqual((folder / f"{original_mtime}.png").read_bytes(), PNG_B)
                    record(path, data)
                    edit()
                    external.update(data=self.cover.read_bytes(), stat=self.cover.stat())

                with (
                    mock.patch.object(
                        assets_versions,
                        "write_json_atomic",
                        side_effect=edit_after_backup,
                    ),
                    mock.patch.object(assets_rpcs, "emit") as emit,
                ):
                    answer = self.restore({**self.params, "version": selected})

                self.assertEqual(answer.get("code"), "CONFLICT", answer)
                self.assertEqual(self.cover.read_bytes(), external["data"])
                actual = self.cover.stat()
                expected = external["stat"]
                self.assertEqual(
                    (actual.st_ino, actual.st_mode, actual.st_mtime_ns),
                    (expected.st_ino, expected.st_mode, expected.st_mtime_ns),
                )
                self.assertEqual({item.name: item.read_bytes() for item in folder.iterdir()}, history)
                self.assertEqual(list(self.cover.parent.glob(f".{self.cover.name}.*.restore")), [])
                emit.assert_not_called()

    def test_restore_at_the_cap_keeps_the_selected_version_and_what_it_replaced(self):
        limit = documented_keep()
        for index in range(limit):
            self.write(PNG_A[:24] + index.to_bytes(2, "big"), 1000 + index)
            self.assertTrue(self.asset(self.params)["ok"])
        self.write(PNG_B, 1000 + limit)
        outgoing = self.cover.read_bytes()
        selected_id = str(1000 * 10**9)
        outgoing_id = str((1000 + limit) * 10**9)
        restored = self.restore({**self.params, "version": selected_id})
        self.assertTrue(restored["ok"], restored)
        self.assertEqual(self.cover.read_bytes()[24:], b"\x00\x00")
        self.assertEqual(len(restored["versions"]), limit)
        self.assertIn(selected_id, [entry["id"] for entry in restored["versions"]])
        self.assertIn(outgoing_id, [entry["id"] for entry in restored["versions"]])
        self.assertEqual(sum(entry["current"] for entry in restored["versions"]), 1)

        for at, version in ((1000, selected_id), (1000 + limit, outgoing_id)):
            shown = self.asset({**self.params, "at": at * 1000 + 500})
            self.assertTrue(shown["earlier"], shown)
            self.assertEqual(shown["versionId"], version)
            self.assertEqual(self.asset({**self.params, "version": version})["dataUrl"], shown["dataUrl"])

        undone = self.restore({**self.params, "version": outgoing_id})
        self.assertTrue(undone["ok"], undone)
        self.assertEqual(self.cover.read_bytes(), outgoing)

    def test_restore_accepts_a_version_kept_before_history_was_filed_by_game(self):
        old_id = str(1000 * 10**9)
        legacy = self.data / "asset-versions" / path_digest(self.cover)
        legacy.mkdir(parents=True)
        (legacy / f"{old_id}.png").write_bytes(PNG_A)
        self.write(PNG_B, 2000)

        restored = self.restore({**self.params, "version": old_id})
        self.assertTrue(restored["ok"], restored)
        self.assertEqual(self.cover.read_bytes(), PNG_A)
        self.assertFalse(legacy.exists())
        self.assertIn(old_id, [entry["id"] for entry in restored["versions"]])
