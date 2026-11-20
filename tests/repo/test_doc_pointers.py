"""What the READMEs and docs/dev documents point readers at is still there.

- Every `tests/...` path they name exists. The docs send readers (and agents) to test files by path; a test that
  moves, splits or is renamed leaves those pointers dangling. Paths with a placeholder (`<feature>`, `*`, `{...}`)
  are patterns, not files, and are skipped.
- Every backtick-quoted `backend/<feature>/<module>.py` and `page/....js` path they name exists: a module split or
  renamed inside a feature otherwise leaves its README's module list and ARCHITECTURE.md naming a file that is gone.
- Every backtick-quoted relative source name (`provision.py`, `transcript/transcript.css.js`) in a feature or page
  README (backend/*/README.md, page/pages/*/README.md) exists beside that README, or in the folder its section's
  heading names (`## The New Game level (`attract/`)`). The "Adding ..." sections are skipped (they name files a
  scaffold would write), as are placeholders (`<tool>_tools.py`) and test files (`test_*.py`, `*.test.mjs`, tests/...).
- None says `retrodev new` lacks a kind it has (`new <kind>`, read from tools/retrodev/cli.py's syntax tree and
  checked against the real parser): such a line sends the reader to hand steps the scaffold now does.
"""

import ast
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIPPED = ("engine/", "tools/npm/", "player/web/", ".dev/", "notes/", ".git/")
PATH = re.compile(r"(?<![\w./-])tests/[\w./<>*{}$-]*")
PATTERN = re.compile(r"[<>*{}$]")
# A concrete source path in a code span (a placeholder such as `<feature>` stops the match, so patterns are skipped).
MODULE = re.compile(r"`((?:backend|page)/[\w./-]+\.(?:py|js|mjs))`")
# A relative source name in a code span: no folder root of the repository, no placeholder.
LOCAL = re.compile(r"`([\w./-]+\.(?:py|js|mjs))`")
HEADING = re.compile(r"^#{2,6}\s+(.*)")
NO_KIND = re.compile(r"retrodev new`? (?:has|had) no (\w+) kind")
EXPECTED_KINDS = {"feature", "rpc", "tool", "event", "listener", "page", "tab", "slot"}
CLI = ROOT / "tools" / "retrodev" / "cli.py"


def _add_subparsers_dest(node: ast.AST) -> str | None:
    """The dest of an ``x.add_subparsers(dest=...)`` call, else None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_subparsers":
        for keyword in node.keywords:
            if keyword.arg == "dest" and isinstance(keyword.value, ast.Constant):
                return keyword.value.value
    return None


def _first_string(call: ast.Call) -> str | None:
    first = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "name"), None)
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None


def _adds_parser(call: ast.AST, holders: set[str]) -> bool:
    """Whether ``call`` is ``h.add_parser(...)`` for one of the subparsers held in ``holders``."""
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "add_parser"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id in holders
    )


def new_kinds(source: str) -> set[str]:
    """Every kind `retrodev new` registers, read from cli.py's syntax tree.

    The kinds are the parsers added to the subparsers whose dest is "kind": directly (``kinds.add_parser("x")``)
    or through a local helper that passes its first parameter on to ``kinds.add_parser`` (``kind("x", ...)``),
    whether the call stands alone, is assigned, is chained or spans several lines.
    """
    kinds = set()
    for function in ast.walk(ast.parse(source)):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        holders = {
            target.id
            for node in ast.walk(function)
            if isinstance(node, ast.Assign) and _add_subparsers_dest(node.value) == "kind"
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        if not holders:
            continue

        helpers = set()
        for helper in ast.walk(function):
            if (
                isinstance(helper, (ast.FunctionDef, ast.AsyncFunctionDef))
                and helper is not function
                and helper.args.args
            ):
                first = helper.args.args[0].arg
                for call in ast.walk(helper):
                    if (
                        _adds_parser(call, holders)
                        and call.args
                        and isinstance(call.args[0], ast.Name)
                        and call.args[0].id == first
                    ):
                        helpers.add(helper.name)
        for call in ast.walk(function):
            direct = _adds_parser(call, holders)
            via_helper = isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in helpers
            if (direct or via_helper) and (name := _first_string(call)):
                kinds.add(name)
    return kinds


def stale_lines(docs: list[Path], kinds: set[str]) -> list[str]:
    """Each line of ``docs`` saying `retrodev new` has no kind that ``kinds`` holds."""
    return [
        f"{doc.relative_to(ROOT) if doc.is_relative_to(ROOT) else doc}:{number}: says `retrodev new` has no {kind} kind"
        for doc in docs
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1)
        for kind in NO_KIND.findall(line)
        if kind in kinds
    ]


def listed_kinds() -> set[str]:
    """The kinds the real parser lists (what `python tools/retrodev new --help` shows)."""
    code = (
        "import sys; sys.path[0] = sys.argv[1]; import argparse; from retrodev.cli import parser\n"
        "new = next(a for a in parser()._actions if isinstance(a, argparse._SubParsersAction)).choices['new']\n"
        "print(' '.join(next(a for a in new._actions if isinstance(a, argparse._SubParsersAction)).choices))"
    )
    run = subprocess.run(
        [sys.executable, "-c", code, str(ROOT / "tools")], capture_output=True, text=True, check=True, cwd=ROOT
    )
    return set(run.stdout.split())


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

    A name resolves against the README's folder, or a folder its section's heading names in backticks (`attract/`).
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
            "docs/dev/ARCHITECTURE.md (git log --follow -- <old path> finds where it went)",
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
                "\n## The level (`attract/`)\n\n| `run.js` | `attract/run.js` | `gone.js` |\n"
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

    def test_no_doc_says_retrodev_new_lacks_a_kind_it_has(self):
        kinds = new_kinds(CLI.read_text(encoding="utf-8"))
        self.assertLessEqual(EXPECTED_KINDS, kinds, "tools/retrodev/cli.py's kinds were not all found: fix new_kinds")
        stale = stale_lines(documents(), kinds)
        self.assertEqual(
            stale,
            [],
            "\n  " + "\n  ".join(stale) + "\nFIX: give the command instead: python tools/retrodev new <kind> ... "
            "(python tools/retrodev new --help lists the kinds and what each writes)",
        )

    def test_every_new_kind_is_read_from_the_cli(self):  # assigned calls and multi-line arguments included
        kinds = new_kinds(CLI.read_text(encoding="utf-8"))
        self.assertLessEqual(EXPECTED_KINDS, kinds)
        self.assertEqual(kinds, listed_kinds(), "new_kinds disagrees with python tools/retrodev new --help")

    def test_a_stale_line_about_any_kind_is_rejected(self):
        kinds = new_kinds(CLI.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            doc = Path(folder) / "README.md"
            doc.write_text("Intro.\n`retrodev new` has no tool kind yet: copy one by hand.\n", encoding="utf-8")
            self.assertEqual(stale_lines([doc], kinds), [f"{doc}:2: says `retrodev new` has no tool kind"])
            for kind in sorted(EXPECTED_KINDS):
                doc.write_text(f"retrodev new has no {kind} kind\n", encoding="utf-8")
                self.assertEqual(len(stale_lines([doc], kinds)), 1, kind)
            doc.write_text("retrodev new has no widget kind\n", encoding="utf-8")
            self.assertEqual(stale_lines([doc], kinds), [])

    def test_a_missing_path_is_found_and_a_pattern_is_not(self):  # the scans' own behaviour, on a fixed text
        text = "See `tests/repo/test_doc_pointers.py`, `tests/repo/test_nope.py`. Pattern: tests/backend/<feature>/."
        self.assertEqual(named_paths(text), [(1, "tests/repo/test_doc_pointers.py"), (1, "tests/repo/test_nope.py")])
        self.assertFalse((ROOT / "tests/repo/test_nope.py").exists())
        self.assertEqual(NO_KIND.findall("a listener: `retrodev new` has no listener kind yet."), ["listener"])


if __name__ == "__main__":
    unittest.main()
