"""What the READMEs and the development skills point readers at is still there.

- Every `tests/...` path they name exists. The docs send readers (and agents) to test files by path; a test that
  moves, splits or is renamed leaves those pointers dangling. Paths with a placeholder (`<feature>`, `*`, `{...}`)
  are patterns, not files, and are skipped.
- Every backtick-quoted `backend/<feature>/<module>.py` and `page/....js` path they name exists: a module split or
  renamed inside a feature otherwise leaves its README's module list and .agents/skills/hermretro-dev-architecture/references/architecture.md naming a file that is gone.
- Every backtick-quoted relative source name (`provision.py`, `transcript/transcript.css.js`) in a feature or page
  README (backend/*/README.md, page/pages/*/README.md) exists beside that README, or in the folder its section's
  heading names (`## The New Game level (`attract/`)`). The "Adding ..." sections are skipped (they name files a
  new piece would add), as are placeholders (`<tool>_tools.py`) and test files (`test_*.py`, `*.test.mjs`, tests/...).
"""

import re
import tempfile
import unittest
from pathlib import Path

from tests.repo.test_layout import files

ROOT = Path(__file__).resolve().parents[2]
SKIPPED = ("engine/", "tools/npm/", "player/web/", ".dev/", "notes/", ".git/")
PATH = re.compile(r"(?<![\w./-])tests/[\w./<>*{}$-]*")
PATTERN = re.compile(r"[<>*{}$]")
# A concrete source path in a code span (a placeholder such as `<feature>` stops the match, so patterns are skipped).
MODULE = re.compile(r"`((?:backend|page)/[\w./-]+\.(?:py|js|mjs))`")
# A relative source name in a code span: no folder root of the repository, no placeholder.
LOCAL = re.compile(r"`([\w./-]+\.(?:py|js|mjs))`")
HEADING = re.compile(r"^#{2,6}\s+(.*)")


def documents() -> list[Path]:
    """Every README.md outside the vendored folders, and every .md of the development skills (.agents/skills/): tracked files only, so a
    developer's downloads cannot decide the result."""
    return [
        ROOT / rel
        for rel in files()
        if not rel.startswith(SKIPPED)
        and (rel == "README.md" or rel.endswith("/README.md") or rel.startswith(".agents/skills/"))
        and rel.endswith(".md")
    ]


def named_paths(text: str) -> list[tuple[int, str]]:
    """(line, path) for each concrete tests/... path in ``text``."""
    named = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in PATH.finditer(line):
            path = match.group(0).rstrip(".,;:)")
            if not PATTERN.search(path) and path not in ("tests", "tests/"):
                named.append((number, path))
    return named


def missing_modules(docs: list[Path]) -> list[str]:
    """``doc:line: path`` for each backtick-quoted backend/ or page/ source path in ``docs`` that does not exist."""
    return [
        f"{doc.relative_to(ROOT) if doc.is_relative_to(ROOT) else doc}:{number}: {path}"
        for doc in docs
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1)
        for path in MODULE.findall(line)
        if not (ROOT / path).is_file()
    ]


def feature_readmes() -> list[Path]:
    """Each feature's and page's README: their opening paragraphs and sections list the folder's own modules."""
    return sorted([*ROOT.glob("backend/*/README.md"), *ROOT.glob("page/pages/*/README.md")])


def missing_local_modules(docs: list[Path]) -> list[str]:
    """``doc:line: name`` for each relative source name in ``docs`` not found beside the README.

    A name resolves against the README's folder, or a folder its section's heading names in backticks (`attract/`),
    or the repository root (a file in another folder, such as the engine's).
    "Adding ..." sections name what a scaffold would write, so they are skipped; so are repository-root paths (the
    MODULE check covers them), tests (`test_*.py`, `*.test.mjs`, `tests/...`) and placeholders, which LOCAL never
    matches (`<`, `*`).
    """
    missing = []
    for doc in docs:
        heading = ""
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if found := HEADING.match(line):
                heading = found.group(1)
                continue
            if heading.startswith("Adding"):
                continue
            folders = [doc.parent, *(doc.parent / sub for sub in re.findall(r"`([\w-]+)/`", heading))]
            for name in LOCAL.findall(line):
                if name.startswith(("backend/", "page/", "tests/")) or re.match(r"test_|.*\.test\.", Path(name).name):
                    continue
                if "/" in name and (ROOT / name).is_file():
                    continue  # a repository-root path to another folder (`engine/.../web-preview-states.js`)
                if not any((folder / name).is_file() for folder in folders):
                    shown = doc.relative_to(ROOT) if doc.is_relative_to(ROOT) else doc
                    missing.append(f"{shown}:{number}: {name}")
    return missing


class DocPathTests(unittest.TestCase):
    def test_every_named_module_exists(self):
        missing = missing_modules(documents())
        self.assertEqual(
            missing,
            [],
            "\nthese docs name backend/ or page/ files that do not exist:\n  "
            + "\n  ".join(missing)
            + "\nFIX: after a module split or rename, update the feature README's module list and any mention in "
            ".agents/skills/hermretro-dev-architecture/references/architecture.md (git log --follow -- <old path> finds where it went)",
        )

    def test_a_doc_naming_a_missing_module_is_caught(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "README.md"
            doc.write_text(
                "Real: `backend/library/games.py`, `page/app/player/stage.js`.\n"
                "Gone: `backend/library/old_games.py`.\nPattern: `backend/<feature>/rpcs.py`, `page/pages/<page>/index.js`.\n"
                "Gone too: `page/app/player/no-stage.js`\n",
                encoding="utf-8",
            )
            self.assertEqual(
                missing_modules([doc]),
                [f"{doc}:2: backend/library/old_games.py", f"{doc}:4: page/app/player/no-stage.js"],
            )

    def test_every_module_a_feature_readme_lists_exists(self):
        missing = missing_local_modules(feature_readmes())
        self.assertEqual(
            missing,
            [],
            "\nthese feature READMEs name modules that are not in their folder:\n  "
            + "\n  ".join(missing)
            + "\nFIX: after a module split or rename, update the README's module list (its opening paragraph or the "
            "section naming it); git log --follow -- <old path> finds where it went",
        )

    def test_a_feature_readme_naming_a_stale_module_is_caught(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "attract").mkdir()
            for name in ("provision.py", "rpcs.py", "attract/run.js"):
                (base / name).write_text("", encoding="utf-8")
            doc = base / "README.md"
            doc.write_text(
                "# backend/setup\n\n"
                "Preparing the machine: ModRetro's CLI (`provision.py`, was `old_provision.py`) and the RPCs (`rpcs.py`).\n"
                "\n## What it adds\n\n- RPCs (`rpcs.py`): `status`. Tools (`tools.py`): none.\n"
                "\n## The level (`attract/`)\n\n| `run.js` | `attract/run.js` | `gone.js` | `engine/src/web-preview-states.js` |\n"
                "\n## Tests\n\n`tests/backend/setup/`: `test_provision.py`, `tests/page/attract.test.mjs`.\n"
                "\n## Adding here\n\n- an event: writes `emits.py`; a split writes `<name>_tools.py`, `listeners.py`.\n",
                encoding="utf-8",
            )
            self.assertEqual(
                missing_local_modules([doc]),
                [f"{doc}:3: old_provision.py", f"{doc}:7: tools.py", f"{doc}:11: gone.js"],
            )

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

    def test_a_missing_path_is_found_and_a_pattern_is_not(self):  # the scans' own behaviour, on a fixed text
        text = "See `tests/repo/test_doc_pointers.py`, `tests/repo/test_nope.py`. Pattern: tests/backend/<feature>/."
        self.assertEqual(named_paths(text), [(1, "tests/repo/test_doc_pointers.py"), (1, "tests/repo/test_nope.py")])
        self.assertFalse((ROOT / "tests/repo/test_nope.py").exists())


if __name__ == "__main__":
    unittest.main()
