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


class AcceptanceInputsRoundTwenty(RepoCase):
    def checked(self, tree, *, cached: bool, code: int = 0, slow: tuple = ("acceptance",)) -> dict:
        """The fast checks (``code``: their exit), then the slow ones by name, as an agent runs them: the second
        run's data (its tree_passed is still the fast checks')."""
        self.clear_log()
        got, data = self.run_cli("check", cwd=tree, as_json=True)
        self.assertEqual(got, code, data)
        got, data = self.run_cli("check", *slow, cwd=tree, as_json=True)
        self.assertEqual(got, 0, data)
        ran = [name for entry in self.check_log() for name in entry.get("names", [])]
        self.assertEqual("acceptance" not in ran, cached, ran)
        row = next(row for row in data["checks"] if row["name"] == "acceptance")
        self.assertEqual(row["cached"], cached, row)
        return data

    def shipped(self, tree) -> list[str]:
        body = write(self.base, "body.md", GOOD_BODY)
        _code, data = self.run_cli(
            "ship", "--title", "Move the glue", "--body", str(body), "--dry-run", cwd=tree, as_json=True
        )
        return [gate["name"] for gate in data["gates"] if not gate["ok"]]

    def test_a_retrodev_test_edit_keeps_the_acceptance_pass_and_the_tree_may_ship(self):
        tree = self.worktree("chore/move")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", "Change the core")
        self.assertTrue(self.checked(tree, cached=False)["tree_passed"])
        self.commit(tree, "tests/retrodev/test_probe.py", "PROBE = 1\n", "Add a retrodev test")
        data = self.checked(tree, cached=True)
        self.assertTrue(data["tree_passed"], data)
        self.assertEqual(
            self.check_log()[0]["names"], ["unit", "lint", "scan"], "the fast checks that read it still run"
        )
        self.assertEqual(self.shipped(tree), [], "the ship gate takes the tree whose pass reused acceptance")
        write(tree, "tests/retrodev/test_probe.py", "PROBE = 2\n")  # uncommitted: the other gates still hold
        self.assertIn("committed and clean", self.shipped(tree))
        git(tree, "commit", "-q", "-am", "Change the probe")
        self.fail_checks("unit")
        data = self.checked(tree, cached=True, code=1)
        self.assertFalse(data["tree_passed"], "a cached acceptance pass never outweighs a failure")
        self.assertIn("checks passed on this tree", self.shipped(tree))

    def test_every_file_the_real_engine_run_may_read_takes_its_pass_back(self):
        tree = self.worktree("chore/move")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", "Change the core")
        self.checked(tree, cached=False)
        for name in (
            "backend/library/core.py",  # the backend, broker and player it runs
            "tests/acceptance/broker_acceptance.py",  # the suite itself
            "tests/support.py",  # shared test helpers
            "tests/retrodev.py",  # beside the folder, not in it
            "tools/ci/prepare_toolchain.py",  # the toolchain
            "tools/check.py",  # the runner
            "tools/retrodev/checks.py",  # what decides and runs it
            "tools/retrodev/policy.toml",  # its inputs and their exceptions
        ):
            with self.subTest(name):
                path = tree / name
                write(tree, name, (path.read_text() if path.is_file() else "") + "\n# changed\n")
                git(tree, "add", "-A")
                git(tree, "commit", "-q", "-m", f"Change {name}")
                self.checked(tree, cached=False)


class AcceptanceContractRoundTwentyOne(RepoCase):
    def checked(self, tree, *, cached: bool, code: int = 0, slow: tuple = ("acceptance",)) -> dict:
        """The fast checks (``code``: their exit), then the slow ones by name, as an agent runs them: the second
        run's data (its tree_passed is still the fast checks')."""
        self.clear_log()
        got, data = self.run_cli("check", cwd=tree, as_json=True)
        self.assertEqual(got, code, data)
        got, data = self.run_cli("check", *slow, cwd=tree, as_json=True)
        self.assertEqual(got, 0, data)
        ran = [name for entry in self.check_log() for name in entry.get("names", [])]
        self.assertEqual("acceptance" not in ran, cached, ran)
        row = next(row for row in data["checks"] if row["name"] == "acceptance")
        self.assertEqual(row["cached"], cached, row)
        return data

    def shipped(self, tree) -> list[str]:
        body = write(self.base, "body.md", GOOD_BODY)
        _code, data = self.run_cli(
            "ship", "--title", "Say what the tool does", "--body", str(body), "--dry-run", cwd=tree, as_json=True
        )
        return [gate["name"] for gate in data["gates"] if not gate["ok"]]

    def test_a_contract_edit_keeps_the_acceptance_pass_and_the_tree_may_ship(self):
        tree = self.worktree("chore/tool")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", "Change the core")
        self.assertTrue(self.checked(tree, cached=False)["tree_passed"])
        self.commit(tree, "docs/dev/CONTRACT.md", "# Contract\n\n`chromatic_x`: says what it does.\n", "Describe it")
        data = self.checked(tree, cached=True)
        self.assertTrue(data["tree_passed"], data)
        self.assertEqual(self.check_log()[0]["names"], ["unit", "scan"], "the fast checks that read it still run")
        self.assertEqual(self.shipped(tree), [], "the ship gate takes the tree whose pass reused acceptance")
        write(tree, "docs/dev/CONTRACT.md", "# Contract\n\nChanged.\n")  # uncommitted: the other gates still hold
        self.assertIn("committed and clean", self.shipped(tree))
        git(tree, "commit", "-q", "-am", "Change it again")
        self.fail_checks("scan")
        data = self.checked(tree, cached=True, code=1)
        self.assertFalse(data["tree_passed"], "a cached acceptance pass never outweighs a failure")
        self.assertIn("checks passed on this tree", self.shipped(tree))

    def test_only_that_exact_file_is_left_out(self):
        tree = self.worktree("chore/tool")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", "Change the core")
        self.checked(tree, cached=False)
        for name in ("docs/dev/CONTRACT.md.orig", "docs/dev/ARCHITECTURE.md", "docs/guide.md", "docs/CONTRACT.md"):
            with self.subTest(name):
                self.commit(tree, name, f"# {name}\n", f"Change {name}")
                self.checked(tree, cached=False)

    def test_the_clean_install_still_reruns_after_a_contract_edit(self):
        tree = self.worktree("chore/glue")
        self.commit(tree, "backend/hermes/glue.py", "GLUE = 2\n", "Change the glue")
        self.checked(tree, cached=False, slow=("acceptance", "clean_install"))
        self.assertTrue([entry for entry in self.check_log() if "script" in entry], self.check_log())
        self.commit(tree, "docs/dev/CONTRACT.md", "# Contract\n", "Describe it")
        self.checked(tree, cached=True, slow=("acceptance", "clean_install"))
        self.assertTrue([entry for entry in self.check_log() if "script" in entry], "the install key keeps docs")
