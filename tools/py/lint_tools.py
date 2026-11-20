"""The tools check.py's lint needs, and whether they are here: ruff (pinned with hashes in tools/py/requirements.txt,
installed by tools/py/setup.py into .dev/py, never by the checks; its settings: tools/py/ruff.toml, whose paths are
taken from the root, where the checks run) and the page's ESLint (tools/npm, found by tools/bundle/node-modules.mjs).
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUFF = ROOT / ".dev" / "py" / "bin" / "ruff"
# --force-exclude: ruff.toml's excludes hold for files named on the command line too (lint_files names them).
RUFF_CHECK = [
    str(RUFF),
    "check",
    "--config",
    "tools/py/ruff.toml",
    "--force-exclude",
    "--output-format",
    "concise",
    ".",
]
RUFF_FORMAT = [str(RUFF), "format", "--config", "tools/py/ruff.toml", "--force-exclude", "."]
RUFF_SETUP = "python tools/py/setup.py (once; about 5 s, then a no-op until tools/py/requirements.txt changes)"
# Both at once: what a fresh checkout needs before `python tools/check.py` can lint.
LINT_SETUP = "python tools/py/setup.py && npm ci --prefix tools/npm --ignore-scripts"
# The same lookup lint-page.mjs makes (tools/bundle/node-modules.mjs), so the answer cannot drift from it.
ESLINT_PROBE = (
    "import { findModules } from './tools/bundle/node-modules.mjs';"
    "process.exit(findModules(['eslint', 'eslint-plugin-react-hooks', 'globals']) ? 0 : 1)"
)


def ruff_missing() -> str | None:
    """Why the pinned ruff cannot run, or None."""
    stamp = ROOT / ".dev" / "py" / "requirements.sha256"
    if not RUFF.is_file():
        return "ruff is not installed in .dev/py"
    pinned = hashlib.sha256((ROOT / "tools" / "py" / "requirements.txt").read_bytes()).hexdigest()
    if not stamp.is_file() or stamp.read_text().strip() != pinned:
        return "the ruff in .dev/py is not the one tools/py/requirements.txt pins"
    return None


def eslint_missing() -> str | None:
    """Why the page's ESLint cannot run, or None (without node the page lint is skipped, as before)."""
    node = shutil.which("node")
    if not node:
        return None
    probe = subprocess.run([node, "--input-type=module", "-e", ESLINT_PROBE], cwd=ROOT, capture_output=True)
    return None if probe.returncode == 0 else "eslint is not installed (tools/npm/node_modules)"


def lint_tools_missing() -> list[str]:
    """Every lint tool that is missing, each with why."""
    return [why for why in (ruff_missing(), eslint_missing()) if why]


def ruff_check(paths: list[str]) -> list[str]:
    """ruff's lint over ``paths`` (check.py's lint: ["."]), with the pinned settings."""
    return [*RUFF_CHECK[:-1], *paths]


def ruff_format_check(paths: list[str]) -> list[str]:
    """ruff's format check over ``paths`` (check.py's lint: ["."]): each file not in the format, one per line."""
    return [*RUFF_FORMAT[:-1], "--check", "--output-format", "concise", *paths]


def page_lint(node: str, files: list[str]) -> list[str]:
    """The page lint (ESLint over page/**/*.js; check.py's lint: every file, ``files`` empty), with its settings."""
    return [node, "tools/bundle/lint-page.mjs", *files]


def lint_files(files: list[str]) -> tuple[bool, list[str]]:
    """Lint only ``files`` (paths from the root: `retrodev new`'s own, after the whole lint failed), with the same
    tools, commands and settings as check.py's lint: ruff for .py, the page lint for page/**/*.js; any other file has
    no lint. (passed, what was said). Passed only when every tool these files need is here, ran and found nothing,
    so a missing tool, a tool that cannot start, or a finding in one of them never counts as the tree's own."""
    present = [name for name in dict.fromkeys(files) if (ROOT / name).is_file()]
    python = [name for name in present if name.endswith(".py")]
    page = [name for name in present if name.startswith("page/") and name.endswith(".js")]
    runs, said = [], []
    if python and (why := ruff_missing()):
        said.append(f"ruff is missing ({why}), so new's {len(python)} Python files were not linted: {RUFF_SETUP}")
    elif python:
        runs += [("ruff check", ruff_check(python)), ("ruff format --check", ruff_format_check(python))]
    node = shutil.which("node")
    if page and not node:
        said.append(f"node is missing, so new's {len(page)} page files were not linted: install Node 22 or newer")
    elif page and (why := eslint_missing()):
        said.append(
            f"{why}, so new's {len(page)} page files were not linted: npm ci --prefix tools/npm --ignore-scripts"
        )
    elif page and node:
        runs.append(("the page lint", page_lint(node, page)))
    for name, command in runs:
        try:
            done = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=300)
        except (OSError, subprocess.SubprocessError) as error:
            said.append(f"{name} could not run on new's files: {error}")
            continue
        if done.returncode:
            lines = (done.stdout + done.stderr).strip().splitlines()[-40:]
            said.append(f"{name} fails on new's own files (exit {done.returncode}):\n" + "\n".join(lines))
    if said:
        return False, said
    return True, [f"new's own files pass lint alone ({len(python)} Python, {len(page)} page; the others have none)"]
