"""What the READMEs and docs/dev documents point readers at is still there.

- Every `tests/...` path they name exists. The docs send readers (and agents) to test files by path; a test that
  moves, splits or is renamed leaves those pointers dangling. Paths with a placeholder (`<feature>`, `*`, `{...}`)
  are patterns, not files, and are skipped.
- None says `retrodev new` lacks a kind it has (`new <kind>` in tools/retrodev/cli.py): such a line sends the reader
  to hand steps the scaffold now does.
"""

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIPPED = ("engine/", "tools/npm/", "player/web/", ".dev/", "notes/", ".git/")
PATH = re.compile(r"(?<![\w./-])tests/[\w./<>*{}$-]*")
PATTERN = re.compile(r"[<>*{}$]")
NO_KIND = re.compile(r"retrodev new`? (?:has|had) no (\w+) kind")
KINDS = re.compile(r"^\s*kind\(\"(\w+)\"", re.M)


def documents() -> list[Path]:
    """Every README.md outside the vendored and generated folders, and every docs/dev/*.md."""
    found = sorted((ROOT / "docs" / "dev").glob("*.md"))
    for folder, dirs, files in os.walk(ROOT):
        here = Path(folder)
        dirs[:] = sorted(
            name
            for name in dirs
            if name != "node_modules" and not f"{(here / name).relative_to(ROOT).as_posix()}/".startswith(SKIPPED)
        )
        found += [Path(folder) / name for name in files if name == "README.md"]
    return found


def named_paths(text: str) -> list[tuple[int, str]]:
    """(line, path) for each concrete tests/... path in ``text``."""
    named = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in PATH.finditer(line):
            path = match.group(0).rstrip(".,;:)")
            if not PATTERN.search(path) and path not in ("tests", "tests/"):
                named.append((number, path))
    return named


class DocPathTests(unittest.TestCase):
    def test_every_named_test_path_exists(self):
        missing = [
            f"{doc.relative_to(ROOT)}:{number}: {path}"
            for doc in documents()
            for number, path in named_paths(doc.read_text(encoding="utf-8"))
            if not (ROOT / path).exists()
        ]
        self.assertEqual(
            missing,
            [],
            "\nthese docs name test files that do not exist:\n  "
            + "\n  ".join(missing)
            + "\nFIX: point each at the file's current path (git log --follow -- <old path> finds where it went), "
            "or remove the reference",
        )

    def test_no_doc_says_retrodev_new_lacks_a_kind_it_has(self):
        kinds = set(KINDS.findall((ROOT / "tools" / "retrodev" / "cli.py").read_text(encoding="utf-8")))
        self.assertIn("listener", kinds, "tools/retrodev/cli.py's kinds were not found: update KINDS here")
        stale = [
            f"{doc.relative_to(ROOT)}:{number}: says `retrodev new` has no {kind} kind"
            for doc in documents()
            for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1)
            for kind in NO_KIND.findall(line)
            if kind in kinds
        ]
        self.assertEqual(
            stale,
            [],
            "\n  " + "\n  ".join(stale) + "\nFIX: give the command instead: python tools/retrodev new <kind> ... "
            "(python tools/retrodev new --help lists the kinds and what each writes)",
        )

    def test_a_missing_path_is_found_and_a_pattern_is_not(self):  # the scans' own behaviour, on a fixed text
        text = "See `tests/repo/test_doc_pointers.py`, `tests/repo/test_nope.py`. Pattern: tests/backend/<feature>/."
        self.assertEqual(named_paths(text), [(1, "tests/repo/test_doc_pointers.py"), (1, "tests/repo/test_nope.py")])
        self.assertFalse((ROOT / "tests/repo/test_nope.py").exists())
        self.assertEqual(NO_KIND.findall("a listener: `retrodev new` has no listener kind yet."), ["listener"])


if __name__ == "__main__":
    unittest.main()
