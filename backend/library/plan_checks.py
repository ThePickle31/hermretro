"""A game's test plan: ``docs/game/TEST-PLAN.md``, written with the hermretro:game-planning skill. Every build
report of a game with one gives each of its open checks a result (``report_tools.py``). Standard library only."""

from __future__ import annotations

import re
from pathlib import Path

PLAN_FILE = Path("docs", "game", "TEST-PLAN.md")
MAX_PLAN_BYTES = 256 * 1024
# A check's ID: the first cell of a row in a table whose first column is "ID" (T1, T12, AUD2, T3b).
CHECK_ID = re.compile(r"^[A-Za-z]{1,4}\d{1,3}[a-z]?$")


def plan_path(root: Path) -> Path:
    return Path(root) / PLAN_FILE


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def open_checks(root: Path) -> list[str] | None:
    """The plan's check IDs in order, without the superseded ones; None when the game has no readable test plan.
    The results log and any other table whose first column is not "ID" hold no checks."""
    try:
        with plan_path(root).open("rb") as handle:
            text = handle.read(MAX_PLAN_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return None
    checks: list[str] = []
    header = None  # the first cell of the table the line is in
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            header = None
            continue
        cells = _cells(line)
        if header is None:
            header = cells[0].lower()
            continue
        if header != "id" or not CHECK_ID.match(cells[0]):
            continue
        if cells[0] not in checks and not any("superseded" in cell.lower() for cell in cells[1:]):
            checks.append(cells[0])
    return checks
