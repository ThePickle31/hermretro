"""The read-only audit: tool calls from a crafted state.db, and the before/after snapshots."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests.retrodev.review.helpers import git, make_db, make_repo

from retrodev.review import audit


class Paths(unittest.TestCase):
    def test_state_db_locations(self):
        self.assertEqual(audit.state_db("rev", {"HERMES_HOME": "/x/h"}), Path("/x/h/profiles/rev/state.db"))
        self.assertEqual(audit.state_db("default", {"HERMES_HOME": "/x/h"}), Path("/x/h/state.db"))
        # HERMES_HOME naming a profile (Hermes sets it so inside a profile's session) still finds the root.
        self.assertEqual(
            audit.state_db("rev", {"HERMES_HOME": "/x/h/profiles/dev"}), Path("/x/h/profiles/rev/state.db")
        )
        self.assertEqual(audit.state_db("rev", {}), Path.home() / ".hermes" / "profiles" / "rev" / "state.db")


class Calls(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="retrodev-audit-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.rev = self.tmp / "reviews" / "7" / "round1"
        (self.rev / "src").mkdir(parents=True)
        self.snap = {"worktrees": "w", "heads": {}, "status": {}, "remote": "r", "src": "d"}

    def run_audit(self, calls, sessions=("s1",)):
        db = make_db(self.tmp / "h" / "profiles" / "rev" / "state.db", {"s1": calls})
        return audit.audit(
            profile="rev",
            session_ids=list(sessions),
            round_dir=self.rev,
            before=self.snap,
            after=dict(self.snap),
            env={"HERMES_HOME": str(self.tmp / "h")},
        ), db

    def test_clean_session(self):
        result, db = self.run_audit(
            [
                ("search_files", {"pattern": "*", "target": "files", "path": str(self.rev / "review")}),
                ("read_file", {"path": str(self.rev / "src" / "backend" / "a.py")}),
                ("read_file", {"path": "src/README.md"}),  # relative: the reviewer's folder is the round folder
                ("search_files", {"pattern": "TODO"}),  # no path: searches its folder
            ]
        )
        self.assertEqual(result["violations"], [])
        self.assertTrue(result["ok"])
        self.assertEqual(result["tools"], {"search_files": 2, "read_file": 2})
        self.assertEqual(result["db"], str(db))

    def test_violations(self):
        outside = str(self.tmp / "elsewhere" / "x.py")
        cases = {
            "write_file": [("write_file", {"path": str(self.rev / "src" / "a.py"), "content": "x"})],
            "patch": [("patch", {"path": str(self.rev / "src" / "a.py"), "old_string": "a", "new_string": "b"})],
            "terminal": [("terminal", {"command": "git status"})],
            "absolute outside": [("read_file", {"path": outside})],
            "dot-dot escape": [("read_file", {"path": str(self.rev / "src" / ".." / ".." / "7.json")})],
            "relative escape": [("search_files", {"pattern": "x", "path": "../../.."})],
            "home": [("read_file", {"path": "~/.ssh/id_ed25519"})],
            "sibling prefix": [("read_file", {"path": str(self.rev) + "-other/a"})],
        }
        for name, calls in cases.items():
            with self.subTest(name):
                result, _ = self.run_audit([("read_file", {"path": str(self.rev / "review" / "brief.md")}), *calls])
                self.assertFalse(result["ok"])
                self.assertEqual(len(result["violations"]), 1, result["violations"])

    def test_symlink_out_of_the_round_is_outside(self):
        (self.rev / "src" / "link").symlink_to(self.tmp)
        result, _ = self.run_audit([("read_file", {"path": str(self.rev / "src" / "link" / "secret")})])
        self.assertFalse(result["ok"])

    def test_missing_session_or_database(self):
        result, _ = self.run_audit([], sessions=("s-unknown",))
        self.assertIn("not found", result["violations"][0])
        result, _ = self.run_audit([], sessions=())
        self.assertIn("no session id", result["violations"][0])
        missing = audit.audit(
            profile="nobody",
            session_ids=["s1"],
            round_dir=self.rev,
            before=self.snap,
            after=self.snap,
            env={"HERMES_HOME": str(self.tmp / "none")},
        )
        self.assertIn("cannot audit", missing["violations"][0])

    def test_unknown_schema_is_refused(self):
        import sqlite3

        db = self.tmp / "odd.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE messages (id INTEGER, body TEXT)")
        conn.commit()
        conn.close()
        with self.assertRaises(audit.AuditError):
            audit.tool_calls(db, ["s1"])


class Snapshots(unittest.TestCase):
    """Only what a file-only reviewer could reach besides its tool calls: the PR's worktree, its remote branch, src/."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="retrodev-snap-"))
        cls.info = make_repo(cls.tmp)
        cls.repo = cls.info["repo"]  # the pull request's worktree (on feat/x)
        cls.other = cls.tmp / "wt"  # another agent's worktree
        git(cls.repo, "worktree", "add", "-q", str(cls.other), "origin/dev")
        cls.src = cls.tmp / "src"
        cls.src.mkdir()
        (cls.src / "a.py").write_text("A\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def snap(self, remote="abc refs/heads/feat/x"):
        seen = []

        def ls_remote(repo, branch):
            seen.append(branch)
            return remote

        found = audit.snapshot(self.repo, self.src, ls_remote=ls_remote)
        self.assertEqual(seen, ["feat/x"], "the PR's own branch is asked for, by its checked-out name")
        return found

    def test_unchanged(self):
        before = self.snap()
        self.assertEqual((before["branch"], before["worktree"]), ("feat/x", str(self.repo)))
        self.assertEqual(audit.compare(before, self.snap()), [])

    def test_every_change_the_reviewer_could_make_is_seen(self):
        before = self.snap()
        (self.repo / "new.txt").write_text("x")
        self.addCleanup((self.repo / "new.txt").unlink)
        self.assertEqual(
            audit.compare(before, self.snap()), [f"files of the pull request's worktree {self.repo} changed"]
        )
        self.assertIn("feat/x on origin", audit.compare(before, self.snap("def refs/heads/feat/x"))[-1])
        dirty = self.snap()
        (self.repo / "new.txt").write_text("y")  # the same status line, other bytes
        self.assertEqual(len(audit.compare(dirty, self.snap())), 1)

    def test_other_worktrees_changing_never_void_a_round(self):
        before = self.snap()
        (self.other / "busy.txt").write_text("another agent at work")
        self.addCleanup((self.other / "busy.txt").unlink)
        git(self.other, "checkout", "-q", "--detach", self.info["commits"][0])
        self.addCleanup(git, self.other, "checkout", "-q", "--detach", self.info["dev"])
        third = self.tmp / "third"
        git(self.repo, "worktree", "add", "-q", str(third), "origin/dev")  # a new worktree appears too
        self.addCleanup(git, self.repo, "worktree", "remove", "--force", str(third))
        self.assertEqual(audit.compare(before, self.snap()), [])

    def test_src_edit_and_head_move(self):
        before = self.snap()
        (self.src / "a.py").write_text("B\n")
        self.addCleanup((self.src / "a.py").write_text, "A\n")
        git(self.repo, "checkout", "-q", "--detach", self.info["commits"][0])
        self.addCleanup(git, self.repo, "checkout", "-q", "feat/x")
        after = audit.snapshot(self.repo, self.src, branch="feat/x", ls_remote=lambda _r, _b: "abc refs/heads/feat/x")
        changes = audit.compare(before, after)
        self.assertTrue(any("src/" in c for c in changes))
        self.assertTrue(any(c.startswith("HEAD of the pull request") for c in changes))

    def test_the_real_remote_branch_is_read(self):
        origin = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", str(origin))
        self.addCleanup(shutil.rmtree, origin)
        git(self.repo, "remote", "add", "origin", str(origin))
        self.addCleanup(git, self.repo, "remote", "remove", "origin")
        self.assertEqual(audit.ls_remote_branch(self.repo, "feat/x"), "")
        git(self.repo, "push", "-q", "origin", "feat/x")
        head = git(self.repo, "rev-parse", "feat/x").strip()
        self.assertEqual(audit.ls_remote_branch(self.repo, "feat/x"), f"{head}\trefs/heads/feat/x")


if __name__ == "__main__":
    unittest.main()
