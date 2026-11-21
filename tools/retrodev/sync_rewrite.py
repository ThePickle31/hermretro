"""Where a change belongs after the base branch rewrote the block it changed (sync's rewrite hint).

A hunk where dev's side is much longer than HEAD's, and HEAD's changed lines are modified copies of lines dev
removed (rewritten_from), means dev rewrote the block: a table row into a subsection, say. new_location then names
where HEAD's change belongs now: for a table row of a markdown file, the subsection headed with the row's first cell
(`### Prompts` for `| Prompts | ... |`); else the markdown block (a heading and its lines) most like HEAD's lines, never a
table row for a row's details; else the line most like them. When the best two are close it names no place (AMBIGUOUS),
and the hint points to the diff instead.
"""

from __future__ import annotations

import difflib
import re

REWRITE_RATIO = 0.6  # difflib ratio: HEAD's changed line is a modified copy of a line dev removed
LONGER = 2  # dev's side of the hunk has at least this many times HEAD's lines (and at least 3)
CLOSE = 0.05  # the best two places' scores this close or closer: no place is named
AMBIGUOUS = "ambiguous"


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def rewritten_from(ours: str, theirs: str, base: list[str], dev: list[str]) -> list[str]:
    """HEAD's changed lines of a hunk that are modified copies of lines dev removed, when dev's side of the hunk is
    much longer than HEAD's (dev rewrote the block, e.g. a table row into a subsection); [] otherwise."""
    mine = [line.strip() for line in ours.splitlines() if line.strip()]
    others = [line for line in theirs.splitlines() if line.strip()]
    if not mine or len(others) < max(3, LONGER * len(mine)):
        return []
    had, kept = {line.strip() for line in base}, {line.strip() for line in dev}
    removed = [line for line in had if line and line not in kept]
    changed = [line for line in mine if line not in had]
    if not changed or not removed:
        return []
    copies = [line for line in changed if max(similarity(line, old) for old in removed) > REWRITE_RATIO]
    return copies if len(copies) == len(changed) else []


def is_row(line: str) -> bool:
    return line.strip().startswith("|")


def plain(text: str) -> str:
    """A heading's or a cell's words, without markup or case: `### **Prompts**` and `| `Prompts` |` are both `prompts`."""
    return " ".join(re.sub(r"[`*_]", " ", text.strip().lstrip("#")).split()).lower()


def first_cell(row: str) -> str:
    return plain(row.strip().strip("|").split("|")[0])


def headings(dev: list[str]) -> list[int]:
    """The 0-based indexes of dev's markdown headings outside code fences."""
    found, fenced = [], False
    for index, line in enumerate(dev):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,6}\s", line):
            found.append(index)
    return found


def best(scored: list[tuple[float, str, object]]) -> str:
    """The place of the highest (score, place, group), or AMBIGUOUS when the best one of another group (another
    subsection) is within CLOSE of it; the earlier place wins a tie within a group."""
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)
    rival = next((item for item in ranked if item[2] != ranked[0][2]), None)
    if rival and ranked[0][0] - rival[0] <= CLOSE:
        return AMBIGUOUS
    return ranked[0][1]


def subsection(name: str, changed: list[str], dev: list[str], base: list[str]) -> str | None:
    """For changed table rows: the place of dev's heading whose text is the rows' first cell; else of the block
    (heading and its lines, table rows left out) most like the rows, among blocks dev added lines to; AMBIGUOUS when
    several match about as well; None when no block qualifies."""
    starts = headings(dev)
    cells = {first_cell(row) for row in changed} - {""}
    had = {line.strip() for line in base}
    named = [i for i in starts if plain(dev[i]) in cells]
    added = [i for i in named if dev[i].strip() not in had]
    named = added if len(named) > 1 and len(added) == 1 else named
    if len(named) == 1:
        return f"the `{dev[named[0]].strip()}` subsection at {name}:{named[0] + 1}"
    if len(named) > 1:
        return AMBIGUOUS
    mine = " ".join(changed)
    scored = []
    for start, end in zip([0, *starts], [*starts, len(dev)], strict=True):
        lines = [line.strip() for line in dev[start:end] if line.strip() and not is_row(line)]
        if not any(line not in had for line in lines if not line.startswith("#")):
            continue
        heading = dev[start].strip() if start in starts else None
        where = f"the `{heading}` subsection at {name}:{start + 1}" if heading else f"{name}:{start + 1}"
        scored.append((similarity(" ".join(lines), mine), where, start))
    return best(scored) if scored else None


def new_location(name: str, changed: list[str], dev: list[str], base: list[str]) -> str | None:
    """Where on the base branch HEAD's change belongs now (see the module's docstring): a place, AMBIGUOUS, or None
    when dev added nothing alike."""
    markdown = name.endswith(".md")
    if markdown and all(is_row(line) for line in changed):
        return subsection(name, changed, dev, base)
    had = {line.strip() for line in base}
    scored = [
        (max(similarity(line.strip(), mine) for mine in changed), number)
        for number, line in enumerate(dev, 1)
        if line.strip() and line.strip() not in had
    ]
    if not scored:
        return None
    places, starts = [], headings(dev) if markdown else []
    for score, number in scored:
        above = [i for i in starts if i < number - 1]
        heading = dev[above[-1]].strip() if above else None
        group = (above[-1] if above else None) if markdown else number
        places.append((score, f"{name}:{number}" + (f" (under `{heading}`)" if heading else ""), group))
    return best(places)
