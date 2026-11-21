"""The trial rounds' regressions for this area (RoundEight, RoundFive, RoundNineReview), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_scaffold_guard
"""

from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from tests.retrodev.fixture import parallel, write
from tests.retrodev.tree_copy import GIB, copy_base, git_ok
import retrodev
from tests.retrodev import test_scaffold_tree as tree_test
import subprocess

load_tests = parallel

ROOT = Path(retrodev.__file__).resolve().parents[2]


class TempSpaceRoundEight(unittest.TestCase):
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


class GuardRoundFive(unittest.TestCase):
    def test_the_guard_runs_every_kind_and_the_real_steps_name_real_features_and_pages(self):
        kinds = {step[0] for step in tree_test.STEPS + tree_test.REAL_STEPS}
        self.assertEqual(kinds, {"feature", "rpc", "tool", "event", "listener", "page", "tab", "slot", "contribution"})
        for step in tree_test.REAL_STEPS:
            where = "page/pages" if step[0] in ("tab", "slot", "contribution") else "backend"
            self.assertTrue((ROOT / where / step[1]).is_dir(), step)
        self.assertIn(["slot", "build"], [step[:2] for step in tree_test.REAL_STEPS])

    def test_the_real_steps_follow_a_tree_whose_pages_have_tabs_and_whose_listeners_are_taken(self):  # review 1, 0
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp)
            for name in [*ROOT.glob("backend/*/__init__.py"), *ROOT.glob("backend/*/listeners.py")]:
                write(tree, str(name.relative_to(ROOT)), name.read_text())
            door = "// {0}: a probe front door.\nimport {{ {1} }} from './{2}'\n\nexport const {3}_PAGE = {{\n  id: '{3}',\n{4}}}\n"
            for page in tree_test.REAL_PAGES:  # each tabless, its Page imported from a file of its own
                write(
                    tree,
                    f"page/pages/{page}/index.js",
                    door.format(page, "OwnPage", "own-page.js", page, "  Page: OwnPage\n"),
                )
            self.assertIn(["tab", "setup", "rdreal-setup-first", "--from-page"], tree_test.real_steps(tree))
            tabbed = door.format("setup", "SETUP_MAIN_TAB", "main/index.js", "setup", "  tabs: [SETUP_MAIN_TAB]\n")
            write(tree, "page/pages/setup/index.js", tabbed)  # setup's Page is a tab already, history listens already
            heard = "".join(
                f'@on("{event}")\ndef on_{event.replace(".", "_")}(**_payload):\n    pass\n'
                for event in tree_test.declared_events(tree)
            )  # history hears every declared event already
            write(tree, "backend/history/listeners.py", "from ..system.events import on\n\n\n" + heard)
            steps = tree_test.real_steps(tree)
            listener = next(step for step in steps if step[0] == "listener")
            self.assertFalse(tree_test.listens(tree, listener[1], listener[2]), listener)
        setup = [step for step in steps if step[:2] == ["tab", "setup"]]
        self.assertEqual(setup, [["tab", "setup", "rdreal-setup-first"], ["tab", "setup", "rdreal-setup-second"]])
        self.assertNotEqual(listener[1], "history", listener)
        names = [step[2] for step in steps if step[0] in ("event", "tab")]
        self.assertEqual(len(set(names)), len(names), "unique probe names")
        self.assertTrue(all(name.startswith("rdreal") for name in names), names)


class WholeModuleFirstRoundNineReview(unittest.TestCase):
    def case(self, failing: set[str], log: list[str]) -> unittest.TestCase:
        """A slow test whose copies are empty folders and whose suites fail when named in ``failing``."""
        case = tree_test.GeneratedCodePassesTheRealChecks("test_tab_from_page_passes_its_own_checks_lint_and_bundle")
        temp = tempfile.TemporaryDirectory(prefix="rd-first-")
        self.addCleanup(temp.cleanup)

        def suite(command, tree, env):
            log.append(command[-1])
            return subprocess.CompletedProcess(command, int(command[-1] in failing), "suite output\n", "")

        case.copy, case.suite = (lambda: (Path(temp.name), Path(temp.name), {})), suite
        return case

    def test_a_tree_failing_page_skips_every_slow_test_after_one_run(self):
        cache, log = {}, []
        for _ in range(3):  # three slow tests of one process
            with self.assertRaises(unittest.SkipTest) as said:
                self.case({"page"}, log).first("1", "", cache)
            self.assertIn(tree_test.PAGE_FIRST, str(said.exception))
        self.assertEqual(log, ["page"], "the page suite ran once, not per test")

    def test_nested_a_failing_unit_suite_skips_as_unit_first(self):
        cache, log = {}, []
        with self.assertRaises(unittest.SkipTest) as said:
            self.case({"unit", "page"}, log).first("nested", "", cache)
        self.assertIn(tree_test.UNIT_FIRST, str(said.exception))
        self.assertEqual(log, ["unit"])

    def test_suites_check_py_ran_already_are_not_run_again(self):
        cache, log = {}, []
        self.case({"page"}, log).first("nested", "unit,page", cache)
        self.case(set(), log).first("1", "", cache)
        self.assertEqual(log, ["page"], "nested: none run; the plain mode's own page once")
