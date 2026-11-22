"""Check that a Hermes still has every name hermretro uses from it (backend/hermes/api.py).

    "$HERMES_RUNTIME_PY" -I tools/ci/hermes_api_check.py      # in CI, with Hermes's own Python
    <python> tools/ci/hermes_api_check.py                     # locally, with your Hermes install's Python
                                                              # (.agents/skills/hermretro-dev-testing/references/testing.md, "The Hermes names check")

CI runs it on every pull request against the oldest supported Hermes (ci.yml's HERMES_REF) and nightly against
Hermes main, so a rename in Hermes is caught before users update. It first makes sure this Python imports Hermes
at all: a Python without Hermes's dependencies would otherwise report every name as missing.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.hermes import api as hermes_api  # noqa: E402 - the repository root goes on sys.path first

IMPORT_FIX = (
    "FIX: run with a Python that imports Hermes and its dependencies (the Python of your Hermes install; "
    ".agents/skills/hermretro-dev-testing/references/testing.md, \"The Hermes names check\")"
)


def import_problems(importer=importlib.import_module) -> list[str]:
    """``module: error`` for hermes_cli and every module in api.USED that fails to import here (hermes_cli
    alone when even it fails: the rest would fail the same way)."""
    problems = []
    for module in ("hermes_cli", *dict.fromkeys(module for module, _attribute in hermes_api.USED)):
        try:
            importer(module)
        except Exception as error:  # noqa: BLE001 - every import failure is reported with its text
            problems.append(f"{module}: {type(error).__name__}: {error}")
            if module == "hermes_cli":
                break
    return problems


def main(importer=importlib.import_module) -> int:
    problems = import_problems(importer)
    if problems:
        print(f"this Python ({sys.executable}) cannot import Hermes:", file=sys.stderr)
        for problem in problems:
            print("  " + problem, file=sys.stderr)
        print(IMPORT_FIX, file=sys.stderr)
        return 1
    gone = hermes_api.missing()
    if gone:
        print("this Hermes lacks: " + ", ".join(gone), file=sys.stderr)
        print(
            "FIX: follow the rename in backend/hermes/api.py (keep the old name working while the oldest "
            "supported Hermes still has it)",
            file=sys.stderr,
        )
        return 1
    print(f"ok: all {len(hermes_api.USED)} Hermes names hermretro uses are present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
