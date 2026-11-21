"""The round folder: a clean export, patches without generated files, and a filled-in brief."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests.retrodev.review.helpers import commit, git, make_repo

from retrodev.review import inputs


class Prepare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="retrodev-inputs-"))
        cls.info = make_repo(cls.tmp)
        cls.repo = cls.info["repo"]
        cls.root = cls.tmp / "reviews"
        cls.r1 = inputs.prepare(
            cls.repo,
            7,
            "HEAD",
            title="Use b",
            goal="Add b and use it.",
            mechanical=[cls.info["commits"][1]],
            root=cls.root,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_layout_and_export(self):
        r = self.r1
        self.assertEqual(r.dir, self.root / "7" / "round1")
        self.assertFalse((r.src / ".git").exists())
        self.assertEqual((r.src / "backend" / "c.py").read_text(), "from .b import B\n")
        self.assertTrue((r.src / "desktop" / "plugin.js").is_file())  # the export is the whole commit
        names = {p.name for p in r.review.iterdir()}
        self.assertEqual(len([n for n in names if n.startswith("commit-")]), 3)
        self.assertTrue({"brief.md", "commits.txt", "stat.txt", "diff.patch"} <= names)

    def test_generated_files_and_lockfiles_left_out(self):
        for patch in self.r1.review.glob("*.p*"):
            text = patch.read_text()
            for name in inputs.EXCLUDED:
                self.assertNotIn(name, text, patch.name)
        self.assertNotIn("plugin.js", (self.r1.review / "stat.txt").read_text())
        self.assertIn("backend/b.py", (self.r1.review / "diff.patch").read_text())

    def test_the_round_line_says_how_many_rounds_this_pull_request_gets(self):
        self.assertEqual(inputs.round_section(1, {}, {}), "THIS IS ROUND 1 of 3.")
        one = inputs.round_section(1, {}, {}, 1)
        self.assertTrue(one.startswith("THIS IS ROUND 1 of 1 (the last)."), one)
        self.assertIn("true severity", one)
        self.assertEqual(inputs.round_section(1, {}, {}, 2), "THIS IS ROUND 1 of 2.")
        self.assertTrue(inputs.round_section(2, {1: "x"}, {}, 2).startswith("THIS IS ROUND 2 of 2 (the last)."))

    def test_brief(self):
        brief = self.r1.brief.read_text()
        self.assertIn("pull request #7", brief)
        self.assertIn(str(self.r1.dir), brief)
        self.assertIn("Add b and use it.", brief)
        self.assertIn("ROUND 1 of 3", brief)
        self.assertIn("the WHOLE PR again", brief)
        mech = self.info["commits"][1][:7]
        self.assertRegex(brief, rf"Commits {mech} are mechanical")
        self.assertNotIn("$", brief.replace("$(", ""))  # every placeholder filled
        self.assertIn('"verdict": "clean" | "findings"', brief)
        self.assertEqual(len((self.r1.review / "commits.txt").read_text().splitlines()), 3)

    def test_round_two_has_earlier_findings_and_the_fixes(self):
        first = self.r1.sha
        git(self.repo, "checkout", "-q", "-b", "feat/fix", first)
        fix = commit(
            self.repo, "Fix round 1", {"backend/c.py": "from .b import B\nprint(B)\n", "desktop/plugin.js": "gen2\n"}
        )
        self.addCleanup(git, self.repo, "checkout", "-q", "feat/x")
        r = inputs.prepare(
            self.repo,
            7,
            fix,
            round_no=2,
            earlier={1: "Finding 0: c.py unused import"},
            last_reviewed=first,
            root=self.root,
        )
        self.assertEqual(
            (r.review / "round1-findings-and-answers.txt").read_text().strip(), "Finding 0: c.py unused import"
        )
        fixes = (r.review / "round1-fixes.patch").read_text()
        self.assertIn("print(B)", fixes)
        self.assertNotIn("plugin.js", fixes)
        self.assertNotIn("Use b", fixes)  # only the commits since the last round
        brief = r.brief.read_text()
        self.assertIn("ROUND 2 of 3", brief)
        self.assertIn("round1-fixes.patch", brief)
        self.assertTrue((self.root / "7" / "round1").is_dir())  # earlier rounds stay

    def test_root_inside_a_worktree_is_refused(self):
        with self.assertRaises(inputs.InputsError):
            inputs.prepare(self.repo, 9, "HEAD", root=self.repo / "scratch")

    def test_default_root_is_in_the_git_folder(self):
        self.assertEqual(inputs.reviews_root(self.repo), (self.repo / ".git").resolve() / "retrodev" / "reviews")
        self.assertEqual(inputs.main_checkout(self.repo), self.repo.resolve())
        # The default is inside the main checkout's folder but in .git, which git status never shows: allowed.
        prepared = inputs.prepare(self.repo, 9, "HEAD")
        self.assertTrue(prepared.dir.is_relative_to((self.repo / ".git").resolve()))


if __name__ == "__main__":
    unittest.main()
