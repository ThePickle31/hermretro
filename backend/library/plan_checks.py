"""A game's test plan: ``docs/game/TEST-PLAN.md``, written with the hermretro:game-planning skill. Every build
report of a game with one gives each of its open checks a result (``report_tools.py``). Standard library only."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PLAN_FILE = Path("docs", "game", "TEST-PLAN.md")
MAX_PLAN_BYTES = 256 * 1024
# A check's ID: 1 to 4 letters, an optional hyphen, 1 to 3 digits and an optional letter (T1, AUD2, GATE-1, T3b),
# in any case: T3B and t3b are the same check.
CHECK_ID = re.compile(r"^[A-Za-z]{1,4}-?\d{1,3}[A-Za-z]?$")
MAX_CHECK_ID = 9
# The checks one build report holds; a plan with more open checks cannot be reported (report_tools.py says so).
MAX_CHECKS = 100
# A check written as a line instead of a table row: "T1: Given ..., when ..., then ...".
CHECK_LINE = re.compile(r"^\s*(?:[-*+]\s+)?[`*_]*([A-Za-z0-9-]+)[`*_]*\s*:\s+(.*)$")
LINE_SUPERSEDED = re.compile(r"^\W*superseded\b|\bstatus\s*:\s*superseded\b", re.IGNORECASE)
STATUS_COLUMNS = ("status", "result")


@dataclass(frozen=True)
class Plan:
    checks: list[str]  # the open check IDs in order, as the plan writes them
    unreadable: list[str]  # first cells of check-table rows that are no check ID


def plan_path(root: Path) -> Path:
    return Path(root) / PLAN_FILE


def check_key(identifier: str) -> str:
    """The form two check IDs are compared in: T3b, T3B and t3b are one check."""
    return identifier.upper()


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _identifier(cell: str) -> str:
    return cell.strip("`*_ ")


def read_plan(root: Path) -> Plan | None:
    """The plan's open checks, None when the game has no readable test plan. A check is a row of a table whose
    first column is "ID", superseded when its Status (or Result) cell says so, or a line ``T1: ...`` outside the
    results sections, superseded when it starts with or gives "Status: superseded". The results log and any other
    table whose first column is not "ID" hold no checks."""
    try:
        with plan_path(root).open("rb") as handle:
            text = handle.read(MAX_PLAN_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return None
    checks: list[str] = []
    unreadable: list[str] = []
    seen: set[str] = set()

    def add(identifier: str, superseded: bool) -> None:
        if check_key(identifier) not in seen:
            seen.add(check_key(identifier))
            if not superseded:
                checks.append(identifier)

    header = None  # the header cells of the table the line is in
    in_results = False
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            in_results = "result" in line.lower()
        if not line.lstrip().startswith("|"):
            header = None
            match = CHECK_LINE.match(line)
            if not in_results and match and CHECK_ID.match(match[1]):
                add(match[1], bool(LINE_SUPERSEDED.search(match[2])))
            continue
        cells = _cells(line)
        if header is None:
            header = [cell.lower() for cell in cells]
            continue
        identifier = _identifier(cells[0])
        if header[0] != "id" or not identifier or not identifier.strip(":- "):
            continue  # another table, an empty cell or the separator row
        if not CHECK_ID.match(identifier):
            unreadable.append(identifier)
            continue
        status = next((index for index, name in enumerate(header) if name in STATUS_COLUMNS), None)
        add(identifier, status is not None and status < len(cells) and "superseded" in cells[status].lower())
    return Plan(checks, unreadable)
