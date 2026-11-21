"""CI's page job on an ordinary pull request runs the scaffold smoke (`RD_SCAFFOLD_FULL=smoke check.py scaffold`):
only the guard test of tests/retrodev/test_scaffold_tree.py (every kind of `retrodev new`, its focused checks), in
the fast mode, selected by tools/check.py SMOKE. The selection must keep matching that test and nothing else, and a
smoke that ran no test fails instead of passing.

Run alone: python -m unittest tests.retrodev.test_scaffold_smoke
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.retrodev import test_scaffold_tree
from tests.retrodev.fixture import parallel

load_tests = parallel

ROOT = Path(__file__).resolve().parents[2]
MODULE = test_scaffold_tree.__name__


def check_py():
    spec = importlib.util.spec_from_file_location("check_py_probe_scaffold_smoke", ROOT / "tools/check.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ids(suite) -> list[str]:
    return [i for t in suite for i in (ids(t) if isinstance(t, unittest.BaseTestSuite) else [t.id()])]


# The guard: one `new` of every kind with the focused checks. Its sibling in the same class,
# test_new_runs_checks_without_caching_or_failing_on_unfilled_stubs, exercises only listener and RPC scaffolds.
GUARD = test_scaffold_tree.GeneratedCodePassesTheRealChecks.test_new_writes_code_that_passes_the_repository_checks


class TheSmokeSelection(unittest.TestCase):
    def test_smoke_selects_exactly_the_guard_test(self):  # review 1, 2 (#112)
        """What unittest actually loads for the smoke's command (`python -m unittest <name>` loads by name) is the
        guard and nothing else: not a sibling a looser pattern would also match."""
        test, _inner = check_py().scaffold_test("smoke")
        chosen = ids(unittest.TestLoader().loadTestsFromNames(test[test.index("-v") + 1 :]))
        guard = test_scaffold_tree.GeneratedCodePassesTheRealChecks
        self.assertEqual(chosen, [f"{MODULE}.{guard.__qualname__}.{GUARD.__name__}"])

    def test_the_modes(self):
        module = check_py()
        for value, mode in (("nested", "nested"), ("smoke", "smoke"), ("1", "1"), ("", "1"), ("yes", "1")):
            with self.subTest(value=value):
                with mock.patch.object(module, "os", SimpleNamespace(environ={"RD_SCAFFOLD_FULL": value})):
                    self.assertEqual(module.scaffold_mode(), mode)
        test, inner = module.scaffold_test("smoke")
        self.assertEqual((test[1:], inner), (["-m", "unittest", "-v", module.SMOKE], "1"), "the fast mode")
        for mode in ("1", "nested"):
            test, inner = module.scaffold_test(mode)
            self.assertEqual((test[1:], inner), (["-m", "unittest", "-v", "tests.retrodev.test_scaffold_tree"], mode))


class TheSmokeFailsClosed(unittest.TestCase):
    def check(self, stderr: str, returncode: int = 0) -> tuple[str, list]:
        module, calls = check_py(), []

        def run(command, **kwargs):
            calls.append((command, kwargs["env"]["RD_SCAFFOLD_FULL"]))
            return subprocess.CompletedProcess(command, returncode, "", stderr)

        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "tools/npm/node_modules").mkdir(parents=True)
            with (
                mock.patch.object(module, "ROOT", Path(root)),
                mock.patch.object(module, "ruff_missing", lambda: None),
                mock.patch.object(module, "need", lambda tool: tool),
                mock.patch.object(module, "scaffold_mode", lambda: "smoke"),
                mock.patch.object(module, "base_failure", lambda args, name: ""),
                mock.patch.object(module, "run", run),
            ):
                return module.check_scaffold(argparse.Namespace(strict=True)), calls

    def test_a_smoke_that_ran_its_test_passes_in_the_fast_mode(self):
        said, calls = self.check(f"{GUARD.__name__} ... ok\n\nRan 1 test in 26.1s\n\nOK\n")
        self.assertIn("smoke", said)
        [(command, inner)] = calls
        self.assertEqual(command[-1], check_py().SMOKE)
        self.assertEqual(inner, "1")

    def test_a_smoke_that_ran_no_test_fails(self):
        for stderr, code in (("\nRan 0 tests in 0.000s\n\nOK\n", 0), ("\nRan 0 tests in 0.000s\n\nNO TESTS RAN\n", 5)):
            with self.subTest(code=code), self.assertRaises(AssertionError) as failed:
                self.check(stderr, code)
            self.assertIn("the smoke ran no test", str(failed.exception))
            self.assertIn("FIX: set SMOKE in tools/check.py", str(failed.exception))

    def test_a_smoke_that_stopped_before_its_count_says_why_not_the_selector(self):  # review 1, 3 (#112)
        """A run that aborts (killed, a crash at import) prints no final count: the failure keeps the exit status
        and stderr, and its FIX is the rerun of that command, never the selector."""
        crash = f"{GUARD.__name__} ... Fatal Python error: Segmentation fault\nin tools/retrodev/scaffold.py line 9\n"
        for stderr, code in ((crash, -11), (crash, 0), ("", 1)):
            with self.subTest(code=code, stderr=bool(stderr)), self.assertRaises(AssertionError) as failed:
                self.check(stderr, code)
            said = str(failed.exception)
            self.assertNotIn("set SMOKE", said)
            self.assertNotIn("ran no test", said)
            self.assertIn(f"exit {code}", said)
            self.assertIn(crash.strip().splitlines()[-1] if stderr else "no test count", said)
            self.assertIn(
                f"FIX: RD_SCAFFOLD_FULL=smoke RD_SCAFFOLD_KEEP=1 python -B -m unittest -v {check_py().SMOKE}", said
            )

    def test_a_smoke_whose_guard_failed_keeps_the_rerun(self):
        stderr = (
            f"{GUARD.__name__} ... FAIL\n\nAssertionError: lint failed\n\nRan 1 test in 20.0s\n\nFAILED (failures=1)\n"
        )
        with self.assertRaises(AssertionError) as failed:
            self.check(stderr, 1)
        said = str(failed.exception)
        self.assertIn("lint failed", said)
        self.assertIn("exit 1", said)
        self.assertNotIn("set SMOKE", said)


if __name__ == "__main__":
    unittest.main()
