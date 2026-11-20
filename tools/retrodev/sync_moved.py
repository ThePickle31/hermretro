"""Where dev took the lines of a conflict hunk it removed: for sync's per-hunk hint.

The branch's side of a hunk holds its own new lines, which can never be on dev, so the search uses the base side:
the diff3/zdiff3 '|||||||' part when git wrote one, else the merge base's lines dev removed that the branch's lines
are edited copies of (`:1:<path>`, the index's merge-base stage). base_lines gives those; taken_over names the dev
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


def base_lines(ctx, name: str, ours: str, base_part: str = "") -> list[str]:
    """The merge base's lines dev removed that this hunk's branch side changed: the diff3 base part when there is
    one, else the base's lines missing from dev's file that a line of ours is an edited copy of (stripped)."""
    if base_part.strip():
        return [line.strip() for line in base_part.splitlines() if line.strip()]
    base, dev = _lines(ctx, f":1:{name}"), set(_lines(ctx, f"MERGE_HEAD:{name}"))
    removed = [line for line in dict.fromkeys(base) if line.strip() and line not in dev]
    mine = [line.strip() for line in ours.splitlines() if line.strip()]
    if not removed or not mine:
        return []
    scored = [(max(similarity(old.strip(), line) for line in mine), old.strip()) for old in removed]
    return [old for score, old in sorted(scored, key=lambda pair: -pair[0]) if score > COPY_RATIO]


def taken_over(ctx, name: str, line: str) -> tuple[str | None, str | None]:
    """(the other file dev's commit that removed ``line`` from ``name`` added the most similar line to, that commit
    as '<sha> (<subject>)'); (None, the commit) when it added no such line elsewhere; (None, None) without one."""
    merge_base = repo.git(["merge-base", "HEAD", "MERGE_HEAD"], ctx.top, check=False).strip()
    span = f"{merge_base}..MERGE_HEAD" if merge_base else "MERGE_HEAD"
    found = repo.git(["log", "-1", "--format=%h%x00%s", f"-S{line}", span, "--", name], ctx.top, check=False).strip()
    if not found:
        return None, None
    sha, _, subject = found.partition("\0")
    commit = f"{sha} ({subject})"
    generated = set(ctx.policy["generated"]["files"])
    shown = repo.git(["show", "--format=", "--unified=0", "--no-color", sha], ctx.top, check=False)
    best, where, current = COPY_RATIO, None, None
    for row in shown.splitlines():
        if row.startswith("+++ "):
            current = row[6:] if row.startswith("+++ b/") else None
        elif row.startswith("+") and current and current != name and current not in generated:
            score = similarity(row[1:].strip(), line)
            if score > best:
                best, where = score, current
    return where, commit
