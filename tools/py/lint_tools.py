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
# --force-exclude: ruff.toml's excludes hold for files named on the command line too.
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
# The same lookups the two ESLint runs make (tools/bundle/node-modules.mjs), so the answer cannot drift from them: the
# page's in any of its folders (exit 1 when none has them), the engine's in tools/npm only (exit 2).
ESLINT_PROBE = (
    "import { findModules, PINNED_MODULES } from './tools/bundle/node-modules.mjs';"
    "process.exit(!findModules(['eslint', 'eslint-plugin-react-hooks', 'globals']) ? 1"
    " : !findModules(['eslint', 'globals'], [PINNED_MODULES]) ? 2 : 0)"
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
    """Why the page's or the engine's ESLint cannot run, or None (without node both are skipped, as before)."""
    node = shutil.which("node")
    if not node:
        return None
    probe = subprocess.run([node, "--input-type=module", "-e", ESLINT_PROBE], cwd=ROOT, capture_output=True)
    if probe.returncode == 2:
        return "the engine's eslint is not installed (tools/npm/node_modules, the pinned versions)"
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


# The exit code of either ESLint run when ESLint or a package it needs is not installed (MISSING_TOOLS in
# tools/bundle/eslint-run.mjs); an error is 1.
LINT_MISSING_TOOLS = 3


def page_lint(node: str, files: list[str]) -> list[str]:
    """The page lint (ESLint over page/**/*.js; check.py's lint: every file, ``files`` empty), with its settings."""
    return [node, "tools/bundle/lint-page.mjs", *files]


def engine_lint(node: str) -> list[str]:
    """The engine lint (ESLint over engine/src and engine/scripts), with its settings."""
    return [node, "tools/engine/lint.mjs"]
