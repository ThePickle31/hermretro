"""Tidy up after merged work: finished worktrees, their branches and records, and bytecode-only leftovers.

    gc [--dry-run]

A worktree goes only when its branch is done and nothing in it would be lost: it has no uncommitted changes, no
ignored file outside the rebuildable caches policy.toml [gc] lists (notes/, games/, scratch: removing the worktree
would delete them), it was pushed, and its branch is merged into the base branch, its pull request is merged (squash merges leave no
ancestry), or the remote deleted the branch while it still pointed at what was pushed. A dirty or never-pushed
worktree is always kept, and said why; a worktree whose folder was deleted by hand loses only git's note of
it, never its branch, unless that branch passes the same checks. A recorded branch with no worktree (its note
pruned by an earlier gc) is judged again on every run, and goes with its record once it passes them. It also removes folders in the main checkout
whose whole subtree holds nothing but bytecode caches and empty folders (left behind when a package moved).
--dry-run fetches nothing and changes nothing.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import github, repo, state
from .output import cmd

SKIP_DIRS = {".git", ".dev", "node_modules", "notes"}


def remote_shas(ctx) -> dict[str, str]:
    prefix = f"refs/remotes/{ctx.remote}/"
    out = repo.git(["for-each-ref", "--format=%(refname) %(objectname)", prefix], ctx.main())
    return {ref.removeprefix(prefix): sha for ref, sha in (line.split() for line in out.splitlines())}


def held_data(ctx, path: Path) -> list[str]:
    """Ignored paths in a worktree that are not rebuildable caches: removing the worktree would delete them."""
    out = repo.git(
        ["--no-optional-locks", "status", "--porcelain=v1", "-z", "--ignored=matching", "--untracked-files=all"], path
    )
    caches = ctx.policy.get("gc", {}).get("caches", [])
    found = []
    for entry in out.split("\0"):
        if entry.startswith("!! "):
            name = entry[3:]
            leaf = name.rstrip("/").rsplit("/", 1)[-1] + ("/" if name.endswith("/") else "")
            if not (repo.matches(name, caches) or repo.matches(leaf, caches)):
                found.append(name)
    return sorted(found)


def verdict(ctx, tree: repo.Worktree, record: dict, before: dict, after: dict) -> tuple[bool, str, str]:
    """(remove?, why, fix) for one worktree. A missing folder proves nothing: its branch is judged like any other."""
    branch, main = tree.branch, ctx.main()
    if not branch:
        return False, "detached HEAD", ""
    if branch in ctx.policy["branches"]["protected"]:
        return False, "a protected branch", ""
    gone = "its folder is gone; " if not tree.path.is_dir() else ""
    if not gone:
        changes = repo.dirty(tree.path)
        if changes:
            return False, f"{len(changes)} uncommitted change(s) (never removed)", ""
        held = held_data(ctx, tree.path)
        if held:
            names = ", ".join(held[:3]) + (f" and {len(held) - 3} more" if len(held) > 3 else "")
            fix = (
                f"move them out (e.g. into the main checkout's notes/: "
                f"{cmd('mv', tree.path / held[0].rstrip('/'), str(main / 'notes') + '/')}), then run gc again; or remove the worktree by hand once nothing in it is needed"
            )
            return False, f"ignored files that are not caches would be deleted with it: {names}", fix
    tip = repo.head(main, f"refs/heads/{branch}") or tree.head or ""
    pushed = record.get("pushed") or before.get(branch) or after.get(branch)
    if not pushed:
        return False, gone + "never pushed", ""
    if pushed != tip and not repo.is_ancestor(main, tip, pushed):
        return False, gone + "has commits that were never pushed", ""
    base = ctx.remote_base
    if repo.head(main, base) and repo.is_ancestor(main, tip, base):
        return True, gone + f"merged into {base}", ""
    number = (record.get("pr") or {}).get("number")
    if number and github.pr_state(ctx, number) == "MERGED":
        return True, gone + f"pull request #{number} merged", ""
    if branch not in after:
        return True, gone + f"deleted on {ctx.remote} after it was pushed", ""
    return False, gone + "still open", ""


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


def run(ctx, dry_run: bool = False, only: str | None = None) -> int:
    """Tidy everything, or with ``only`` just that branch's worktree, branch and record (land, after a merge)."""
    main = ctx.main()
    before = remote_shas(ctx)
    if dry_run:
        after = before
        ctx.out.say(f"dry run: using {ctx.remote}'s branches from the last fetch; nothing is changed")
    else:
        repo.git(["fetch", "--quiet", "--prune", ctx.remote], main)
        after = remote_shas(ctx)
    records = {record.get("branch"): record for record in state.branches(main)}
    removed, kept, judged, moved = [], [], set(), []

    def judge(tree: repo.Worktree, what: str) -> None:
        remove, why, fix = verdict(ctx, tree, records.get(tree.branch, {}), before, after)
        row = {"path": str(tree.path) if what == "worktree" else None, "branch": tree.branch, "why": why}
        (removed if remove else kept).append(row | ({"fix": fix} if fix else {}))
        judged.add(tree.branch)
        label = str(tree.path) if what == "worktree" else f"branch {tree.branch}, no worktree"
        ctx.out.say(f"{'remove' if remove else 'keep':>6}  {label}  ({tree.branch}: {why})")
        if fix:
            ctx.out.say(f"{'':>6}  FIX: {fix}")
        if what == "worktree" and not tree.path.is_dir() and not dry_run:
            repo.git(["worktree", "prune"], main)  # only git's note of the folder; the branch is judged above
        if remove and not dry_run:
            if what == "worktree" and tree.path.is_dir():
                repo.git(["worktree", "remove", str(tree.path)], main)
                if inside(ctx.started, tree.path):
                    moved.append(str(tree.path))
                    ctx.out.say(f"your shell may still be in {tree.path} (removed): {cmd('cd', main)}")
            repo.git(["branch", "-D", tree.branch], main)
            state.drop_branch(main, tree.branch)

    for tree in repo.worktrees(main):
        if not tree.main and (only is None or tree.branch == only):
            judge(tree, "worktree")
    live = {tree.branch for tree in repo.worktrees(main)}
    local = set(repo.git(["for-each-ref", "--format=%(refname:short)", "refs/heads/"], main).split())
    for name in sorted(n for n in records if n and n in local and n not in live and n not in judged):
        if only is not None and name != only:
            continue
        # Recorded, its branch here, no worktree (an earlier gc pruned a missing folder's note): judged again.
        nowhere = repo.common_dir(main) / "retrodev" / "no-worktree"  # never a folder: judged as gone
        judge(repo.Worktree(path=nowhere, head=None, branch=name, main=False), "branch")
    if not dry_run:
        local = set(repo.git(["for-each-ref", "--format=%(refname:short)", "refs/heads/"], main).split())
    gone = {row["branch"] for row in removed}
    stale = [name for name in records if name and name not in local and name not in gone and name not in live]
    stale = [name for name in stale if only is None or name == only]
    for name in stale:
        ctx.out.say(f"{'forget':>6}  record of {name} (the branch no longer exists)")
        if not dry_run:
            state.drop_branch(main, name)
    folders = leftover_folders(main) if only is None else []
    for folder in folders:
        ctx.out.say(f"{'remove':>6}  {folder}/ (only bytecode caches left)")
        if not dry_run:
            shutil.rmtree(folder)
    if not (removed or stale or folders):
        ctx.out.say("nothing to tidy")
    ctx.out.set(dry_run=dry_run, removed=removed, kept=kept, forgotten=stale, folders=[str(f) for f in folders])
    if moved:
        ctx.out.set(cd=str(main), started_in_removed=moved[0])
    return 0


def inside(path: Path, folder: Path) -> bool:
    """Whether ``path`` is ``folder`` or below it (resolved: symlinked temp folders compare equal)."""
    path, folder = Path(path).resolve(), Path(folder).resolve()
    return path == folder or folder in path.parents
