"""What release run checks before and around its steps: which release it works on, whether there is anything to
release, a next-version pull request in the way, and one rerun of a failed push run (release_run.py)."""

from __future__ import annotations

import json

from . import checks_triggers, github, release, repo, state

FAILED_RUN = {"failure", "cancelled", "timed_out", "startup_failure"}


def records(ctx) -> list[dict]:
    folder = state.root(ctx.top) / "releases"
    found = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        if release.VERSION.match(path.stem):
            found.append(state.load_release(ctx.top, path.stem) or {})
    return [rec for rec in found if rec.get("version")]


def choose(ctx, rc: bool, named: str | None) -> str:
    """The release this run works on: an unpublished one an earlier run started (or the one named, also a published
    one this command started: its last step, release next, may be left), else the next."""
    if named and not rc:
        kept = state.load_release(ctx.top, release.stable(named)) or {}
        if kept.get("published") and kept.get("run"):
            return kept["version"]
    started = [
        rec
        for rec in records(ctx)
        if not rec.get("published")
        and bool(rec.get("rc")) == rc
        and (release.stable(rec["version"]) == named if named else bool(rec.get("run")))
    ]
    if started:
        return max(started, key=lambda rec: release.key(rec["version"]))["version"]
    return release.target(ctx, rc, named)[0]


def news(ctx) -> str | None:
    """None when the base branch has nothing since the newest stable tag besides plugin.yaml's version line (or no
    tag exists); else what changed."""
    previous = release.previous_stable(ctx)
    if not previous:
        return "no stable release yet"
    since = repo.head(ctx.top, f"refs/tags/v{previous}")
    if not since:
        return f"v{previous} is not here"
    if repo.ok(["diff", "--quiet", since, ctx.remote_base, "--"], ctx.top):
        return None  # the very same files
    return checks_triggers.beyond_version(ctx.top, since, ctx.remote_base)


def stale_next(ctx, version: str, dry_run: bool) -> None:
    """A next-version pull request release next opened for another version than this release's (the owner named a
    different one) would set dev back once this lands: closed, with a comment saying why."""
    for rec in records(ctx):
        nxt = rec.get("next") or {}
        if not nxt.get("pr") or nxt.get("merged") or nxt.get("closed") or nxt.get("version") == release.stable(version):
            continue
        number = int(nxt["pr"])
        if github.pr_state(ctx, number) != "OPEN":
            continue
        why = f"release {version} sets its own version; this pull request for {nxt.get('version')} is not needed"
        if dry_run:
            ctx.out.say(f"would close #{number}: {why}")
            continue
        github.gh(ctx, ["pr", "close", str(number), "--comment", why + " (release run)", "--delete-branch"])
        rec["next"] = {**nxt, "closed": state.now()}
        state.save_release(ctx.top, rec)
        ctx.out.say(f"closed #{number}: {why}")


def rerun(ctx, rec: dict, sha: str, why: str) -> bool:
    """Once per release commit: rerun the failed jobs of its failed push runs (a flaky runner). False when it
    was rerun already or no failed run is found."""
    if sha in (rec.get("ci_rerun") or {}):
        return False
    code, out, _err = github.gh(
        ctx, ["run", "list", "--commit", sha, "--json", "databaseId,conclusion,event"], check=False
    )
    try:
        found = json.loads(out) if code == 0 else []
    except json.JSONDecodeError:
        found = []
    failed = [r["databaseId"] for r in found if r.get("event") == "push" and r.get("conclusion") in FAILED_RUN]
    if not failed:
        return False
    rec.setdefault("ci_rerun", {})[sha] = {"at": state.now(), "runs": failed, "why": why}
    state.save_release(ctx.top, rec)  # before asking: a stopped run never reruns twice
    for run_id in failed:
        github.gh(ctx, ["run", "rerun", str(run_id), "--failed"])
    ctx.out.say(f"CI failed on {sha[:9]} ({why}): reran the failed jobs once (a flaky runner?); waiting again")
    return True
