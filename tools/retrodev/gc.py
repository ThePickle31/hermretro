"""Tidy up after merged work: finished worktrees, their branches and records, and bytecode-only leftovers.

    gc [--dry-run]

A worktree goes only when its branch is done and nothing in it would be lost: it has no uncommitted changes, it
was pushed, and its branch is merged into the base branch, its pull request is merged (squash merges leave no
ancestry), or the remote deleted the branch while it still pointed at what was pushed. A dirty or never-pushed
worktree is always kept, and said why; a worktree whose folder was deleted by hand loses only git's note of
it, never its branch, unless that branch passes the same checks. It also removes folders in the main checkout
whose whole subtree holds nothing but bytecode caches and empty folders (left behind when a package moved).
--dry-run fetches nothing and changes nothing.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import github, repo, state

SKIP_DIRS = {".git", ".dev", "node_modules", "notes"}


def remote_shas(ctx) -> dict[str, str]:
    prefix = f"refs/remotes/{ctx.remote}/"
    out = repo.git(["for-each-ref", "--format=%(refname) %(objectname)", prefix], ctx.main())
    return {ref.removeprefix(prefix): sha for ref, sha in (line.split() for line in out.splitlines())}


def verdict(ctx, tree: repo.Worktree, record: dict, before: dict, after: dict) -> tuple[bool, str]:
    """(remove?, why) for one worktree. A missing folder proves nothing: its branch is judged like any other."""
    branch, main = tree.branch, ctx.main()
    if not branch:
        return False, "detached HEAD"
    if branch in ctx.policy["branches"]["protected"]:
        return False, "a protected branch"
    gone = "its folder is gone; " if not tree.path.is_dir() else ""
    if not gone:
        changes = repo.dirty(tree.path)
        if changes:
            return False, f"{len(changes)} uncommitted change(s) (never removed)"
    tip = repo.head(main, f"refs/heads/{branch}") or tree.head or ""
    pushed = record.get("pushed") or before.get(branch) or after.get(branch)
    if not pushed:
        return False, gone + "never pushed"
    if pushed != tip and not repo.is_ancestor(main, tip, pushed):
        return False, gone + "has commits that were never pushed"
    base = ctx.remote_base
    if repo.head(main, base) and repo.is_ancestor(main, tip, base):
        return True, gone + f"merged into {base}"
    number = (record.get("pr") or {}).get("number")
    if number and github.pr_state(ctx, number) == "MERGED":
        return True, gone + f"pull request #{number} merged"
    if branch not in after:
        return True, gone + f"deleted on {ctx.remote} after it was pushed"
    return False, gone + "still open"


def leftover_folders(main: Path) -> list[Path]:
    """The top-most folders under ``main`` whose whole subtree is bytecode (at least one file) and empty folders.

    Nothing is skipped unseen: a folder retrodev does not look into (.git, notes, node_modules, any hidden one),
    a symlink (never followed), an unreadable folder or any other file is content, so no folder above it goes.
    """
    blocked: set[Path] = set()  # folders holding something other than bytecode, somewhere below
    code: set[Path] = set()  # folders holding bytecode, somewhere below

    def mark(found: set[Path], path) -> None:
        path = Path(path)
        while path != main and main in path.parents and path not in found:
            found.add(path)
            path = path.parent

    def unreadable(error: OSError) -> None:
        mark(blocked, error.filename or main)

    for folder, dirs, files in os.walk(main, onerror=unreadable):
        here = Path(folder)
        for name in list(dirs):
            if name in SKIP_DIRS or name.startswith(".") or (here / name).is_symlink():
                mark(blocked, here)
                dirs.remove(name)
        for name in files:
            path = here / name
            bytecode = name.endswith((".pyc", ".pyo")) and not path.is_symlink() and path.is_file()
            mark(code if bytecode else blocked, here)
    only = code - blocked
    return sorted(folder for folder in only if folder.name != "__pycache__" and folder.parent not in only)


def run(ctx, dry_run: bool = False) -> int:
    main = ctx.main()
    before = remote_shas(ctx)
    if dry_run:
        after = before
        ctx.out.say(f"dry run: using {ctx.remote}'s branches from the last fetch; nothing is changed")
    else:
        repo.git(["fetch", "--quiet", "--prune", ctx.remote], main)
        after = remote_shas(ctx)
    records = {record.get("branch"): record for record in state.branches(main)}
    removed, kept = [], []
    for tree in repo.worktrees(main):
        if tree.main:
            continue
        remove, why = verdict(ctx, tree, records.get(tree.branch, {}), before, after)
        (removed if remove else kept).append({"path": str(tree.path), "branch": tree.branch, "why": why})
        ctx.out.say(f"{'remove' if remove else 'keep':>6}  {tree.path}  ({tree.branch}: {why})")
        if not tree.path.is_dir() and not dry_run:
            repo.git(["worktree", "prune"], main)  # only git's note of the folder; the branch is judged above
        if remove and not dry_run:
            if tree.path.is_dir():
                repo.git(["worktree", "remove", str(tree.path)], main)
            repo.git(["branch", "-D", tree.branch], main)
            state.drop_branch(main, tree.branch)
    live = {tree.branch for tree in repo.worktrees(main)} if not dry_run else set()
    local = set(repo.git(["for-each-ref", "--format=%(refname:short)", "refs/heads/"], main).split())
    stale = [name for name in records if name and name not in local and (dry_run or name not in live)]
    for name in stale:
        ctx.out.say(f"{'forget':>6}  record of {name} (the branch no longer exists)")
        if not dry_run:
            state.drop_branch(main, name)
    folders = leftover_folders(main)
    for folder in folders:
        ctx.out.say(f"{'remove':>6}  {folder}/ (only bytecode caches left)")
        if not dry_run:
            shutil.rmtree(folder)
    if not (removed or stale or folders):
        ctx.out.say("nothing to tidy")
    ctx.out.set(dry_run=dry_run, removed=removed, kept=kept, forgotten=stale, folders=[str(f) for f in folders])
    return 0
