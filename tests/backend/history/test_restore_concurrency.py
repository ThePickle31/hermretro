"""Editor saves, hard links and backup reuse during restore."""

import os
from unittest import mock

from backend.history import restore_files, snapshots
from tests.backend.history.test_restore_failures import RestoreCase


class RestoreConcurrency(RestoreCase):
    def test_an_editor_save_during_the_last_ancestor_scan_is_not_overwritten(self):
        scan = restore_files._check_project_marker

        def editor_save(fd):
            scan(fd)
            if list(self.keep.parent.glob(".*.hr-restore")):
                self.keep.write_bytes(b"editor")

        with mock.patch.object(restore_files, "_check_project_marker", side_effect=editor_save):
            answer = self.restore()

        self.assertEqual((answer.get("code"), answer["changed"], answer["removed"]), ("PARTIAL", 0, 1))
        self.assertEqual(self.keep.read_bytes(), b"editor")

    def test_an_editor_save_during_the_last_ancestor_scan_is_not_deleted(self):
        added = self.keep.parent / "added.txt"
        added.write_bytes(b"new file")
        scan = restore_files._check_project_marker

        def editor_save(fd):
            scan(fd)
            if added.exists():
                replacement = added.with_suffix(".tmp")
                replacement.write_bytes(b"editor")
                replacement.replace(added)

        with mock.patch.object(restore_files, "_check_project_marker", side_effect=editor_save):
            answer = self.restore()

        self.assertEqual((answer.get("code"), answer["changed"], answer["removed"]), ("PARTIAL", 1, 1))
        self.assertEqual(added.read_bytes(), b"editor")

    def test_a_parent_moved_during_file_validation_is_not_overwritten(self):
        moved = self.root / "moved"
        digest = restore_files._digest_open_file

        def move_parent(handle, path, *args, **kwargs):
            if path == self.keep.name:
                self.keep.parent.rename(moved)
            return digest(handle, path, *args, **kwargs)

        with mock.patch.object(restore_files, "_digest_open_file", side_effect=move_parent):
            answer = self.restore()

        self.assertEqual((answer.get("code"), answer["changed"], answer["removed"]), ("PARTIAL", 0, 1))
        self.assertEqual((moved / self.keep.name).read_bytes(), b"new")

    def test_new_project_markers_during_hashing_protect_both_deletion_and_replacement(
        self,
    ):
        spare = self.root / "new-game" / "spare.gbsres"
        spare.parent.mkdir()
        spare.write_bytes(b"spare scene")
        targets = {path.name: path for path in (spare, self.keep)}
        open_file = restore_files._open_file

        def open_then_mark(path, dir_fd):
            handle = open_file(path, dir_fd)
            if dir_fd is not None and path in targets:
                (targets[path].parent / "child.gbsproj").write_text("{}")
            return handle

        with mock.patch.object(restore_files, "_open_file", side_effect=open_then_mark):
            answer = self.restore()

        self.assertEqual(answer.get("code"), "PARTIAL", answer)
        self.assertEqual((answer["changed"], answer["removed"]), (0, 1))
        self.assertEqual(self.keep.read_bytes(), b"new")
        self.assertEqual(spare.read_bytes(), b"spare scene")
        self.assertEqual(
            (self.folder / answer["backup"] / "files" / "new-game" / spare.name).read_bytes(),
            b"spare scene",
        )

    def test_atomic_save_after_the_final_hash_preserves_the_edit_and_reports_partial(
        self,
    ):
        digest = snapshots.file_digest

        def save_after_read(path, *args, **kwargs):
            measured = digest(path, *args, **kwargs)
            if path == self.keep and not self.extra.exists():
                temporary = self.keep.with_suffix(".tmp")
                temporary.write_bytes(b"editor")
                temporary.replace(self.keep)
            return measured

        with mock.patch.object(snapshots, "file_digest", side_effect=save_after_read):
            answer = self.restore()

        self.assertEqual(answer.get("code"), "PARTIAL", answer)
        self.assertTrue(any(self.keep.name in problem for problem in answer["problems"]), answer)
        self.assertEqual(self.keep.read_bytes(), b"editor")
        self.assertEqual(
            (self.folder / answer["backup"] / "files" / "project" / self.keep.name).read_bytes(),
            b"new",
        )

    def test_hard_linked_files_can_be_removed_replaced_and_kept_in_one_restore(self):
        changed = self.keep.with_name("a-changed.txt")
        unchanged = self.keep.with_name("z-unchanged.txt")
        changed.write_bytes(b"past")
        unchanged.write_bytes(b"new")
        self.keep.write_bytes(b"old")
        snapshots.take(self.store, self.game, self.root, now_ms=2000)
        self.keep.write_bytes(b"new")
        for alias in (changed, unchanged):
            alias.unlink()
            os.link(self.keep, alias)
        removed = self.keep.with_name("removed.txt")
        os.link(self.keep, removed)

        answer = self.restore(id="2000")

        self.assertTrue(answer["ok"], answer)
        self.assertEqual((answer["changed"], answer["removed"]), (2, 1))
        self.assertFalse(removed.exists())
        self.assertEqual(changed.read_bytes(), b"past")
        self.assertEqual(self.keep.read_bytes(), b"old")
        self.assertEqual(unchanged.read_bytes(), b"new")

    def test_an_external_ctime_change_after_restore_unlinks_a_sibling_is_preserved(self):
        os.link(self.keep, self.root / "also-new.txt")
        scan = restore_files._check_project_marker
        before = self.keep.stat().st_mode
        edited = False

        def editor_change(fd):
            nonlocal edited
            scan(fd)
            if not edited and list(self.keep.parent.glob(".*.hr-restore")):
                edited = True
                self.keep.chmod(0o600 if before & 0o777 != 0o600 else 0o644)

        with mock.patch.object(restore_files, "_check_project_marker", side_effect=editor_change):
            answer = self.restore()

        self.assertEqual((answer.get("code"), answer["changed"], answer["removed"]), ("PARTIAL", 0, 2))
        self.assertTrue(edited)
        self.assertNotEqual(self.keep.stat().st_mode, before)
        self.assertEqual(self.keep.read_bytes(), b"new")

    def test_partial_restore_exposes_a_reused_build_snapshot_as_a_backup(self):
        ref = "a" * 32
        saved = snapshots.take(self.store, self.game, self.root, now_ms=2000, build_ref=ref)
        restore = snapshots._restore_files

        def edit_then_restore(*args, **kwargs):
            self.keep.write_bytes(b"editor")
            return restore(*args, **kwargs)

        with mock.patch.object(snapshots, "_restore_files", side_effect=edit_then_restore):
            answer = self.restore()

        self.assertEqual((answer["code"], answer["backup"]), ("PARTIAL", saved["id"]))
        reused, _ = snapshots.list_snapshots(self.store, self.game)
        self.assertEqual((reused["id"], reused["reason"], reused["buildRefs"]), (saved["id"], "build", [ref]))
        self.assertEqual(reused["backup"]["from"], "1000")
        self.assertGreater(reused["backup"]["at"], reused["at"])
        self.assertTrue(self.restore(id=answer["backup"])["ok"])
        self.assertEqual(self.keep.read_bytes(), b"new")
