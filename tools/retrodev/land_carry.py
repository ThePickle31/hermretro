"""A head that only merged the base branch after its review keeps that review (land; `sync` makes such heads).

The reviewed head is the last round's clean head, or the head accepted with round 3's fixes. A later head counts as
reviewed when it descends from it, every commit since (beyond the base branch's own) is a merge or touches only
generated files, and the merges changed nothing of their own: the head's tree is what git merges the reviewed head
and the base branch into by itself (git merge-tree), generated files aside. What a conflict resolution changed
beyond that is counted in lines: up to policy.toml [land] max_sync_resolution_lines it is accepted and recorded
(record['carried'], shown by summary as "merge resolution, not reviewed: N lines"); more, and the review round is
due as before. Anything this cannot judge (a git error, a binary file, a conflict on a binary file even when the
resolution kept one side whole) keeps today's rule: a new head is reviewed.
"""

from __future__ import annotations

from pathlib import Path

from . import repo, reviews, state
from .review import records


def reviewed_head(rec: dict) -> str | None:
    """The head the reviews cleared: the last round's clean head, or the head accepted after round 3."""
    rounds = records.valid_rounds(rec)
    if rec.get("skipped") or not rounds or rec["rounds"][-1].get("stopped"):
        return None
    if rounds[-1]["result"]["verdict"] == "clean":
        return rounds[-1]["sha"]
    if len(rounds) >= records.MAX_ROUNDS:
        return (rec.get("accepted") or {}).get("head")
    return None


def only_merges(ctx, tree: Path, reviewed: str, head: str, generated: list[str]) -> bool:
    """Every commit after ``reviewed`` that the base branch lacks is a merge, or touches only generated files."""
    merges = 0
    for line in repo.git(["rev-list", "--parents", head, "^" + reviewed, "^" + ctx.remote_base], tree).splitlines():
        shas = line.split()
        if len(shas) > 2:
            merges += 1
            continue
        files = repo.git(["diff-tree", "--no-commit-id", "--name-only", "-r", shas[0]], tree).split()
        if not files or any(name not in generated for name in files):
            return False
    return merges > 0


def resolution_lines(ctx, tree: Path, reviewed: str, head: str, generated: list[str]) -> int | None:
    """Lines the head differs from git's own merge of ``reviewed`` and the base it merged (None: cannot tell)."""
    point = repo.git(["merge-base", ctx.remote_base, head], tree).strip()
    code, out, _err = repo.run(
        ["git", "merge-tree", "--write-tree", "--name-only", "--no-messages", reviewed, point], tree
    )
    if code not in (0, 1) or not out.split():
        return None
    merged, _, info = out.partition("\n")
    conflicted = sorted({name for name in info.partition("\n\n")[0].splitlines() if name and name not in generated})
    if code == 1 and conflicted and not lines_judge(tree, reviewed, point, conflicted):
        return None  # a binary conflict: git's merge kept one side whole, so the head's line count says nothing
    excluded = [f":(exclude){name}" for name in generated]
    stat = repo.git(["diff", "--numstat", "--no-renames", merged, head, "--", ".", *excluded], tree)
    total = 0
    for line in stat.splitlines():
        added, removed, _name = line.split("\t", 2)
        if added == "-" or removed == "-":
            return None  # a binary file: no line count, so it is reviewed
        total += int(added) + int(removed)
    return total


def lines_judge(tree: Path, reviewed: str, point: str, conflicted: list[str]) -> bool:
    """Every conflicted path is text on both sides, so its resolution can be counted in lines."""
    paths = [f":(literal){name}" for name in conflicted]
    stat = repo.git(["diff", "--numstat", "--no-renames", reviewed, point, "--", *paths], tree)
    return all(line.split("\t", 2)[:2] != ["-", "-"] for line in stat.splitlines())


def carry(ctx, tree: Path | None, rec: dict, head: str, save: bool = True) -> dict:
    """Record ``head`` as reviewed (rec['carried']) when it only merged the base branch after the reviewed head."""
    reviewed = reviewed_head(rec)
    if not tree or not reviewed or head == reviewed or records.reviewed_as(rec, head) != head:
        return rec
    generated = list(ctx.policy.get("generated", {}).get("files", []))
    limit = int(ctx.policy.get("land", {}).get("max_sync_resolution_lines", 20))
    try:
        if not repo.is_ancestor(tree, reviewed, head) or not only_merges(ctx, tree, reviewed, head, generated):
            return rec
        lines = resolution_lines(ctx, tree, reviewed, head, generated)
    except (repo.GitError, ValueError):
        return rec
    if lines is None:
        return rec
    if lines > limit:
        ctx.out.say(
            f"{head[:9]} merged {ctx.base} after the review of {reviewed[:9]}, and its merge resolution changed "
            f"{lines} lines (over [land] max_sync_resolution_lines = {limit}): that needs a review"
        )
        ctx.out.set(sync_resolution=lines)
        return rec
    entry = {"head": head, "reviewed": reviewed, "resolution_lines": lines, "at": state.now()}
    rec.setdefault("carried", []).append(entry)
    if save:
        reviews.save(ctx, rec)
    ctx.out.say(
        f"{head[:9]} only merged {ctx.base} after the review of {reviewed[:9]}: the review carries over"
        + (f" (merge resolution, not reviewed: {lines} lines; recorded)" if lines else "")
    )
    ctx.out.set(carried=entry)
    return rec
