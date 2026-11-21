"""check's fast gate: only the fast checks gate a draft push, whatever the branch changed; the slow ones run when
named or with --full, and one that fails or is skipped is said so and never counts as a pass.

Run alone: python -m unittest tests.retrodev.test_fast_gate
"""

import json

from retrodev import checks, state

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write

load_tests = parallel
FAST = ["unit", "bundle", "lint", "page", "scan"]


class FastGate(RepoCase):
    def test_a_branch_s_changes_add_no_slow_check(self):
        """Only the fast checks gate a draft push, whatever the branch changed: PR CI runs the slow ones its
        changes select. A template (scaffold's old trigger) and a moved backend file (acceptance and the installs') add none."""
        tree = self.worktree("chore/move")
        write(tree, "tools/retrodev/templates/tool/tool.py.tmpl", "# changed\n")
        git(tree, "mv", "backend/hermes/glue.py", "backend/hermes/seam.py")
        git(tree, "add", "-A")
        git(tree, "commit", "-q", "-m", "Move the glue")
        code, data = self.run_cli("check", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual([entry["names"] for entry in self.check_log()], [FAST])
        self.assertEqual([row["name"] for row in data["checks"]], FAST)
        self.assertTrue(data["tree_passed"])
        self.assertNotIn("adding", json.dumps(data))

    def test_slow_checks_run_when_named_or_with_full(self):
        tree = self.worktree("chore/move")
        git(tree, "mv", "backend/hermes/glue.py", "backend/hermes/seam.py")
        git(tree, "commit", "-q", "-m", "Move the glue")
        code, data = self.run_cli("check", "acceptance", "clean_install", "update", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        log = self.check_log()
        self.assertEqual(log[0]["names"], ["acceptance"])
        self.assertEqual(log[0]["tmpdir"], checks.short_tmp())
        self.assertIsNone(log[0]["deps"], "acceptance uses the toolchain setup put in place")
        head = git(tree, "rev-parse", "HEAD").strip()
        self.assertEqual(log[1:], [{"script": [], "head": head}, {"script": ["--update-from"], "head": head}])
        self.assertFalse(data["tree_passed"], "the fast checks never ran here: no pass to ship on")
        self.assertEqual(data["unpassed"], FAST)
        self.clear_log()
        code, data = self.run_cli("check", "--full", "--again", cwd=tree, as_json=True)
        self.assertEqual(code, 0, data)
        rest = [name for name in FAST if name != "lint"] + ["scaffold"]  # lint first: scaffold waits for it
        self.assertEqual([entry["names"] for entry in self.check_log()[:2]], [["lint"], rest])
        self.assertEqual([row["name"] for row in data["checks"]], FAST + ["scaffold", "acceptance", "clean_install"])
        self.assertTrue(data["tree_passed"])

    def test_a_slow_check_that_fails_or_is_skipped_is_said_so_and_never_counts(self):
        tree = self.worktree()
        self.fail_checks("acceptance")
        code, out = self.run_cli("check", "--full", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("failed: acceptance; the fast checks passed on this tree, so it may ship as a draft", out)
        self.assertIn("passed_tree", state.load_branch(self.main, "docs/tidy"), "the fast checks passed")
        body = write(self.main, "notes/pr/tidy.md", GOOD_BODY)
        code, data = self.run_cli("ship", "--title", "Tidy", "--body", str(body), "--dry-run", cwd=tree, as_json=True)
        gate = next(gate for gate in data["gates"] if gate["name"] == "checks passed on this tree")
        self.assertTrue(gate["ok"], data)
        self.assertIn("not proven here: acceptance FAILED", gate["message"])
        self.fail_checks()
        self.skip_checks("acceptance")
        code, out = self.run_cli("check", "acceptance", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("0 of 1 passed", out)
        self.assertIn("skipped, so not proven here: acceptance", out)
        self.assertNotIn("all 1 passed", out)

    def test_a_named_rerun_on_a_tree_whose_other_inputs_changed_records_no_pass_and_names_them(self):
        tree = self.worktree()
        self.assertEqual(self.run_cli("check", cwd=tree)[0], 0)
        self.commit(tree, "tests/repo/test_probe.py", "PROBE = 1\n")  # unit, lint and scan read it
        code, out = self.run_cli("check", "unit", cwd=tree)
        self.assertEqual(code, 0, out)
        self.assertIn("not passed on this tree yet: lint, scan", out)
        self.assertNotIn("passed_tree", state.load_branch(self.main, "docs/tidy"))
        self.assertEqual(self.run_cli("check", cwd=tree)[0], 0)  # the bare check runs only what is missing
        self.assertIn("passed_tree", state.load_branch(self.main, "docs/tidy"))

    def test_a_skipped_fast_check_is_no_pass(self):
        tree = self.worktree()
        self.skip_checks("page")
        code, out = self.run_cli("check", cwd=tree)
        self.assertEqual(code, 1, out)
        self.assertIn("skipped (a tool is missing): page", out)
        self.assertNotIn("passed_tree", state.load_branch(self.main, "docs/tidy"))
