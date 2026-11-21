"""release next --owner-words "..." [--dry-run]: dev moves to the next version right after a release.

Run by `release run` once a stable release is tagged, and on its own (the first time, or after a run stopped).
When dev's plugin.yaml still says the newest stable release's version, it opens the next patch's version pull
request (chore/release-X.Y.Z, titled "Version X.Y.Z for the next release": the `version:` line only; started,
checked and shipped as release prepare does), approves it with the owner's release words as a release approval
scoped to that version (land_gates.release_scope_gate holds land to the version line), and lands it. So the next
`release run` finds dev on an untagged version and releases dev's green head as it is: no version pull request,
no CI run of its own.

Nothing to do when dev already says a newer, untagged version. An open pull request from that branch (an earlier
run stopped) is resumed, never opened twice. The pull request is kept in the released version's record ("next").
--dry-run fetches nothing and changes nothing: it says what it would do.
"""

from __future__ import annotations

from . import approve, checks, gates, github, land, land_merge, release, repo, reviews, ship, start, state
from .output import Failure, cmd


def title(version: str) -> str:
    return f"Version {version} for the next release"


def body(released: str, version: str, words: str) -> str:
    return f"""## Why
dev carries the next release's version from the moment {released} is released, so the next release needs no
version pull request: release run releases dev's green head as it is. The owner asked for releases: "{words}".

## What changed
The `version:` line of plugin.yaml, {released} to {version}; nothing else.

## How verified
python tools/retrodev check passed on this exact tree (release next ran it), on:
{release.systems()}

## Risk and rollback
The version line only: until {version} is released, an install of dev reports {version}. Rollback: revert this
pull request (the next release then opens its own version pull request).

## Not done
Releasing {version}: that waits for the owner's words (python tools/retrodev release run).

Made by an agent (Hermes, retrodev release next) for the owner.
"""


def command(words: str, dry_run: bool = False) -> str:
    return cmd(
        "python", "tools/retrodev", "release", "next", "--owner-words", words, *(["--dry-run"] if dry_run else [])
    )


def next_patch(version: str) -> str:
    major, minor, patch, _rc = release.parse(version)
    return f"{major}.{minor}.{patch + 1}"


def target(ctx) -> tuple[str | None, str, str | None]:
    """(newest stable release, dev's version, the version to move dev to or None when dev is ahead already)."""
    released = release.previous_stable(ctx)
    current = release.version_at(ctx, ctx.remote_base) or ""
    if not released:
        return None, current, None
    if not release.VERSION.match(current) or release.key(current) > release.key(released):
        return released, current, None
    return released, current, next_patch(released)


def remember(ctx, released: str, entry: dict) -> None:
    rec = state.load_release(ctx.top, released) or {"version": released}
    rec["next"] = {**(rec.get("next") or {}), **entry}
    state.save_release(ctx.top, rec)


def recorded(ctx, released: str, version: str) -> dict | None:
    """The pull request an earlier run opened and kept in the record, while GitHub says it is open or merged (its
    search by branch can lag a fresh pull request), else None."""
    kept = (state.load_release(ctx.top, released) or {}).get("next") or {}
    if kept.get("version") != version or not kept.get("pr"):
        return None
    found = github.pr_state(ctx, int(kept["pr"]))
    return {"number": int(kept["pr"]), "state": found} if found in ("OPEN", "MERGED") else None


def finish_landing(ctx, released: str) -> None:
    """A next-version pull request that merged while its landing stopped after the merge (the main checkout's pull,
    the worktree cleanup): land finishes those steps (never merging again) and the record says merged."""
    kept = (state.load_release(ctx.top, released) or {}).get("next") or {}
    if not kept.get("pr") or kept.get("merged") or kept.get("closed"):
        return
    number = int(kept["pr"])
    found = github.pr_state(ctx, number)
    if found is None:  # unknown is not "not merged": its landing may be left half done
        raise Failure(
            f"GitHub did not say whether #{number} (the next version's pull request) is merged",
            f"gh pr view {number}; then {command(kept.get('words') or '<the owner words>')} again (it resumes)",
        )
    if found != "MERGED":
        return
    land.run(ctx, number)
    landed(ctx, released, number)


def landed(ctx, released: str, number: int) -> None:
    """The record says merged only once land finished every step after the merge (the main checkout's pull, the
    cleanup); otherwise it says what is left, and the next run (finish_landing) finishes it."""
    left = land_merge.unfinished(reviews.load(ctx, number))
    if left:
        raise Failure(
            f"#{number} merged, but its landing did not finish (the main checkout's pull or the worktree cleanup)",
            f"read land's output above; python tools/retrodev land {number} finishes it",
        )
    remember(ctx, released, {"merged": state.now()})


def open_it(ctx, released: str, version: str, words: str) -> int:
    """The version pull request, made the way release prepare makes one (a worktree left over is reused)."""
    branch = f"chore/release-{version}"
    body_file = state.release_path(ctx.top, version).with_name(f"next-{version}.md")
    state.write_atomic(body_file, body(released, version, words))
    _kind, topic = gates.parse_branch(branch, ctx.policy["branches"]["kinds"])
    path = start.worktree_path(ctx, topic)
    if not path.exists():
        start.run(ctx, branch, no_plan=True)
    tree = ctx.at(path)
    release.release_only(tree, path, branch)
    if release.version_at(tree, "HEAD") != version:
        release.set_version(path, version)
        repo.git(["add", "--", "plugin.yaml"], path)
        repo.git(["commit", "--quiet", "-m", title(version)], path)  # only the staged manifest
        release.release_only(tree, path, branch)
    checks.run(tree, release.version_pr_checks(tree))
    ship.run(tree, title(version), str(body_file))
    number = (state.load_branch(ctx.top, branch).get("pr") or {}).get("number")
    if not number:
        raise Failure(f"ship recorded no pull request for {branch}", f"gh pr list --head {branch}")
    return int(number)


def run(ctx, words: str | None, dry_run: bool = False) -> int:
    try:
        words = release.words_gate(words)
    except Failure as failure:
        raise Failure(failure.message, f"ask the owner; then {command('<their exact words>', dry_run)}", failure.code)
    if ctx.top.resolve() != ctx.main().resolve():
        raise Failure(
            f"release next runs from the main checkout ({ctx.main()}): land removes the worktree",
            f"{cmd('cd', ctx.main())} && {command(words, dry_run)}",
        )
    if not dry_run:
        repo.git(["fetch", "--quiet", "--tags", ctx.remote], ctx.top)
    released, current, version = target(ctx)
    ctx.out.set(released=released, dev_version=current, next=version, dry_run=dry_run)
    if released and not dry_run:
        finish_landing(ctx, released)
    if not released:
        ctx.out.say("no stable release is tagged yet: nothing to move on from")
        return 0
    if not version:
        ctx.out.say(f"{ctx.remote_base} already says {current} (newer than {released}): nothing to do")
        return 0
    branch = f"chore/release-{version}"
    again = command(words, dry_run)
    found = recorded(ctx, released, version) or github.branch_pr(ctx, branch)
    if found and found.get("state") == "MERGED":
        ctx.out.say(f"#{found['number']} set {version} on {ctx.remote_base} already (fetch to see it): nothing to do")
        return 0
    if dry_run:
        what = f"land #{found['number']}" if found else f"open {branch} (version {current} to {version}), approve, land"
        ctx.out.say(f"would: {what}")
        ctx.out.say("dry run: nothing was opened, approved or merged")
        return 0
    try:
        number = int(found["number"]) if found else open_it(ctx, released, version, words)
    except Failure as failure:
        raise Failure(failure.message, f"{failure.fix}; then {again} (it resumes)", failure.code, failure.data)
    remember(ctx, released, {"version": version, "branch": branch, "pr": number, "at": state.now(), "words": words})
    ctx.out.set(pr=number)
    from . import release_run  # its checks of a version pull request's head (release_run imports this module)

    info = reviews.pr_view(ctx, number)
    sha = release_run.checked_head(ctx, info, {"branch": branch, "version": version}, again)
    given = state.load_branch(ctx.top, branch).get("approval") or {}
    if given.get("pr") != number or given.get("head") != sha:
        scope = {"scope": "release", "version": version, "checked": sha}
        approve.approve(ctx, number, words, scope=scope)
    ctx.out.say(f"running: {cmd('python', 'tools/retrodev', 'land', number)}")
    try:
        land.run(ctx, number)
    except Failure as failure:
        raise Failure(failure.message, f"{failure.fix}; then {again} (it resumes)", failure.code, failure.data)
    landed(ctx, released, number)
    ctx.out.say(f"{ctx.remote_base} now says {version}: the next release needs no version pull request")
    return 0
