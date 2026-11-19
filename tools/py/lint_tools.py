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
RUFF_CHECK = [str(RUFF), "check", "--config", "tools/py/ruff.toml", "--output-format", "concise", "."]
RUFF_FORMAT = [str(RUFF), "format", "--config", "tools/py/ruff.toml", "."]
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
