"""Friction the ninth round of fresh-agent trials found outside `new`: an over-long title reached ship (the plan's
Title: line was skipped without a word, and ship's FIX gave a generic example); the Made by line named Hermes and
nothing said how to name the real agent; sync's FIX had no word for code dev rewrote, and the takeover hint showed
the diff but not the commits; a base tree failing page made scaffold fail; failed runs fed the time budgets; the
README's long rows were cut by agents' readers. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_nine
"""

import argparse
import importlib.util
import json
import io
import subprocess
import threading
import unittest
from pathlib import Path
from unittest import mock

from retrodev import checks, config, gates, output, plan, status, sync

from tests.retrodev import test_scaffold_tree as tree_test
from tests.retrodev.fixture import FILLED_PLAN, RepoCase, git, parallel, write

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]
LONG = "Show how many builds each game of the library has had, newest first, on the Home page's shelf and in Game"  # 105 characters


def titled(topic: str, title: str) -> str:
    return FILLED_PLAN.format(topic=topic).replace("\n\n## Goal", f"\n\nTitle: {title}\n\n## Goal")


class Title(RepoCase):
    def test_the_gate_names_the_problem_and_the_length(self):
        self.assertEqual(len(LONG), 105)
        gate = gates.title_gate(LONG)
        self.assertIn("the title is 105 characters; the limit is 100", gate.message)
        self.assertIn("shorten it to 100 characters or fewer (yours is 105)", gate.fix)
        self.assertNotIn("One plain sentence saying", gate.fix)
        self.assertIn("drop the trailing period", gates.title_gate("Keep the goalie in goal.").fix)
        both = gates.title_gate(LONG + ".")
        self.assertIn("drop the trailing period, and shorten it", both.fix)
        self.assertTrue(gates.title_gate("Keep the goalie in goal").ok)

    def test_the_template_says_the_limit_and_where_files_go_points_to_dry_run(self):
        self.assertIn("Title: <!-- One plain sentence, at most 100 characters, no trailing period", plan.TEMPLATE)
        where = plan.TEMPLATE.split("## Where files go")[1].split("##")[0]
        self.assertIn("--dry-run", where)

    def test_plan_approve_runs_the_title_gate_on_the_plan_s_title_line(self):
        path = self.main / "notes/plans/longer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(titled("longer", LONG))
        code, out = self.run_cli("plan", "approve", "longer", "--words", "start")
        self.assertEqual(code, 1, out)
        self.assertIn("the plan's title: the title is 105 characters; the limit is 100", out)
        self.assertIn("shorten it to 100 characters or fewer (yours is 105)", out)
        path.write_text(titled("longer", "Show every build."))
        code, out = self.run_cli("plan", "approve", "longer", "--words", "start")
        self.assertEqual(code, 1, out)
        self.assertIn("drop the trailing period", out)
        path.write_text(titled("longer", "Show every build"))
        code, out = self.run_cli("plan", "approve", "longer", "--words", "start")
        self.assertEqual(code, 0, out)

    def test_check_status_and_ship_say_why_they_skip_the_plan_s_title(self):
        tree = self.worktree("feat/longer")
        path = self.main / "notes/plans/longer.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(titled("longer", "Show every build"))
        self.assertEqual(self.run_cli("plan", "approve", "longer", "--words", "start")[0], 0)
        path.write_text(titled("longer", LONG))  # edited after the approval
        self.commit(tree, "docs/guide.md", "# longer\n")
        why = "the plan's title is 105 characters; the limit is 100"
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn(why, out.strip().splitlines()[-1])
        _code, out = self.run_cli("status", cwd=tree)
        self.assertIn(why, out)
        code, out = self.run_cli("ship", "--dry-run", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn(why, out)


class MadeBy(RepoCase):
    def test_start_and_check_say_how_to_name_the_agent(self):
        self.commit(
            self.main, ".github/pull_request_template.md", (ROOT / ".github/pull_request_template.md").read_text()
        )
        git(self.main, "push", "-q", "origin", "dev")
        self.new_plan("goalie")
        self.run_cli("plan", "approve", "goalie", "--words", "start")
        code, out = self.run_cli("start", "feat/goalie", "--no-setup")
        self.assertEqual(code, 0, out)
        self.assertIn("RETRODEV_AGENT='<agent, model>'", out)
        tree = self.base / "hermretro-wt" / "goalie"
        self.commit(tree, "docs/guide.md", "# goalie\n")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("RETRODEV_AGENT='<agent, model>'", out.strip().splitlines()[-1])
        body = self.main / "notes/pr/goalie.md"
        body.write_text(
            body.read_text().replace("Made by an agent (Hermes) for the owner.", "Made by an agent (Codex) for x.")
        )
        _code, out = self.run_cli("check", cwd=tree)
        self.assertNotIn("RETRODEV_AGENT", out.strip().splitlines()[-1], "a named agent needs no hint")

    def test_the_hint_is_for_the_generic_line_only(self):
        self.assertIn("RETRODEV_AGENT", gates.agent_hint("Made by an agent (Hermes) for @someone."))
        self.assertEqual(gates.agent_hint("Made by an agent (Claude Code, Opus) for @someone."), "")


class SyncAndTakeover(RepoCase):
    def test_the_conflict_fix_says_to_redo_a_change_on_dev_s_rewrite(self):
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()))
        fix = sync.resume_fix(ctx)
        self.assertIn(
            "if dev rewrote the code your side changed, take dev's lines in the merge and redo your change on top "
            "in its own commit after sync",
            fix,
        )

    def test_the_read_first_hint_names_dev_s_commits_too(self):
        said = status.read_first(["backend/library/core.py"], "origin/dev")
        self.assertIn("`git diff HEAD...origin/dev -- backend/library/core.py`", said)
        self.assertIn("`git log --oneline HEAD..origin/dev -- backend/library/core.py`", said)


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
        self.assertEqual(ctx.policy["checks"]["budgets"]["scaffold"], 58)  # round eleven: idle 48.3 s plus 20%
        policy = (ROOT / "tools/retrodev/policy.toml").read_text()
        self.assertIn(
            "scaffold = 58           # retrodev new on a copy of the tree: the idle measure (48.3 s) plus 20%", policy
        )


class PageFirst(RepoCase):
    def test_a_base_tree_that_fails_page_reports_scaffold_skipped(self):
        tree = self.worktree("feat/pages")
        self.commit(tree, "tools/retrodev/scaffold.py", "# changed\n")  # scaffold is due
        self.fail_checks("page")
        self.skip_checks("scaffold")
        write(self.base, "skip-detail", checks.PAGE_FIRST)
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("scaffold: skipped: the tree fails page (fix page first)", out)
        self.assertNotIn("skipped (a tool is missing)", out)

    def test_page_s_recorded_result_decides_without_running_page_again(self):  # review round 2, 0
        tree = self.worktree("feat/pages-first")
        self.commit(tree, "tools/retrodev/scaffold.py", "# changed\n")  # scaffold is due
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

    def test_check_py_and_the_scaffold_test_say_page_first(self):
        self.assertEqual(tree_test.PAGE_FIRST, checks.PAGE_FIRST.removeprefix("skipped: "))


class WholeScaffoldCheckFirst(unittest.TestCase):
    """Review round 2 of #64, 0: check.py scaffold looks at the tree's page suite once, before the scaffold module
    runs at all (this invocation's own page row when it has one, never a second run): a failing one skips the whole
    check, a passing one goes to the module in RD_SCAFFOLD_BASE so it does not run it again."""

    def check_py(self):
        spec = importlib.util.spec_from_file_location("check_py_probe_nine_first", ROOT / "tools/check.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not (ROOT / "tools/npm/node_modules").is_dir():
            self.skipTest("the npm tools are not set up here")
        return module

    def scaffold(self, module, args, page=None):
        ran = []

        def run(command, **kwargs):
            ran.append(kwargs.get("env", {}))
            return subprocess.CompletedProcess(command, 0, "", "Ran 12 tests\n\nOK\n")

        with (
            mock.patch.object(module, "run", run),
            mock.patch.object(module, "ruff_missing", lambda: None),
            mock.patch.object(module, "need", lambda tool: tool),
            mock.patch.dict(module.CHECKS, {"page": page or (lambda _args: "fine")}),
        ):
            try:
                return module.check_scaffold(args), ran
            except module.Skip as skip:
                return str(skip), ran

    def invocation(self, page_state: str):
        done = threading.Event()
        done.set()
        return argparse.Namespace(strict=False, finished={"page": done}, states={"page": page_state})

    def test_a_page_row_of_the_same_run_that_failed_skips_the_whole_check(self):
        module = self.check_py()
        said, ran = self.scaffold(module, self.invocation("FAILED"), page=self.fail)
        self.assertEqual(said.splitlines()[0], "skipped: the tree fails page (fix page first)")
        self.assertIn("FIX: python tools/check.py page", said)
        self.assertEqual(ran, [], "the scaffold module does not run at all")

    def test_a_page_row_of_the_same_run_that_passed_is_reused(self):
        module = self.check_py()
        said, ran = self.scaffold(module, self.invocation("ok"), page=self.fail)  # page itself would fail: unused
        self.assertEqual(said, "retrodev new of every kind passes the real checks")
        self.assertEqual([env.get("RD_SCAFFOLD_BASE") for env in ran], ["page"])

    def test_without_a_page_row_check_py_runs_page_once_itself(self):
        module = self.check_py()
        calls = []

        def page(_args):
            calls.append(1)
            raise AssertionError("not ok 1 - rdprobe")

        said, ran = self.scaffold(module, argparse.Namespace(strict=False), page=page)
        first, shown = said.splitlines()[:2]
        self.assertEqual((first, calls, ran), ("skipped: the tree fails page (fix page first)", [1], []))
        self.assertEqual(shown, "not ok 1 - rdprobe", "the failure shows, not only that there was one")

    @staticmethod
    def fail(_args):
        raise AssertionError("page ran a second time")


class Readme(unittest.TestCase):
    def test_no_line_of_the_readme_or_the_reference_runs_past_600_characters(self):
        for name in ("README.md", "REFERENCE.md"):
            text = (ROOT / "tools/retrodev" / name).read_text()
            long = [(number, len(line)) for number, line in enumerate(text.splitlines(), 1) if len(line) > 600]
            self.assertEqual(long, [], name)
        self.assertLess(len((ROOT / "tools/retrodev/README.md").read_text()), 8000, "the README stays the entry")

    def test_the_readme_keeps_the_entry_and_the_reference_is_a_listed_document(self):
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        self.assertIn("## Quick path", readme)
        self.assertIn("## The flow, from plan to merge", readme)
        self.assertIn("by default a `<checkout>-wt` folder next to the checkout", readme)
        self.assertIn("`python tools/retrodev config list` shows it", readme)
        self.assertIn("## Releases", readme)  # AGENTS.md and RELEASE-CHECKLIST.md point at it
        self.assertIn('"tools/retrodev/REFERENCE.md" = ', (ROOT / "tools/layout.toml").read_text())
        reference = (ROOT / "tools/retrodev/REFERENCE.md").read_text()
        for kind in ("feature", "rpc", "tool", "event", "listener", "page", "tab", "slot", "contribution"):
            self.assertIn(f"### `new {kind} ", reference, kind)  # one sub-section per kind


if __name__ == "__main__":
    unittest.main()
