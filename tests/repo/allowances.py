"""Deliberate exceptions to a structure rule, written where they happen and kept visible.

A line that breaks a rule on purpose carries a comment naming the rule and the reason:

    from ..library.games import _json  # retrodev: allow <rule> — <why this line cannot follow the rule>

(``//`` instead of ``#`` in JavaScript; ``--`` works as well as the dash.) The reason is required. The checks
that honour allowances (tests/repo/test_boundaries.py) skip that line for that rule only, and every allowance
in the repository is printed as a warning on every run (tests/repo/test_layout.py), so none is forgotten.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Rule names an allowance may name, with what the rule protects.
RULES = {
    "front-door": "features use each other only through the names a front door exports",
    "layer": "backend.system imports nothing of ours above it; only the Hermes layer imports backend.features",
    "front-door-export": "a front door does not leak private names",
    "event": "events are declared once by their owner, emitted only by it, and literal",
}
MARK = re.compile(r"(?:#|//)\s*retrodev:\s*allow\s+([\w-]+)\s*(?:(?:—|--)\s*(.*?))?\s*$")


@dataclass(frozen=True)
class Allowance:
    file: str
    line: int
    rule: str
    reason: str

    def problem(self) -> str | None:
        if self.rule not in RULES:
            return f"{self.file}:{self.line}: unknown rule {self.rule!r} (known: {', '.join(sorted(RULES))})"
        if not self.reason:
            return f"{self.file}:{self.line}: allowance for {self.rule} has no reason after '—'"
        return None


def in_text(text: str, file: str) -> list[Allowance]:
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        match = MARK.search(line)
        if match:
            found.append(Allowance(file, number, match.group(1), (match.group(2) or "").strip()))
    return found


def in_files(root: Path, names: list[str]) -> list[Allowance]:
    found = []
    for name in names:
        if name.endswith((".py", ".js", ".mjs")) and not name.startswith(("engine/", "tools/npm/", "desktop/")):
            found += in_text((root / name).read_text(encoding="utf-8", errors="replace"), name)
    return found


def allows(allowances: list[Allowance], file: str, line: int, rule: str) -> bool:
    """Whether ``file:line`` carries a well-formed allowance for ``rule``."""
    return any(a.file == file and a.line == line and a.rule == rule and a.problem() is None for a in allowances)


def warn(allowances: list[Allowance]) -> None:
    for item in allowances:
        print(f"layout warning: allowance {item.file}:{item.line} {item.rule}: {item.reason or '(no reason)'}",
              file=sys.stderr)
