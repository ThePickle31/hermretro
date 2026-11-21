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


class TheSmokeSelection(unittest.TestCase):
    def test_smoke_selects_only_the_guard_test(self):
        loader = unittest.TestLoader()
        loader.testNamePatterns = [f"*{check_py().SMOKE}*"]  # what unittest -k does
        cases = [
            case
            for case in vars(test_scaffold_tree).values()
            if isinstance(case, type) and issubclass(case, unittest.TestCase) and case.__module__ == MODULE
        ]
        chosen = [i for case in cases for i in ids(loader.loadTestsFromTestCase(case))]
        self.assertEqual(len(chosen), 1, f"SMOKE must pick the one guard test, picked {chosen}")
        guard = test_scaffold_tree.GeneratedCodePassesTheRealChecks
        self.assertTrue(chosen[0].startswith(f"{guard.__module__}.{guard.__qualname__}.test_new_"), chosen)

    def test_the_modes(self):
        module = check_py()
        for value, mode in (("nested", "nested"), ("smoke", "smoke"), ("1", "1"), ("", "1"), ("yes", "1")):
            with self.subTest(value=value):
                with mock.patch.object(module, "os", SimpleNamespace(environ={"RD_SCAFFOLD_FULL": value})):
                    self.assertEqual(module.scaffold_mode(), mode)
        test, inner = module.scaffold_test("smoke")
        self.assertEqual((test[-3:], inner), (["-k", module.SMOKE, "tests.retrodev.test_scaffold_tree"], "1"))
        for mode in ("1", "nested"):
            test, inner = module.scaffold_test(mode)
            self.assertNotIn("-k", test)
            self.assertEqual(inner, mode)


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
        said, calls = self.check("test_new_writes_code_that_passes_x ... ok\n\nRan 1 test in 26.1s\n\nOK\n")
        self.assertIn("smoke", said)
        [(command, inner)] = calls
        self.assertIn("-k", command)
        self.assertEqual(inner, "1")

    def test_a_smoke_that_ran_no_test_fails(self):
        for stderr, code in (("\nRan 0 tests in 0.000s\n\nOK\n", 0), ("\nRan 0 tests in 0.000s\n\nNO TESTS RAN\n", 5)):
            with self.subTest(code=code), self.assertRaises(AssertionError) as failed:
                self.check(stderr, code)
            self.assertIn("the smoke ran no test", str(failed.exception))
            self.assertIn("FIX: set SMOKE in tools/check.py", str(failed.exception))


if __name__ == "__main__":
    unittest.main()
