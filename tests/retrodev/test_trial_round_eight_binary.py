"""Review round 2 of the eighth trial round's pull request: sync's new-lines warning read every staged file as text,
so a PNG merged from dev (even cleanly, beside a resolved source conflict) stopped `sync` with a UnicodeDecodeError
before it could finish the merge. It now counts only the files that were in conflict, reads blobs as bytes and
skips binary ones; every git call retrodev makes reads output it cannot decode without crashing. Each test failed
before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_eight_binary
"""

import unittest
from pathlib import Path

from retrodev import land_carry, repo

from tests.retrodev.fixture import RepoCase, git, parallel, write

load_tests = parallel
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + bytes(range(256))
ART = "player/art.png"
TEXT = "backend/library/both.py"


class SyncBinary(RepoCase):
    def bytes_on_dev(self, name: str, data: bytes) -> None:
        other = self.base / "other"
        if not other.exists():
            git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        git(other, "pull", "-q", "origin", "dev")
        self.commit_bytes(other, name, data, "Dev changes the art")
        git(other, "push", "-q", "origin", "dev")

    def commit_bytes(self, tree: Path, name: str, data: bytes, message: str = "Change the art") -> None:
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_bytes(data)
        git(tree, "add", "-A")
        git(tree, "commit", "-q", "-m", message)

    def conflicted(self, branch_art: bytes | None = None) -> Path:
        """dev changes a PNG and a text file; the branch conflicts on the text file (and on the PNG when given)."""
        self.on_dev(TEXT, "VALUE = 1\n", "Both")
        self.bytes_on_dev(ART, PNG)
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/art")
        self.commit(tree, TEXT, "VALUE = 2\n")
        if branch_art is not None:
            self.commit_bytes(tree, ART, branch_art)
        self.on_dev(TEXT, "VALUE = 3\n")
        self.bytes_on_dev(ART, PNG[::-1] + b"\xff\xfe")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        return tree

    def assert_merged(self, tree: Path) -> None:
        self.assertFalse(repo.ok(["rev-parse", "-q", "--verify", "MERGE_HEAD"], tree), "the merge is finished")
        self.assertEqual(len(git(tree, "rev-list", "--parents", "-n1", "HEAD").split()), 3, "a merge commit")
        self.assertEqual(git(tree, "status", "--porcelain"), "")

    def test_a_png_merged_cleanly_from_dev_lets_sync_finish_and_still_warns_about_the_text_file(self):
        tree = self.conflicted()
        write(tree, TEXT, "VALUE = 3\nEXTRA = 4\n")
        git(tree, "add", TEXT)
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assert_merged(tree)
        self.assertEqual((tree / ART).read_bytes(), PNG[::-1] + b"\xff\xfe", "dev's art came in")
        self.assertIn(f"warning: the resolution adds 1 line(s) neither side had ({TEXT}): ", out)

    def test_a_png_conflict_resolved_to_dev_s_art_is_never_read_as_text(self):
        """A binary file has no hunks: taking one side whole is its only resolution (here dev's, so it is staged)."""
        tree = self.conflicted(branch_art=PNG + b"\x80ours")
        git(tree, "checkout", "--theirs", "--", ART)
        write(tree, TEXT, "VALUE = 2\n")
        git(tree, "add", ART, TEXT)
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assert_merged(tree)
        self.assertEqual((tree / ART).read_bytes(), PNG[::-1] + b"\xff\xfe")
        self.assertNotIn("neither side had", out)

    def test_only_conflicted_files_count_a_cleanly_merged_text_file_never_warns(self):
        """dev and the branch change different hunks of one file (git merges it); only the conflicted file counts."""
        self.on_dev("backend/library/wide.py", "A = 1\n\n\n\n\nB = 1\n", "Wide")
        tree_text = "A = 2\n\n\n\n\nB = 1\n"
        self.on_dev(TEXT, "VALUE = 1\n", "Both")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/wide")
        self.commit(tree, TEXT, "VALUE = 2\n")
        self.commit(tree, "backend/library/wide.py", tree_text)
        self.on_dev(TEXT, "VALUE = 3\n")
        self.on_dev("backend/library/wide.py", "A = 1\n\n\n\n\nB = 3\n")
        self.assertEqual(self.run_cli("sync", cwd=tree)[0], 1)
        write(tree, TEXT, "VALUE = 2\n")
        write(tree, "backend/library/wide.py", "A = 2\n\n\n\n\nB = 3\nC = 9\n")  # work slipped into a clean file
        git(tree, "add", TEXT, "backend/library/wide.py")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("neither side had", out)


class Blobs(RepoCase):
    def test_git_output_that_is_not_utf_8_never_raises(self):
        tree = self.worktree("fix/blob")
        (tree / ART).parent.mkdir(parents=True, exist_ok=True)
        (tree / ART).write_bytes(PNG)
        (tree / "notes.txt").write_bytes(b"caf\xe9\n")
        git(tree, "add", "-A")
        git(tree, "commit", "-q", "-m", "Art")
        code, out, _err = repo.run(["git", "cat-file", "blob", f"HEAD:{ART}"], tree)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("\ufffdPNG"))
        self.assertEqual(repo.blob(tree, f"HEAD:{ART}"), PNG)
        self.assertIsNone(repo.text(PNG))
        self.assertIsNone(repo.text(b"caf\xe9\n"), "not UTF-8: not counted as lines")
        self.assertEqual(repo.text(b"VALUE = 1\n"), "VALUE = 1\n")
        self.assertIsNone(repo.blob(tree, "HEAD:missing.txt"))
        self.assertIsNone(land_carry.blob(tree, "HEAD", ART), "land's resolution counter cannot count it")
        self.assertIsNone(land_carry.blob(tree, "HEAD", "notes.txt"))
        self.assertEqual(land_carry.blob(tree, "HEAD", "missing.txt"), "")


if __name__ == "__main__":
    unittest.main()
