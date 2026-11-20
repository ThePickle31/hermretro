"""Friction the eighth round of fresh-agent trials found in the flow: the scaffold check's copy filled a small
$XDG_RUNTIME_DIR and its git assertions hid git's words; sync's 'dev removed this block' hint searched only page/
and backend/ (the block had moved into tests/support.py); a resolution that wrote new code into the merge passed
silently; plan approve in a taken-over test/x branch wrote no pull request body and check said nothing while the
body was missing; takeover was silent about a branch kind the repository does not name; the plan had no title
line for ship --title. Each test failed before its fix. The `new` kinds' fixes: test_trial_round_eight_new.py.

Run alone: python -m unittest tests.retrodev.test_trial_round_eight
"""

import tempfile
import unittest
from pathlib import Path

from retrodev import doctor, plan
from retrodev.gates import agent_hint  # the Made by hint after check's body line (round nine)

from tests.retrodev.fixture import FILLED_PLAN, RepoCase, git, parallel, write
from tests.retrodev.test_trial_round_six import line_with
from tests.retrodev.tree_copy import GIB, copy_base, git_ok

load_tests = parallel
HELPER = "def moving_helper():\n    return 2\n"
TESTS = "tests/backend/library/test_moving.py"


class TempSpace(unittest.TestCase):
    def test_the_copy_leaves_a_short_folder_under_1_gb_and_says_so(self):
        free = {"/short": GIB // 2}
        chosen, note = copy_base("/short", free=lambda path: free.get(path, 2 * GIB))
        self.assertIn(chosen, (tempfile.gettempdir(), "/tmp"))
        self.assertIn("/short has under 1 GB free: the tree's copy goes in", note)
        self.assertEqual(copy_base("/short", free=lambda path: 2 * GIB), ("/short", ""))

    def test_a_failed_git_command_shows_git_s_own_words(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(AssertionError) as raised:
                git_ok(self, Path(empty), {"PATH": "/usr/bin:/bin", "GIT_CEILING_DIRECTORIES": empty}, ["log"])
        self.assertIn("not a git repository", str(raised.exception))

    def test_doctor_warns_when_the_short_temp_folder_has_under_1_gb(self):
        low = doctor.space_item("/run/user/x", GIB // 2)
        self.assertEqual((low["ok"], low["warning"]), (True, True))
        self.assertIn("free space in /run/user/x", low["fix"])
        self.assertFalse(doctor.space_item("/run/user/x", 2 * GIB)["warning"])


class DoctorRun(RepoCase):
    def test_doctor_prints_the_space_warning_with_its_fix(self):
        self.fakes["tmp_free"] = 10
        _code, out = self.run_cli("doctor")
        self.assertIn("!!  short temp folder space: ", out)
        self.assertIn("FIX: free space in ", out)


class Sync(RepoCase):
    def test_a_block_moved_into_tests_support_is_found_by_the_hint_s_command(self):
        test = '"""Moving."""\n\n\n{helper}\n\ndef test_it():\n    assert moving_helper() == {value}\n'
        self.on_dev(TESTS, test.format(helper=HELPER, value=2), "A test helper")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/helper")
        self.commit(tree, TESTS, test.format(helper=HELPER.replace("2", "22"), value=22))
        self.on_dev("tests/support.py", HELPER, "The helper moves to tests/support.py")
        self.on_dev(TESTS, test.format(helper="", value=2).replace("\n\n\n\n\n", "\n\n\n"))  # dev's side: empty
        code, out = self.run_cli("sync", cwd=tree, as_json=True)
        self.assertEqual(code, 1, out)
        hint = "`git log -p origin/dev -Smoving_helper` finds where"
        self.assertIn(f"{TESTS}: dev removed this block; if it moved, {hint}", out["error"]["fix"])
        self.assertIn("+++ b/tests/support.py", git(tree, "log", "-p", "origin/dev", "-Smoving_helper"))
        before = git(tree, "log", "-p", "origin/dev", "-Smoving_helper", "--", "page", "backend")
        self.assertNotIn("tests/support.py", before, "the old hint's pathspec missed it")

    def conflicted(self) -> Path:
        self.on_dev("backend/library/both.py", "VALUE = 1\n", "Both")
        git(self.main, "fetch", "-q", "origin")
        tree = self.worktree("fix/both")
        self.commit(tree, "backend/library/both.py", "VALUE = 2\n")
        self.on_dev("backend/library/both.py", "VALUE = 3\n")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 1, out)
        return tree

    def test_a_resolution_with_lines_neither_side_had_gets_the_own_commit_warning(self):
        tree = self.conflicted()
        write(tree, "backend/library/both.py", "VALUE = 3\nEXTRA = 4\n")
        git(tree, "add", "backend/library/both.py")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "warning: the resolution adds 1 line(s) neither side had (backend/library/both.py): new work belongs in "
            "its own commit after sync (a resolution over 20 lines needs a full review round at land)",
            out,
        )

    def test_a_resolution_made_of_the_two_sides_warns_nothing(self):
        tree = self.conflicted()
        write(tree, "backend/library/both.py", "VALUE = 2\n")
        git(tree, "add", "backend/library/both.py")
        code, out = self.run_cli("sync", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("neither side had", out)


class Takeover(RepoCase):
    def pushed(self, branch: str) -> Path:
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", branch)
        self.commit(mate, "tests/backend/library/test_extra.py", "EXTRA = 1\n")
        git(mate, "push", "-q", "origin", branch)
        return self.base / "hermretro-wt" / branch.partition("/")[2]

    def test_a_test_branch_keeps_its_name_and_plan_approve_there_writes_its_body(self):
        tree = self.pushed("test/extra")
        code, out = self.run_cli("takeover", "test/extra")
        self.assertEqual(code, 0, out)
        note = line_with(out, "note: 'test' is not one of this repository's kinds")
        self.assertIn("test/extra keeps its name: ship, land and CI accept any work branch", note)
        self.assertIn("so keep it", note)
        self.assertNotIn("git branch -m", note)  # a rename would strand the branch's retrodev record
        self.new_plan("extra")
        code, out = self.run_cli("plan", "approve", "extra", "--words", "start", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertTrue((self.main / "notes/pr/extra.md").is_file(), out)

    def test_a_feat_branch_gets_no_kind_note(self):
        self.pushed("feat/extra")
        code, out = self.run_cli("takeover", "feat/extra")
        self.assertEqual(code, 0, out)
        self.assertNotIn("is not one of this repository's kinds", out)


class TitleAndBody(RepoCase):
    def test_the_plan_template_asks_for_a_title_and_present_tense(self):
        self.run_cli("plan", "new", "titled")
        text = (self.main / "notes/plans/titled.md").read_text()
        self.assertIn("Title: <!-- One plain sentence", text)
        self.assertIn("in the present tense ('X does Y')", text)
        self.assertEqual(plan.unfilled(FILLED_PLAN.format(topic="t")), [])

    def test_check_names_a_missing_body_and_check_status_and_ship_suggest_the_plan_s_title(self):
        tree = self.worktree("fix/nobody")
        path = self.main / "notes/plans/nobody.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            FILLED_PLAN.format(topic="nobody").replace("\n\n## Goal", "\n\nTitle: Nobody gets a body\n\n## Goal")
        )
        body = self.main / "notes/pr/nobody.md"
        self.run_cli("plan", "approve", "nobody", "--words", "start")
        body.unlink(missing_ok=True)  # start writes it; a branch made by hand has none
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            out.strip().splitlines()[-1],
            f"next: fill in the pull request body (missing: {body}; ship writes it from the template), then python "
            "tools/retrodev ship --title 'Nobody gets a body'" + agent_hint(None),
        )
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn("ship --title 'Nobody gets a body'", out)
        _code, out = self.run_cli("ship", "--dry-run", cwd=tree)
        self.assertIn("--title 'Nobody gets a body'", out)


if __name__ == "__main__":
    unittest.main()
