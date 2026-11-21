"""Throwaway checkouts: `try <pr>` runs a pull request's full checks in one, and the release commands run the
clean install (with its update check) in one at the release commit.

try's required checks are fixed by the launcher (the fast ones, scaffold nested, acceptance, the clean
install and the update from the newest published release), whatever the pull request changed: its own suite, kept
apart from what a draft push needs (`check`) and from `check --full`.

    try <pr> [--keep] [--no-setup]

A throwaway checkout is a detached git worktree in a short temp folder outside the repository (short: the checks
open Unix sockets, whose paths are limited to about 104 characters). It is removed afterwards (the folder, then
`git worktree prune` drops git's note of it), unless --keep: then its path is printed with the commands that
remove it. The pull request's head comes from `<remote> refs/pull/<n>/head`, so a pull request from a fork works
too, and nothing is checked out in any worktree an agent works in.
"""

from __future__ import annotations

import contextlib
import shlex
import shutil
import sys
import tempfile
from pathlib import Path

from . import checks, repo, start
from .output import Failure


def temp_root(ctx) -> str:
    """Where throwaway checkouts go (tests point it into their own folder)."""
    return str(ctx.fakes.get("tmp_root") or checks.short_tmp())


def add(ctx, sha: str, label: str) -> Path:
    """A detached worktree at ``sha`` in a new short temp folder."""
    folder = Path(tempfile.mkdtemp(prefix=f"rd-{label}-", dir=temp_root(ctx))).resolve()
    path = folder / "tree"
    repo.git(["worktree", "add", "--quiet", "--detach", str(path), sha], ctx.main())
    return path


def remove(ctx, path: Path) -> None:
    """Delete the throwaway folder, then git's note of the worktree (no forced removal needed)."""
    shutil.rmtree(path.parent, ignore_errors=True)
    repo.git(["worktree", "prune"], ctx.main(), check=False)


@contextlib.contextmanager
def throwaway(ctx, sha: str, label: str, keep: bool = False):
    path = add(ctx, sha, label)
    try:
        yield path
    finally:
        if keep:
            ctx.out.say(f"kept {path}; remove it with: rm -r {path.parent} && git -C {ctx.main()} worktree prune")
        else:
            remove(ctx, path)


def install_check(ctx, sha: str, update_from: str | None) -> dict:
    """tools/ci/clean_install_check.py --update-from [ref] on ``sha``, in a throwaway checkout; its result row."""
    command = [sys.executable, "tools/ci/clean_install_check.py", "--update-from"]
    if update_from:
        command.append(update_from)
    with throwaway(ctx, sha, "install") as path:
        ctx.out.say(f"running {shlex.join(command[1:])} at {sha[:9]} in {path} ...")
        code, lines = checks._stream(ctx.at(path), command, checks.env_for("update"))
    tail = [line for line in lines if line.strip()][-1:] or [""]
    return {"ok": code == 0, "command": shlex.join(command[1:]), "sha": sha, "detail": tail[0]}


def fetch_pr(ctx, number: int) -> str:
    ref = f"refs/pull/{number}/head"
    code, _out, err = repo.run(["git", "fetch", "--quiet", ctx.remote, ref], ctx.top)
    if code:
        raise Failure(
            f"could not fetch pull request #{number} ({ctx.remote} {ref}): {err.strip()[:300]}",
            f"gh pr view {number} (is it the right number?), then python tools/retrodev try {number}",
        )
    sha = repo.head(ctx.top, "FETCH_HEAD")
    if not sha:
        raise Failure(f"the fetch of #{number} gave no commit", f"git fetch {ctx.remote} {ref}, then try again")
    return sha


REQUIRED = ("unit", "bundle", "lint", "page", "scan", "scaffold", "acceptance", "clean_install", "update")


def upgrade_baseline(ctx, number: int, sha: str) -> str:
    """Resolve and pin the latest stable release before we test the exact PR head."""
    main = f"refs/remotes/{ctx.remote}/main"
    refspec = f"refs/heads/main:{main}"
    code, _, err = repo.run(["git", "fetch", "--quiet", "--atomic", "--tags", ctx.remote, refspec], ctx.top)
    if code:
        raise Failure(
            f"#{number} upgrade is unverified: could not refresh {ctx.remote}/main and release tags: {err.strip()}",
            f"check the remote and retry python tools/retrodev try {number}",
        )
    # Same stable-tag rule as tools/ci/update_check.py. Pin the commit so the subsequent check cannot pick another.
    tags = repo.git(["tag", "--merged", main, "--list", "v*", "--sort=-v:refname"], ctx.top).split()
    latest = next((tag for tag in tags if "-" not in tag), "")
    baseline = repo.head(ctx.top, f"refs/tags/{latest}^{{commit}}") if latest else None
    if not baseline:
        raise Failure(
            f"#{number} upgrade is unverified: no stable release tag on {ctx.remote}/main",
            "check the published branch and its tags; do not count this trial as a full pass",
        )
    if not repo.is_ancestor(ctx.top, baseline, sha):
        raise Failure(
            f"#{number} upgrade is unverified: latest release {latest} is not an ancestor of PR head {sha[:9]}",
            f"sync and push the PR branch, then run python tools/retrodev try {number} again",
        )
    ctx.out.say(f"upgrade baseline: {latest} ({baseline[:9]})")
    ctx.out.set(update_from=baseline, update_tag=latest)
    return baseline


def run(ctx, number: int, keep: bool = False, setup: bool = True) -> int:
    sha = fetch_pr(ctx, number)
    ctx.out.say(f"pull request #{number} at {sha[:9]}")
    path = add(ctx, sha, f"try{number}")
    ctx.out.set(pr=number, head=sha, path=str(path), kept=keep)
    try:
        ctx.out.say(f"throwaway checkout {path}")
        inside = ctx.at(path)
        configured = inside.policy.get("checks", {}).get("inputs", {})
        missing = [name for name in REQUIRED if name not in configured]
        if missing:
            raise Failure(
                f"#{number} is unverified: required check configuration is missing: {', '.join(missing)}",
                "restore the required entries under [checks.inputs] in tools/retrodev/policy.toml and push the fix",
            )
        baseline = upgrade_baseline(ctx, number, sha)
        if setup:
            start.run_setup(ctx, path)
        try:
            checks.run(inside, list(REQUIRED), env={"RD_SCAFFOLD_FULL": "nested"}, update_from=baseline)
        except Failure as failure:
            raise Failure(
                f"#{number} at {sha[:9]} failed its full checks: {failure.message}",
                f"read the failures above; python tools/retrodev try {number} --keep keeps the checkout to look into",
                failure.code,
            )
        # check's shipping policy may let a check skip (acceptance without the toolchain) and still exit 0; try
        # promises the full checks, so a skipped row means they were not all run: unverified, never a pass.
        skipped = [row["name"] for row in ctx.out.data.get("checks", []) if row.get("state") == "skipped"]
        ctx.out.set(skipped=skipped)
        if skipped:
            raise Failure(
                f"#{number} at {sha[:9]} is unverified: {', '.join(skipped)} skipped, so the full checks did not pass",
                "set up what each skipped row names (python tools/retrodev doctor lists it; the real-engine run needs "
                f"python tools/ci/prepare_toolchain.py), then python tools/retrodev try {number}",
            )
    finally:
        if keep:
            ctx.out.say(f"kept {path}; remove it with: rm -r {path.parent} && git -C {ctx.main()} worktree prune")
        else:
            remove(ctx, path)
            ctx.out.say(f"removed {path}")
    ctx.out.say(f"#{number} at {sha[:9]} passed the full checks")
    return 0
