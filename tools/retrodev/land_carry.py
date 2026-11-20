"""A head that only merged the base branch after its review keeps that review (land; `sync` makes such heads).

The reviewed head is the last round's clean head, or the head accepted with round 3's fixes. A later head counts as
reviewed when it descends from it, every commit since (beyond the base branch's own) is a merge or touches only
generated files, and the merges changed nothing of their own: the head's tree is what git merges the reviewed head
and the base branch into by itself (git merge-tree), generated files aside. What a conflict resolution changed
beyond that is counted in lines of code (a change only to a comment counts 0, by conservative rules: code_lines.py):
up to policy.toml [land] max_sync_resolution_lines it is accepted and recorded
(record['carried'], shown by summary as "merge resolution, not reviewed: N lines"); more, and the review round is
due as before. Anything this cannot judge (a git error, git output it cannot read, a binary file, a conflict on a
binary file even when the resolution kept one side whole) keeps today's rule: a new head is reviewed. Paths are read
NUL-delimited (-z), so a name git would quote (non-ASCII, a double quote) is still the real file.
"""

from __future__ import annotations

from pathlib import Path

from . import code_lines, repo, reviews, state
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
    code, out, _err = repo.run(["git", "merge-tree", "--write-tree", "--name-only", "-z", reviewed, point], tree)
    parsed = merge_tree_output(code, out)
    if parsed is None:
        return None  # output this cannot read: reviewed
    merged, conflicted = parsed
    conflicted = sorted({name for name in conflicted if name not in generated})
    if conflicted and not lines_judge(tree, reviewed, point, conflicted):
        return None  # a binary conflict: git's merge kept one side whole, so the head's line count says nothing
    excluded = [f":(exclude){name}" for name in generated]
    stat = numstat(tree, [merged, head, "--", ".", *excluded])
    if stat is None or any(added is None for added, _removed, _name in stat):
        return None  # a binary file: no line count, so it is reviewed
    # Only code counts: a line whose change is only in a comment is no resolution to review (code_lines.py).
    base = repo.git(["merge-base", reviewed, point], tree).strip()
    total = 0
    for name in (name for added, removed, name in stat if added or removed):
        texts = {rev: blob(tree, rev, name) for rev in (reviewed, base, point, merged, head)}
        if any(text is None for text in texts.values()):
            return None  # a version git counted in lines but that is not UTF-8 text: no line count, so reviewed
        before = None
        if name in conflicted:  # both sides' code, merged without their comments
            before = code_lines.merge_code(tree, name, *(texts[rev] or "" for rev in (reviewed, base, point)))
        if before is None:
            before = code_lines.code(name, texts[merged] or "")
        total += code_lines.count(before, code_lines.code(name, texts[head] or ""))
    return total


def blob(tree: Path, rev: str, name: str) -> str | None:
    """The file ``name`` at ``rev`` ("" when it is not there: added or deleted on one side; None when it is binary,
    a NUL byte or bytes that are not UTF-8: read as bytes, never decoded as text)."""
    data = repo.blob(tree, f"{rev}:{name}")
    return "" if data is None else repo.text(data)


def merge_tree_output(code: int, out: str) -> tuple[str, list[str]] | None:
    """The merged tree and the conflicted paths from ``git merge-tree --write-tree --name-only -z`` (None: unclear).

    Clean (exit 0): the tree id and a NUL. Conflicts (exit 1): the tree id, each conflicted path, an empty field,
    then the informational messages. Paths come unquoted, so any name (quotes, non-ASCII, newlines) reads as is."""
    oid, sep, rest = out.partition("\0")
    if not sep or len(oid) not in (40, 64) or any(c not in "0123456789abcdef" for c in oid):
        return None
    if code == 0:
        return (oid, []) if rest == "" else None
    if code != 1:
        return None
    paths, sep, messages = rest.partition("\0\0")
    names = paths.split("\0")
    if not sep or not paths or not messages.endswith("\0") or not all(names):
        return None
    return oid, names


def numstat(tree: Path, args: list[str]) -> list[tuple[int | None, int | None, str]] | None:
    """``git diff --numstat -z --no-renames`` rows; a binary file counts None lines (None: output unclear)."""
    rows = []
    for record in repo.git(["diff", "--numstat", "-z", "--no-renames", *args], tree).split("\0"):
        if not record:
            continue
        fields = record.split("\t", 2)
        if len(fields) != 3 or not fields[2]:
            return None
        if fields[:2] == ["-", "-"]:
            rows.append((None, None, fields[2]))
        elif fields[0].isdigit() and fields[1].isdigit():
            rows.append((int(fields[0]), int(fields[1]), fields[2]))
        else:
            return None
    return rows


def lines_judge(tree: Path, reviewed: str, point: str, conflicted: list[str]) -> bool:
    """Every conflicted path differs as text between the two sides, so its resolution can be counted in lines."""
    stat = numstat(tree, [reviewed, point, "--", *(f":(literal){name}" for name in conflicted)])
    if stat is None or {name for _a, _r, name in stat} != set(conflicted):
        return False  # unreadable, or a conflicted path the diff did not show: nothing was checked, so reviewed
    return all(added is not None for added, _removed, _name in stat)


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
