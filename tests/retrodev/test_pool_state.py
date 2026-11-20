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

from retrodev import checks, scaffold

from tests.retrodev.fixture import alone
from tests.retrodev.pool import ParallelSuite

load_tests = alone


class ScaffoldGate(unittest.TestCase):
    def test_validate_passes_the_gate_only_to_its_subprocesses(self):  # review 1, 0
        seen = {}

        def fake_run(ctx, names, **kwargs):
            seen["during"] = os.environ.get(scaffold.SCAFFOLD_CHECK)
            seen["env"] = kwargs.get("env")

        before = dict(os.environ)
        with (
            mock.patch.object(scaffold.repo, "branch", return_value="feat/x"),
            mock.patch.object(scaffold.state, "load_branch", return_value={}),
            mock.patch.object(scaffold.state, "save_branch"),
            mock.patch.object(scaffold.checks, "run", fake_run),
        ):
            scaffold.validate(mock.Mock(), ["unit"])
        self.assertIsNone(seen["during"], "validate set the gate in os.environ, which every pooled thread shares")
        self.assertEqual(seen["env"], {scaffold.SCAFFOLD_CHECK: "1"})
        self.assertEqual(dict(os.environ), before)

    def test_the_subprocess_environment_carries_the_gate_and_os_environ_does_not(self):
        before = dict(os.environ)
        for name in ("fast", "acceptance"):
            env = checks.env_for(name, {scaffold.SCAFFOLD_CHECK: "1"})
            self.assertEqual(env[scaffold.SCAFFOLD_CHECK], "1", name)
        self.assertNotIn(scaffold.SCAFFOLD_CHECK, checks.env_for("fast"))
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

    def run_pooled(self, name: str) -> unittest.TestResult:
        result = unittest.TestResult()
        cwd, path = os.getcwd(), list(sys.path)
        try:
            ParallelSuite([self.Leaky(name)]).run(result)
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
            result = self.run_pooled(name)
            self.assertEqual(len(result.errors), 1, name)
            text = str(result.errors[0][0]) + result.errors[0][1]
            self.assertIn(__name__, text, name)
            self.assertIn(what, text, name)
        self.assertNotIn("RETRODEV_POOL_STATE_PROBE", os.environ)

    def test_a_clean_test_passes(self):
        result = self.run_pooled("test_clean")
        self.assertEqual((result.errors, result.failures, result.testsRun), ([], [], 1))


if __name__ == "__main__":
    unittest.main()
