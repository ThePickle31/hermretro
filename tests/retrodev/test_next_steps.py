"""Next-step lines that fit the state: plan approve with a branch already under the plan, answer on a merged or an
already-shipped pull request, the hint after land or gc removed the worktree a command started in, and report's
cached checks.

Run alone: python -m unittest tests.retrodev.test_next_steps
"""

import json
import re
import unittest

from retrodev import state
from retrodev.review import records

from tests.retrodev.fixture import RepoCase, git, parallel
from tests.retrodev.landing import PR, LandCase, reply

load_tests = parallel
ROOT = (".git", "retrodev", "reviews")


class PlanApprove(RepoCase):
    def test_a_branch_already_under_the_plan_is_pointed_at_instead_of_a_new_start(self):
        self.run_cli("plan", "new", "big")
        tree = self.worktree("fix/part")
        record = state.load_branch(self.main, "fix/part")
        record["plan"] = "big"  # start fix/part --plan big, or plan link big
        state.save_branch(self.main, record)
        code, data = self.run_cli("plan", "approve", "big", "--words", "start", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["linked"], [{"branch": "fix/part", "worktree": str(tree)}])
        code, out = self.run_cli("plan", "approve", "big", "--words", "start")
        self.assertIn(f"next: fix/part already works under it: cd {tree} && python tools/retrodev status", out)
        self.assertIn("python tools/retrodev start <kind>/<topic> --plan big", out)
        self.assertNotIn("start feat/big", out)

    def test_a_plan_without_branches_still_says_start(self):
        self.run_cli("plan", "new", "alone")
        code, out = self.run_cli("plan", "approve", "alone", "--words", "start")
        self.assertEqual(code, 0, out)
        self.assertIn("next: python tools/retrodev start feat/alone", out)


class Answer(LandCase):
    def round_with_a_finding(self) -> None:
        body = json.loads(reply("x", 1).splitlines()[1])
        root = self.main.joinpath(*ROOT)
        records.add_round(root, 12, {"round": 1, "sha": self.info["headRefOid"], "result": body, "void": False})

    def test_on_a_merged_pull_request_the_next_step_is_the_summary(self):
        self.open_pr()
        self.round_with_a_finding()
        self.info["state"] = "MERGED"
        self.answer_view()
        code, data = self.run_cli("answer", PR, "1", "0", "Fixed in abc: the test", as_json=True)
        self.assertEqual((code, data["stage"]), (0, "merged"), data)
        code, out = self.run_cli("answer", PR, "1", "0", "Fixed in abc: the test")
        self.assertIn("next: python tools/retrodev summary 12", out)
        self.assertNotIn("commit, check and ship", out)

    def test_fixes_not_shipped_then_shipped(self):
        tree = self.open_pr()
        self.round_with_a_finding()
        self.commit(tree, "docs/value.md", "# Two\n", "Fix the finding")  # committed, not shipped yet
        code, out = self.run_cli("answer", PR, "1", "0", "Fixed: docs/value.md")
        self.assertEqual(code, 0, out)
        self.assertIn("next: commit, check and ship the fixes, then python tools/retrodev land 12", out)
        self.publish(tree)  # shipped: pushed, the pull request's head moved past the reviewed one
        code, out = self.run_cli("answer", PR, "1", "0", "Fixed: docs/value.md")
        self.assertIn("next: python tools/retrodev land 12", out)
        self.assertNotIn("commit, check and ship", out)


class RemovedShell(LandCase):
    def test_land_started_in_the_worktree_says_where_to_cd(self):
        tree = self.open_pr()
        code, out = self.run_cli("land", PR, "--ci-timeout", "0", "--no-review", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertFalse(tree.exists())
        self.assertIn(f"your shell may still be in {tree} (removed): cd {self.main}", out)
        self.assertIn(f"next: cd {self.main} && python tools/retrodev summary 12", out)


class GCShell(RepoCase):
    def test_gc_says_it_only_for_the_folder_it_started_in(self):
        tree = self.worktree("docs/done")
        self.commit(tree, "docs/done.md", "# Done\n")
        git(self.main, "push", "-q", "origin", "docs/done")
        git(tree, "push", "-q", "origin", "HEAD:dev")  # merged into dev
        code, data = self.run_cli("gc", cwd=self.main, as_json=True)
        self.assertEqual([row["branch"] for row in data["removed"]], ["docs/done"])
        self.assertNotIn("cd", data)
        other = self.worktree("docs/again")
        self.commit(other, "docs/again.md", "# Again\n")
        git(self.main, "push", "-q", "origin", "docs/again")
        git(other, "push", "-q", "origin", "HEAD:dev")
        code, out = self.run_cli("gc", cwd=other / "docs")
        self.assertEqual(code, 0, out)
        self.assertIn(f"your shell may still be in {other} (removed): cd {self.main}", out)


class Report(RepoCase):
    def test_a_cached_check_says_when_it_passed_and_how_long_it_took(self):
        tree = self.worktree("chore/look")
        self.commit(tree, "docs/guide.md", "# Better\n")
        self.run_cli("check", "unit", cwd=tree)
        self.run_cli("check", "unit", cwd=tree)  # cached now
        code, data = self.run_cli("report", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        row = next(row for row in data["checks"] if row["name"] == "unit")
        self.assertTrue(row["cached"])
        self.assertEqual(row["passed_at"], state.load_branch(self.main, "chore/look")["checks"]["unit"]["at"])
        code, out = self.run_cli("report", cwd=tree)
        self.assertRegex(out, r"unit +cached \(passed \d{4}-\d\d-\d\dT[\d:]+[+-]\d{4}, took 0\.1 s\)")
        self.assertIsNone(re.search(r"unit +cached\n", out))


if __name__ == "__main__":
    unittest.main()
