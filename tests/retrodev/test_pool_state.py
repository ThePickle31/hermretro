"""Process state the pooled tests share: `new`'s own checks pass the placeholder gate's switch only to the processes
they start (never through os.environ, which every thread of the pool reads), and the pool itself fails a pooled
test module that leaves os.environ, the working folder or sys.path changed (the paths the syntax guard in
tests/repo/test_pool_guard.py cannot see: a mutation inside the code a test calls).

These tests patch module attributes and plant changes to the process state, so this module runs alone.
Run alone: python -m unittest tests.retrodev.test_pool_state
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

from retrodev import checks, scaffold_checks

from tests.retrodev.fixture import alone
from tests.retrodev.pool import ParallelSuite
import subprocess
from pathlib import Path
import retrodev

load_tests = alone


class ScaffoldGate(unittest.TestCase):
    def setUp(self):  # new's own unit run (test_scaffold_tree) has the gate set: start without it
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(scaffold_checks.SCAFFOLD_CHECK, None)

    def test_validate_passes_the_gate_only_to_its_subprocesses(self):  # review 1, 0
        seen = {}

        def fake_run(ctx, names, **kwargs):
            seen["during"] = os.environ.get(scaffold_checks.SCAFFOLD_CHECK)
            seen["env"] = kwargs.get("env")

        before = dict(os.environ)
        with (
            mock.patch.object(scaffold_checks.repo, "branch", return_value="feat/x"),
            mock.patch.object(scaffold_checks.state, "load_branch", return_value={}),
            mock.patch.object(scaffold_checks.state, "save_branch"),
            mock.patch.object(scaffold_checks.checks, "run", fake_run),
        ):
            scaffold_checks.validate(mock.Mock(), ["unit"])
        self.assertIsNone(seen["during"], "validate set the gate in os.environ, which every pooled thread shares")
        self.assertEqual(seen["env"], {scaffold_checks.SCAFFOLD_CHECK: "1"})
        self.assertEqual(dict(os.environ), before)

    def test_the_subprocess_environment_carries_the_gate_and_os_environ_does_not(self):
        before = dict(os.environ)
        for name in ("fast", "acceptance"):
            env = checks.env_for(name, {scaffold_checks.SCAFFOLD_CHECK: "1"})
            self.assertEqual(env[scaffold_checks.SCAFFOLD_CHECK], "1", name)
        self.assertNotIn(scaffold_checks.SCAFFOLD_CHECK, checks.env_for("fast"))
        self.assertEqual(dict(os.environ), before)


class PoolCheck(unittest.TestCase):
    class Leaky(unittest.TestCase):
        """Planted (not discovered: a class attribute): each test leaves one piece of process state changed (the outer test puts it back)."""

        def test_environ(self):
            os.environ["RETRODEV_POOL_STATE_PROBE"] = "1"

        def test_cwd(self):
            os.chdir(tempfile.gettempdir())

        def test_sys_path(self):
            sys.path.append("/retrodev-pool-state-probe")

        def test_clean(self):
            pass

    def run_pooled(self, name: str, as_class: bool = False) -> unittest.TestResult:
        """One Leaky test on the pool: by itself (a parallel module's item), or inside an ordinary class suite (how
        one_pool hands it a class of a module without load_tests = parallel)."""
        result = unittest.TestResult()
        cwd, path = os.getcwd(), list(sys.path)
        item = unittest.TestSuite([self.Leaky(name), self.Leaky("test_clean")]) if as_class else self.Leaky(name)
        try:
            ParallelSuite([item]).run(result)
        finally:
            os.chdir(cwd)
            sys.path[:] = path
        return result

    def test_the_pool_fails_a_module_that_changes_process_state_and_names_it(self):
        for name, what in (
            ("test_environ", "os.environ"),
            ("test_cwd", "working folder"),
            ("test_sys_path", "sys.path"),
        ):
            for as_class in (False, True):  # review 2, 1: a class suite drops its tests as it runs them
                with self.subTest(name=name, as_class=as_class):
                    result = self.run_pooled(name, as_class)
                    self.assertEqual(len(result.errors), 1, name)
                    text = str(result.errors[0][0]) + result.errors[0][1]
                    self.assertIn(__name__, text, name)
                    self.assertNotIn("a pooled module", text, name)
                    self.assertIn(what, text, name)
        self.assertNotIn("RETRODEV_POOL_STATE_PROBE", os.environ)

    def test_a_clean_test_passes(self):
        result = self.run_pooled("test_clean")
        self.assertEqual((result.errors, result.failures, result.testsRun), ([], [], 1))
        result = self.run_pooled("test_clean", as_class=True)
        self.assertEqual((result.errors, result.failures, result.testsRun), ([], [], 2))


ROOT = Path(retrodev.__file__).resolve().parents[2]

WALK = """
import sys, unittest


def flat(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flat(item)
        else:
            yield item


found = unittest.TestLoader().discover(sys.argv[1] + "/tests", top_level_dir=sys.argv[1])  # as check.py unit
print("\\n".join(test.id() for test in flat(found)))
"""


class PoolRoundFour(unittest.TestCase):
    def test_walking_the_discovered_suite_reaches_every_test_id(self):
        # In a process of its own: discovery imports every test module, whose first import changes sys.path.
        ids = subprocess.run(
            [sys.executable, "-c", WALK, str(ROOT)], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
        self.assertIn(f"{__name__}.{type(self).__name__}.test_walking_the_discovered_suite_reaches_every_test_id", ids)
        self.assertIn(
            "tests.retrodev.test_check_gates.CheckRoundFour.test_scaffold_does_not_run_when_lint_fails_in_the_same_run",
            ids,
        )


if __name__ == "__main__":
    unittest.main()
