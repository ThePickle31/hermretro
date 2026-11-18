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
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="retrodev-snap-"))
        cls.info = make_repo(cls.tmp)
        cls.repo = cls.info["repo"]
        cls.wt = cls.tmp / "wt"
        git(cls.repo, "worktree", "add", "-q", str(cls.wt), "origin/dev")
        cls.src = cls.tmp / "src"
        cls.src.mkdir()
        (cls.src / "a.py").write_text("A\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def snap(self, remote="abc refs/heads/dev"):
        return audit.snapshot(self.repo, self.src, ls_remote=lambda _repo: remote)

    def test_unchanged(self):
        before = self.snap()
        self.assertEqual(len(before["heads"]), 2)
        self.assertEqual(audit.compare(before, self.snap()), [])

    def test_every_change_is_seen(self):
        before = self.snap()
        (self.wt / "new.txt").write_text("x")
        self.addCleanup((self.wt / "new.txt").unlink)
        self.assertEqual(len(audit.compare(before, self.snap())), 1)
        self.assertIn("branches on origin", audit.compare(before, self.snap("def refs/heads/dev"))[-1])

    def test_busy_worktree_is_left_out_and_recorded(self):
        before = audit.snapshot(self.repo, self.src, lambda _r: "r", skip=[self.wt])
        (self.wt / "busy.txt").write_text("another agent at work")
        self.addCleanup((self.wt / "busy.txt").unlink)
        git(self.wt, "checkout", "-q", "--detach", self.info["commits"][0])
        self.addCleanup(git, self.wt, "checkout", "-q", "--detach", self.info["dev"])
        after = audit.snapshot(self.repo, self.src, lambda _r: "r", skip=[self.wt])
        self.assertEqual(audit.compare(before, after), [])
        self.assertEqual(before["skipped"], [str(self.wt.resolve())])
        self.assertEqual(list(before["heads"]), [str(self.repo)])

    def test_src_edit_and_head_move(self):
        before = self.snap()
        (self.src / "a.py").write_text("B\n")
        git(self.wt, "checkout", "-q", "--detach", self.info["commits"][0])
        changes = audit.compare(before, self.snap())
        self.assertTrue(any("src/" in c for c in changes))
        self.assertTrue(any(c.startswith("HEAD of worktree") for c in changes))
        (self.src / "a.py").write_text("A\n")
        git(self.wt, "checkout", "-q", "--detach", self.info["dev"])


if __name__ == "__main__":
    unittest.main()
