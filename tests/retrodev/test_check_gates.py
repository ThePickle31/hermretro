"""The trial rounds' regressions for this area (RoundFive, RoundFour, RoundNine, RoundThree, RoundTwo), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_check_gates
"""

from pathlib import Path
import retrodev
from tests.retrodev.fixture import RepoCase, parallel, write
from tests.retrodev.fixture import GOOD_BODY
import io
import re
from retrodev import checks, config, output, repo, state
import json

load_tests = parallel

ROOT = Path(retrodev.__file__).resolve().parents[2]

TITLE = "Make the goalie work"


def line_with(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


class Check(RepoCase):
    def test_a_scaffold_skipped_for_a_failing_unit_suite_says_so(self):
        tree = self.worktree("chore/templates")
        self.commit(tree, "tools/retrodev/templates/tool/tool.py.tmpl", "# changed\n")
        self.skip_checks("scaffold")
        (self.base / "skip-detail").write_text("skipped: the tree fails unit (fix unit first)")
        code, out = self.run_cli("check", "scaffold", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("scaffold: skipped: the tree fails unit (fix unit first)", out)
        self.assertNotIn("a tool is missing", out)


class CheckRoundFour(RepoCase):
    def test_scaffold_does_not_run_when_lint_fails_in_the_same_run(self):
        tree = self.worktree("chore/lint")
        self.fail_checks("lint")
        code, out = self.run_cli("check", "lint", "scaffold", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertEqual([entry["names"] for entry in self.check_log()], [["lint"]], "scaffold never started")
        self.assertIn("skipped  scaffold", out)
        self.fail_checks()
        self.clear_log()
        self.run_cli("check", "lint", "scaffold", cwd=tree)
        self.assertEqual([entry["names"] for entry in self.check_log()], [["lint"], ["scaffold"]])


class Budgets(RepoCase):
    def test_only_passing_runs_count(self):
        tree = self.worktree()
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        failed = [{"name": "scaffold", "state": "FAILED", "seconds": 90.0, "cached": False}]
        last = checks.durations(failed, None, {"scaffold": 30.0})
        self.assertEqual(last["scaffold"], 30.0, "a failed run measures nothing")
        self.assertEqual(checks.budget_warnings(ctx, failed, None, False, {"scaffold": 90.0}), [])
        slow = [{"name": "scaffold", "state": "ok", "seconds": 65.0, "cached": False}]
        self.assertEqual(len(checks.budget_warnings(ctx, slow, None, False, {"scaffold": 60.0})), 1)


class PageFirst(RepoCase):
    def test_a_base_tree_that_fails_page_reports_scaffold_skipped(self):
        tree = self.worktree("feat/pages")
        self.commit(tree, "tools/retrodev/scaffold.py", "# changed\n")  # scaffold is due
        self.fail_checks("page")
        self.skip_checks("scaffold")
        write(self.base, "skip-detail", checks.PAGE_FIRST)
        code, out = self.run_cli("check", "--full", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("scaffold: skipped: the tree fails page (fix page first)", out)
        self.assertNotIn("skipped (a tool is missing)", out)

    def test_page_s_recorded_result_decides_without_running_page_again(self):  # review round 2, 0
        tree = self.worktree("feat/pages-first")
        self.commit(tree, "tools/retrodev/scaffold.py", "# changed\n")
        self.fail_checks("page")
        self.run_cli("check", cwd=tree)
        before = len(self.check_log())
        code, out = self.run_cli("check", "scaffold", "--again", cwd=tree)  # page's recorded failure, these inputs
        self.assertEqual(code, 1, out)
        self.assertIn("scaffold: skipped: the tree fails page (fix page first)", out)
        self.assertNotIn("scaffold", json.dumps(self.check_log()[before:]), "scaffold did not run")
        self.fail_checks()
        self.run_cli("check", "page", cwd=tree)
        before = len(self.check_log())
        self.run_cli("check", "scaffold", "--again", cwd=tree)  # page's recorded pass: check.py does not rerun it
        [entry] = [e for e in self.check_log()[before:] if "scaffold" in e.get("names", [])]
        self.assertIn("page", entry["base"].split(","))


class Status(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def feat(self, topic="goalie"):
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        tree = self.worktree(f"feat/{topic}")
        record = state.load_branch(self.main, f"feat/{topic}")
        state.save_branch(self.main, {**record, "plan": topic})
        self.commit(tree, "docs/guide.md", f"# {topic}\n")
        self.passed(tree, f"feat/{topic}")
        return tree

    def test_a_dry_run_stopped_by_the_base_gate_is_recorded_as_failed(self):
        tree = self.feat()
        body = write(self.main, "notes/pr/goalie.md", GOOD_BODY)
        answer = [{"number": 12, "url": "u", "baseRefName": "main"}]  # opened by hand into main
        self.gh.answers[("pr", "list")] = (0, json.dumps(answer), "")
        code, out = self.run_cli("ship", "--title", TITLE, "--body", str(body), "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("into main", out)
        self.assertFalse(state.load_branch(self.main, "feat/goalie")["dry_run"]["ok"])
        _code, out = self.run_cli("status", cwd=tree)
        self.assertNotIn("dry-run passed", out)
        self.assertIn("(the body passes ship's body gate)", line_with(out, "next:"), out)


class CheckRoundThree(RepoCase):
    def test_scaffold_on_a_tree_that_fails_lint_is_skipped_not_a_rerun_fix(self):
        tree = self.worktree("chore/lint")
        self.fail_checks("lint", "scaffold")
        code, out = self.run_cli("check", "lint", "scaffold", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("scaffold: skipped: the tree fails lint (fix lint first)", out)
        self.assertNotIn("FIX: fix scaffold", out)
        self.assertIn("FIX: fix lint", out)
        code, out = self.run_cli("check", "scaffold", cwd=tree)  # lint's recorded failure, on these very inputs
        self.assertEqual(code, 1, out)
        self.assertIn("scaffold: skipped: the tree fails lint (fix lint first)", out)
        self.assertNotIn("FIX: fix scaffold", out)
        self.fail_checks("scaffold")
        self.run_cli("check", "lint", cwd=tree)
        _code, out = self.run_cli("check", "scaffold", cwd=tree)  # lint passes now: scaffold's own failure shows
        self.assertIn("FIX: fix scaffold", out)


class Flow(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def feat(self, topic="goalie"):
        self.new_plan(topic)
        self.run_cli("plan", "approve", topic, "--words", "start")
        tree = self.worktree(f"feat/{topic}")
        record = state.load_branch(self.main, f"feat/{topic}")
        state.save_branch(self.main, {**record, "plan": topic})
        self.commit(tree, "docs/guide.md", f"# {topic}\n")
        self.passed(tree, f"feat/{topic}")
        return tree

    def test_a_check_warns_only_on_the_second_run_over_budget(self):
        tree = self.worktree()
        policy = (tree / "tools/retrodev/policy.toml").read_text()
        policy = re.sub(r"(?m)^(fast_total|unit|lint|scan|default) = \d+$", r"\1 = 0.01", policy)
        self.commit(tree, "tools/retrodev/policy.toml", policy, "Tiny budgets")
        code, out = self.run_cli("check", "--again", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("warning:", out, "one run over budget says nothing")
        self.assertEqual(state.load_branch(self.main, "docs/tidy")["durations"]["unit"], 0.1)
        code, out = self.run_cli("check", "--again", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("warning: unit took 0.1 s, over its 0.01 s budget twice in a row", out)
