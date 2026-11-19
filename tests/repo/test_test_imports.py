"""Tests import their helpers as ``tests.support``, never with tests/ itself on sys.path.

A test that puts tests/ on sys.path and imports ``support`` makes tests/backend importable as ``backend``: once
it is first in sys.path, the next test module's ``from backend.setup import ...`` loads the test folder instead
of the real package, and running two dotted test modules together fails with an ImportError that neither shows
alone (``python -B -m unittest tests.backend.setup.test_remove_tools tests.backend.library.test_games``).

Run alone: python -m unittest tests.repo.test_test_imports
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PLAIN_SUPPORT = re.compile(r"^\s*(from support import|import support\b)", re.M)
# sys.path.insert(0, str(Path(__file__).resolve().parents[N])) where N lands on tests/ itself.
INSERT = re.compile(r"sys\.path\.insert\(\s*0\s*,\s*str\(Path\(__file__\)\.resolve\(\)\.parents\[(\d)\]\)")


def offenders(path: Path, text: str) -> list[str]:
    found = []
    if PLAIN_SUPPORT.search(text):
        found.append(f"{path}: imports support without the tests. prefix")
    tests = ROOT / "tests"
    for match in INSERT.finditer(text):
        level = int(match.group(1))
        parents = (ROOT / path).resolve().parents
        if level < len(parents) and parents[level] == tests:
            found.append(f"{path}: puts tests/ on sys.path")
    return found


class TestImports(unittest.TestCase):
    def test_no_test_puts_tests_on_sys_path(self):
        found = []
        for file in sorted((ROOT / "tests").rglob("*.py")):
            relative = file.relative_to(ROOT)
            found += offenders(relative, file.read_text(encoding="utf-8"))
        self.assertEqual(
            found,
            [],
            "\n  ".join(["", *found])
            + "\nFIX: drop the sys.path.insert of tests/ and write `from tests.support import ...` (tests/ on "
            "sys.path makes tests/backend shadow the real backend package)",
        )

    def test_the_rule_catches_both_forms(self):
        path = Path("tests/backend/setup/test_example.py")
        bad = "sys.path.insert(0, str(Path(__file__).resolve().parents[2]))\nfrom support import throwaway_deps\n"
        self.assertEqual(len(offenders(path, bad)), 2)
        good = (
            "sys.path.insert(0, str(Path(__file__).resolve().parents[3]))\nfrom tests.support import throwaway_deps\n"
        )
        self.assertEqual(offenders(path, good), [])


if __name__ == "__main__":
    unittest.main()
