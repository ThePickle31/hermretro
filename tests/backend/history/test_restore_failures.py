"""Restore preflight, integrity and partial failures. Run alone: python -m unittest tests.backend.history.test_restore_failures"""

import os
import subprocess
import sys
import unittest
from unittest import mock

from backend.history import rpcs, snapshots
from tests.support import isolated_home, make_library_game


class RestoreFailures(unittest.TestCase):
    def setUp(self):
        home = isolated_home(self)
        self.store = home.data / "snapshots"
        self.game, self.root = make_library_game(home)
        self.folder = self.store / self.game
        self.keep = self.root / "project" / "scene.gbsres"
        self.keep.write_bytes(b"old")
        snapshots.take(self.store, self.game, self.root, now_ms=1000)
        self.saved = self.folder / "1000" / "files"
        self.keep.write_bytes(b"new")
        self.extra = self.root / "extra.txt"
        self.extra.write_text("keep me")

    def restore(self, **selection):
        return rpcs.rpc_build_restore(None)({"game": self.game, "id": "1000", **selection})

    def assert_refused(self, code, **selection):
        answer = self.restore(**selection)
        self.assertEqual((answer.get("ok"), answer.get("code")), (False, code), answer)
        self.assertEqual(self.keep.read_bytes(), b"new")
        self.assertEqual(self.extra.read_text(), "keep me")
        self.assertEqual([record["id"] for record in snapshots.list_snapshots(self.store, self.game)], ["1000"])

    def test_a_missing_saved_file_fails_the_count_check(self):
        (self.saved / "project" / "scene.gbsres").unlink()
        self.assert_refused("INVALID_SNAPSHOT")

    def test_a_saved_file_changed_without_changing_its_size_fails_the_fingerprint_check(self):
        (self.saved / "project" / "scene.gbsres").write_bytes(b"bad")
        self.assert_refused("INVALID_SNAPSHOT")

    def test_a_snapshot_id_without_the_selected_build_occurrence_is_refused(self):
        self.assert_refused("MISSING", buildRef="other-build")
        self.assert_refused("MISSING", buildAt=2000)
        self.assertTrue(self.restore(buildAt=1000)["ok"])

    def test_a_saved_file_replaced_by_a_symlink_is_rejected(self):
        saved = self.saved / "project" / "scene.gbsres"
        saved.unlink()
        saved.symlink_to(self.extra)
        self.assert_refused("INVALID_SNAPSHOT")

    def test_a_snapshot_that_cannot_be_fully_listed_is_rejected(self):
        self.scandir_fails(self.saved / "project")
        self.assert_refused("INVALID_SNAPSHOT")

    def test_an_unreadable_project_folder_blocks_backup_and_restore(self):
        self.scandir_fails(self.root / "project")
        self.assert_refused("BACKUP_FAILED")

    def test_a_tree_that_changes_during_backup_is_rejected(self):
        original_read = snapshots._file_digest

        def digest(path, limit, writer=None):
            if writer is not None and path == self.keep:
                (self.root / "appeared.txt").write_text("new file")
            return original_read(path, limit, writer)

        with mock.patch.object(snapshots, "_file_digest", side_effect=digest):
            self.assert_refused("BACKUP_FAILED")
        self.assertEqual(list(self.folder.glob("*.part")), [])

    def test_a_project_over_the_backup_limit_is_untouched(self):
        count = len(snapshots.walk(self.saved, stored=True))
        with mock.patch.object(snapshots, "MAX_FILES", count):
            self.assert_refused("TOO_LARGE")

    def test_an_incomplete_restore_returns_the_backup_counts_and_problems(self):
        self.keep.unlink()
        # Put the link outside the project so the restore can remove the new project file independently.
        outside = self.store / "untouched"
        outside.write_text("keep me")
        self.keep.symlink_to(outside)
        answer = self.restore()
        self.assertEqual((answer["ok"], answer["code"], answer["changed"], answer["removed"]), (False, "PARTIAL", 0, 1))
        self.assertTrue(self.keep.is_symlink())
        self.assertEqual(outside.read_text(), "keep me")
        self.assertFalse(self.extra.exists())
        self.assertIn("project/scene.gbsres: a link is in the way", answer["problems"])
        self.assertEqual((self.folder / answer["backup"] / "files" / "extra.txt").read_text(), "keep me")

    def test_a_damaged_identical_backup_is_replaced_with_a_valid_copy(self):
        saved = snapshots.take(self.store, self.game, self.root, now_ms=2000)
        (self.folder / saved["id"] / "files" / "extra.txt").unlink()
        restored = self.restore()
        self.assertTrue(restored["ok"], restored)
        self.assertNotEqual(restored["backup"], saved["id"])
        self.assertEqual((self.folder / restored["backup"] / "files" / "extra.txt").read_text(), "keep me")

    def test_restore_holds_the_same_lock_from_selection_through_pruning_and_writes(self):
        probe_lock = """
import fcntl
import sys

with open(sys.argv[1]) as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(0)
sys.exit("History lock was available")
"""

        def under_lock(function):
            def check(*args, **kwargs):
                probe = subprocess.run(
                    [sys.executable, "-c", probe_lock, str(self.folder / ".lock")], capture_output=True, text=True
                )
                self.assertEqual(probe.returncode, 0, probe.stderr)
                return function(*args, **kwargs)

            return check

        with (
            mock.patch.object(snapshots, "_read_snapshot", side_effect=under_lock(snapshots._read_snapshot)) as read,
            mock.patch.object(snapshots, "_take_locked", side_effect=under_lock(snapshots._take_locked)) as backup,
            mock.patch.object(snapshots, "_prune", side_effect=under_lock(snapshots._prune)) as prune,
            mock.patch.object(snapshots, "_restore_files", side_effect=under_lock(snapshots._restore_files)) as write,
        ):
            answer = self.restore()
        self.assertTrue(answer["ok"], answer)
        for operation in (read, backup, prune, write):
            operation.assert_called_once()

    def scandir_fails(self, folder):
        original_scan = os.scandir

        def scandir(path):
            if path == folder:
                raise PermissionError("directory unreadable")
            return original_scan(path)

        self.enterContext(mock.patch.object(snapshots.os, "scandir", side_effect=scandir))


if __name__ == "__main__":
    unittest.main()
