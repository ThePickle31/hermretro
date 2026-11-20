"""Where dev took the lines of a conflict hunk it removed: for sync's per-hunk hint.

The branch's side of a hunk holds its own new lines, which can never be on dev, so the search uses the base side:
the diff3/zdiff3 '|||||||' part when git wrote one, else the merge base's lines dev removed, in the region the hunk's
unchanged context places it in `:1:<path>` (the index's merge-base stage), that the branch's lines are edited copies of. base_lines gives those; taken_over names the dev
commit that removed the first of them and the other file it added the most similar line to (never a generated file).
"""

from __future__ import annotations

from . import repo
from .sync_rewrite import similarity

COPY_RATIO = 0.5  # difflib ratio: the branch's line is an edited copy of the base line (or dev's new line of it)


def base_parts(text: str) -> list[str]:
    """The '|||||||' (common ancestor) part of each conflict hunk, in conflict_hunks' order ('' without diff3)."""
    parts, part, base = [], None, []
    for line in text.splitlines():
        if line.startswith("<<<<<<<"):
            part, base = "ours", []
        elif part and line.startswith("|||||||"):
            part = "base"
        elif part and line.startswith("======="):
            part = "theirs"
        elif part and line.startswith(">>>>>>>"):
            parts.append("\n".join(base))
            part = None
        elif part == "base":
            base.append(line)
    return parts


def _lines(ctx, spec: str) -> list[str]:
    data = repo.blob(ctx.top, spec)
    content = repo.text(data) if data is not None else None
    return content.splitlines() if content else []


CONTEXT = 5  # unchanged lines at most on each side of a hunk that place it in the merge base's file


def _find(base: list[str], lines: list[str], last: bool) -> int | None:
    """Where the shortest unique run of ``lines`` next to the hunk (their end when ``last``) is in ``base``: the index
    just past it (above the hunk) or of its first line (below); None when no run is unique."""
    for size in range(1, len(lines) + 1):
        run = lines[-size:] if last else lines[:size]
        found = [i for i in range(len(base) - size + 1) if base[i : i + size] == run]
        if len(found) == 1:
            return found[0] + size if last else found[0]
        if not found:
            return None
    return None


def _context(text: str, first: int, last: int) -> tuple[list[str], list[str]]:
    """The unchanged lines just above and just below the hunk (markers at lines first..last, 1-based), stopping at
    another hunk's marker."""
    lines = text.splitlines()
    markers = ("<<<<<<<", "|||||||", "=======", ">>>>>>>")
    above, below = [], []
    for line in reversed(lines[max(0, first - 1 - CONTEXT) : first - 1]):
        if line.startswith(markers):
            break
        above.insert(0, line)
    for line in lines[last : last + CONTEXT]:
        if line.startswith(markers):
            break
        below.append(line)
    return above, below


def _region(base: list[str], text: str, first: int, last: int) -> list[str]:
    """The merge base's lines this hunk replaces, placed by its unchanged context lines; [] when either side of it
    is not found in exactly one place (a guess could name another hunk's destination)."""
    above, below = _context(text, first, last)
    start = _find(base, above, last=True) if above else (0 if first == 1 else None)
    end = _find(base, below, last=False) if below else (len(base) if last == len(text.splitlines()) else None)
    if start is None or end is None or end < start:
        return []
    return base[start:end]


def base_lines(
    ctx, name: str, ours: str, base_part: str = "", text: str = "", first: int = 0, last: int = 0
) -> list[str]:
    """The merge base's lines dev removed that this hunk's branch side changed: the diff3 base part when there is
    one, else the lines of the base's region of this hunk (placed by its context in ``text``, the conflicted file;
    lines first..last its markers) missing from dev's file that a line of ours is an edited copy of (stripped)."""
    if base_part.strip():
        return [line.strip() for line in base_part.splitlines() if line.strip()]
    base, dev = _lines(ctx, f":1:{name}"), set(_lines(ctx, f"MERGE_HEAD:{name}"))
    region = _region(base, text, first, last) if first else []
    removed = [line for line in dict.fromkeys(region) if line.strip() and line not in dev]
    mine = [line.strip() for line in ours.splitlines() if line.strip()]
    if not removed or not mine:
        return []
    scored = [(max(similarity(old.strip(), line) for line in mine), old.strip()) for old in removed]
    return [old for score, old in sorted(scored, key=lambda pair: -pair[0]) if score > COPY_RATIO]


def taken_over(ctx, name: str, line: str) -> tuple[str | None, str | None]:
    """(the other file dev's commit that removed ``line`` from ``name`` added the most similar line to, that commit
    as '<sha> (<subject>)'); (None, the commit) when it added no such line elsewhere, added equally close lines to
    two files, or MERGE_HEAD no longer has that line in that file (renamed, deleted or changed later); (None, None) without one."""
    merge_base = repo.git(["merge-base", "HEAD", "MERGE_HEAD"], ctx.top, check=False).strip()
    span = f"{merge_base}..MERGE_HEAD" if merge_base else "MERGE_HEAD"
    found = repo.git(["log", "-1", "--format=%h%x00%s", f"-S{line}", span, "--", name], ctx.top, check=False).strip()
    if not found:
        return None, None
    sha, _, subject = found.partition("\0")
    commit = f"{sha} ({subject})"
    generated = set(ctx.policy["generated"]["files"])
    shown = repo.git(["show", "--format=", "--unified=0", "--no-color", sha], ctx.top, check=False)
    best, where, current, added, tied = COPY_RATIO, None, None, "", False
    for row in shown.splitlines():
        if row.startswith("+++ "):
            current = row[6:] if row.startswith("+++ b/") else None
        elif row.startswith("+") and current and current != name and current not in generated:
            score = similarity(row[1:].strip(), line)
            if score > best:
                best, where, added, tied = score, current, row[1:], False
            elif score == best and where and current != where:
                tied = True
    # two files took an equally close line: no evidence says which one this hunk belongs in, so name neither
    if tied:
        where = None
    # a later dev commit may have renamed or deleted that file, or changed the line: name it only while dev has it
    if where and _norm(added) not in {_norm(held) for held in _lines(ctx, f"MERGE_HEAD:{where}")}:
        where = None
    return where, commit


def _norm(line: str) -> str:
    return " ".join(line.split())
