"""Scaffold's two modes (the fast one and RD_SCAFFOLD_FULL=nested) keep separate results in the branch record: a pass
in one never erases or stands for the other's, alternating them on an unchanged tree reuses both passes, a nested
failure stays visible in ship's gate after a fast-mode pass, and a record from before (the nested result kept under
``scaffold`` with a ``+nested`` digest) is read as the nested one. Also: a slow-check failure says honestly that PR
CI runs only the slow checks its changes select, never that CI will run that check.

Run alone: python -m unittest tests.retrodev.test_scaffold_modes
"""

import io

from retrodev import checks, config, output, repo, report, state

from tests.retrodev.fixture import GOOD_BODY, RepoCase, parallel, write

load_tests = parallel
NESTED = {"RD_SCAFFOLD_FULL": "nested"}
FAST_MODE = {"RD_SCAFFOLD_FULL": "1"}


class ScaffoldModes(RepoCase):
    def setUp(self):
        super().setUp()
        self.tree = self.worktree("chore/modes")
        self.ctx = config.Context.make(self.tree, output.Out(stream=io.StringIO()))

    def scaffold_runs(self) -> list[str]:
        """The modes scaffold ran in since the log was last cleared (each run of the stand-in check.py logs one)."""
        return [entry.get("mode") for entry in self.check_log() if "scaffold" in entry.get("names", [])]

    def run_scaffold(self, env: dict) -> int:
        try:
            return checks.run(self.ctx, ["scaffold"], env=env)
        except output.Failure as failure:
            return failure.code

    def record(self) -> dict:
        return state.load_branch(self.main, "chore/modes")

    def gate(self) -> dict:
        body = write(self.main, "notes/pr/modes.md", GOOD_BODY)
        _code, data = self.run_cli(
            "ship", "--title", "Modes", "--body", str(body), "--dry-run", cwd=self.tree, as_json=True
        )
        return next(gate for gate in data["gates"] if gate["name"] == "checks passed on this tree")

    def test_alternating_modes_on_an_unchanged_tree_reuse_both_passes(self):
        self.assertEqual(self.run_scaffold(FAST_MODE), 0)
        self.assertEqual(self.run_scaffold(NESTED), 0)
        self.assertEqual(self.scaffold_runs(), ["1", "nested"])
        self.clear_log()
        self.assertEqual(self.run_scaffold(FAST_MODE), 0)
        self.assertEqual(self.run_scaffold(NESTED), 0)
        self.assertEqual(self.scaffold_runs(), [], "both passes are still on these inputs: neither reruns")
        found = self.record()["checks"]
        self.assertEqual((found["scaffold"]["state"], found["scaffold_nested"]["state"]), ("ok", "ok"))
        self.assertFalse(found["scaffold"]["digest"].endswith("+nested"))
        self.assertTrue(found["scaffold_nested"]["digest"].endswith("+nested"))

    def test_a_nested_failure_stays_in_the_ship_gate_after_a_fast_mode_pass(self):
        self.assertEqual(self.run_cli("check", cwd=self.tree)[0], 0)  # the fast checks: the draft may ship
        self.fail_checks("scaffold")
        self.assertEqual(self.run_scaffold(NESTED), 1)
        self.fail_checks()
        self.assertEqual(self.run_scaffold(FAST_MODE), 0)
        found = self.record()["checks"]
        self.assertEqual((found["scaffold"]["state"], found["scaffold_nested"]["state"]), ("ok", "FAILED"))
        gate = self.gate()
        self.assertTrue(gate["ok"], gate)
        self.assertIn("not proven here: scaffold (nested) FAILED", gate["message"])
        self.assertIn("PR CI runs only the slow checks its changes select", gate["message"])
        self.clear_log()
        self.assertEqual(self.run_scaffold(NESTED), 0, "the failure is not cached: the nested run goes again")
        self.assertEqual(self.scaffold_runs(), ["nested"])
        self.assertNotIn("not proven here", self.gate()["message"])

    def test_an_older_record_s_nested_result_under_scaffold_is_read_as_the_nested_one(self):
        self.assertEqual(self.run_cli("check", cwd=self.tree)[0], 0)
        ids = repo.file_ids(self.tree)
        record = self.record()
        old = {"state": "FAILED", "digest": checks.input_digest(self.ctx, ids, "scaffold", True), "seconds": 1.0}
        record["checks"]["scaffold"] = old  # as the record was written before the modes had their own keys
        state.save_branch(self.main, record)
        self.assertIn("not proven here: scaffold (nested) FAILED", self.gate()["message"])
        self.assertEqual(self.run_scaffold(FAST_MODE), 0)  # never cached from the old nested entry
        self.assertEqual(self.scaffold_runs(), ["1"])
        found = self.record()["checks"]
        self.assertEqual(found["scaffold_nested"], old, "moved to its own key, not lost to the fast-mode pass")
        self.assertEqual(found["scaffold"]["state"], "ok")

    def test_report_finds_a_cached_nested_row_s_own_pass(self):
        self.assertEqual(self.run_scaffold(NESTED), 0)
        self.assertEqual(self.run_scaffold(NESTED), 0)  # cached now
        record = self.record()
        row = record["last_run"]["rows"][0]
        self.assertEqual((row["name"], row["key"], row["cached"]), ("scaffold", "scaffold_nested", True))
        self.assertEqual(report.cached_from(row, record)["passed_at"], record["checks"]["scaffold_nested"]["at"])

    def test_a_slow_failure_says_pr_ci_runs_only_what_its_changes_select(self):
        self.fail_checks("acceptance")
        code, out = self.run_cli("check", "--full", cwd=self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn(
            "failed: acceptance; the fast checks passed on this tree, so it may ship as a draft (PR CI runs only the "
            "slow checks its changes select)",
            out,
        )
        self.assertNotIn("CI runs the slow checks on its exact head", out)
        self.fail_checks()
        self.skip_checks("acceptance")
        code, out = self.run_cli("check", "acceptance", cwd=self.tree)
        self.assertEqual(code, 0, out)
        self.assertIn("skipped, so not proven here: acceptance (PR CI runs it only when its changes select it)", out)


class NestedScaffoldRoundFourteen(RepoCase):
    def test_the_nested_mode_comes_from_the_caller_and_keeps_its_own_pass(self):
        tree = self.worktree("fix/probe")
        self.commit(tree, "tests/repo/test_probe.py", "VALUE = 1\n")  # once a nested trigger: adds nothing now
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertNotIn("scaffold", [name for entry in self.check_log() for name in entry.get("names", [])])
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        self.clear_log()
        self.assertEqual(checks.run(ctx, ["scaffold"], env={"RD_SCAFFOLD_FULL": "nested"}), 0)
        self.assertEqual([entry.get("mode") for entry in self.check_log() if "scaffold" in entry["names"]], ["nested"])
        self.clear_log()
        checks.run(ctx, ["scaffold"], env={"RD_SCAFFOLD_FULL": "1"})  # the nested pass never stands for this one
        self.assertEqual([entry.get("mode") for entry in self.check_log() if "scaffold" in entry["names"]], ["1"])

    def test_a_fast_mode_pass_never_stands_for_the_nested_one_and_nested_has_its_own_budget(self):
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()))
        ids = {"a.py": "1"}
        self.assertNotEqual(checks.input_digest(ctx, ids, "scaffold"), checks.input_digest(ctx, ids, "scaffold", True))
        self.assertEqual(checks.input_digest(ctx, ids, "unit"), checks.input_digest(ctx, ids, "unit", True))
        self.assertIn("scaffold_nested", ctx.policy["checks"]["budgets"])
        self.assertGreater(checks.budget(ctx, "scaffold_nested"), checks.budget(ctx, "scaffold"))
        rows = [{"name": "scaffold", "state": "ok", "seconds": 120.0, "cached": False, "budget": "scaffold_nested"}]
        self.assertEqual(checks.budget_warnings(ctx, rows, None, False, {"scaffold_nested": 120.0}), [])
        self.assertEqual(checks.durations(rows, None, {}), {"scaffold_nested": 120.0})
