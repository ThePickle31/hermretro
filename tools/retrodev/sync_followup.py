"""What a conflicted sync said about each hunk, carried to the sync that finishes the merge.

The first sync stops on source conflicts with one line per hunk (sync.moved_hints): dev moved, deleted or rewrote
the block this branch changed, and where the change may belong now. Resolving those hunks removes the markers that
advice came from, so the sync that finishes the merge could no longer say it. This module keeps the advice as data
in retrodev's records (sync/<branch>.json), tied to the exact merge: the branch, its HEAD and the MERGE_HEAD it was
merging. A record for another merge (aborted, or replaced by a newer dev) is ignored; finishing the merge, or starting
a new one, removes it. The advice stays advice: dev's version may already do what the branch's lines did, so it says
to check before redoing anything, and never names a destination the first sync did not find.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import repo, state


def _path(ctx) -> Path | None:
    branch = repo.branch(ctx.top) or ""
    parts = branch.split("/")
    if not branch or not all(state.NAME.match(part) for part in parts):
        return None
    return state.root(ctx.top).joinpath("sync", *parts[:-1], parts[-1] + ".json")


def _key(ctx) -> dict:
    return {"branch": repo.branch(ctx.top), "head": repo.head(ctx.top), "merge_head": repo.head(ctx.top, "MERGE_HEAD")}


def _load(ctx) -> dict | None:
    """The record for the merge open now, or None (none kept, unreadable, or kept for another merge)."""
    path = _path(ctx)
    try:
        record = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else None
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or not record.get("merge_head"):
        return None
    return record if all(record.get(name) == value for name, value in _key(ctx).items()) else None


def remember(ctx, hunks: list[dict]) -> None:
    """Keep ``hunks`` (sync.moved_hints' data) for the open merge, adding to what an earlier sync of the same merge
    kept: a later sync sees only the files still unresolved."""
    path = _path(ctx)
    if path is None:
        return
    kept = (_load(ctx) or {}).get("hunks", [])
    merged = kept + [hunk for hunk in hunks if hunk not in kept]
    state.write_atomic(path, json.dumps({**_key(ctx), "hunks": merged}, indent=2, sort_keys=True) + "\n")


def forget(ctx) -> None:
    path = _path(ctx)
    if path is not None:
        path.unlink(missing_ok=True)


def _line(ctx, hunk: dict) -> str:
    # the lines are the conflict markers', gone once resolved: they say which hunk, not where to look now
    at, where, commit = f"{hunk['file']} (conflict lines {hunk['lines']})", hunk.get("where"), hunk.get("commit")
    if hunk.get("kind") == "rewritten":
        if where:
            return (
                f"{at}: {ctx.base} rewrote that block; if {ctx.base}'s version does not already do what your change "
                f"did, redo your change in {where} in its own commit"
            )
        return f"{at}: {ctx.base} rewrote that block; if your change still matters, redo it where it belongs now"
    if where:
        return (
            f"{at}: {ctx.base} moved that block to {where}"
            + (f" in {commit}" if commit else " (or deleted it)")
            + f"; check "
            f"whether {where} already does what your lines did (then add only a test that pins it), else add your "
            "lines there in a new commit"
        )
    return (
        f"{at}: {ctx.base} deleted that block" + (f" (removed in {commit})" if commit else "") + "; if your change "
        "still matters, redo it where it belongs now in a new commit"
    )


def advice(ctx, conflicted: list[str] | None, generated: set[str]) -> list[str]:
    """The lines to print once the merge is finished: the kept per-hunk advice for this exact merge; without a record
    for it, a general reminder naming the source files the merge conflicted in (``conflicted``, from git merge-tree);
    nothing for a merge whose conflicts the first sync gave no advice for, or that conflicted in no source file."""
    record = _load(ctx)
    if record is not None:
        hunks = record.get("hunks") or []
        if not hunks:
            return []
        head = "follow up after the merge (what the first sync said about these hunks; advice, not a check):"
        return [head, *("  " + _line(ctx, hunk) for hunk in hunks)]
    sources = [name for name in conflicted or [] if name not in generated]
    if not sources:
        return []
    return [
        f"follow up after the merge: it conflicted in {', '.join(sources)}; if {ctx.base} moved or rewrote code your "
        "side changed there, check that your change is still in effect, else redo it where that code lives now in "
        "a new commit (advice, not a check)"
    ]
