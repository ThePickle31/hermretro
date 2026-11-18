"""release publish <version> [--dry-run]: main fast-forwards to the release commit, the tag, the draft release.

Gates, all reported at once: the owner's words are recorded for this version (release prepare); its version pull
request is merged (the merge commit is the release commit; without one, the base branch's head); that commit is
on the base branch, its plugin.yaml says the version, and the required CI job ("All checks pass") is green on that
exact commit (gh api .../commits/<sha>/check-runs); for a stable release main can fast-forward to it. Then
`tools/ci/clean_install_check.py --update-from` runs on that commit in a throwaway checkout (its pass is kept for
that commit). Then, each step skipped when it is done already (so a stopped publish resumes):

    git push <remote> <sha>:<main>         a fast-forward only (never forced); HERMES_RELEASE=1 for this push only,
                                           which the local guard hooks require
    git tag -a v<version> <sha>            annotated
    git push <remote> refs/tags/v<version>
    gh release create v<version> --verify-tag --generate-notes --notes-start-tag v<previous stable> --draft

A release candidate (X.Y.Z-rc.M) is tagged on the base-branch commit with --prerelease; main does not move.
--dry-run fetches nothing, runs nothing and changes nothing: it prints the gates and every command.
"""

from __future__ import annotations

import json
import os

from . import gates, github, release, repo, state, trial
from .gates import Gate
from .output import OWNER, WAITING, Failure

MAIN = "main"


def commit_gate(ctx, rec: dict | None, version: str) -> tuple[str | None, Gate]:
    """The release commit: the version pull request's merge commit, else the base branch's head."""
    name = "release pull request merged"
    if not rec:
        return None, Gate(name, False, f"no release {version} is recorded", "release prepare first", OWNER)
    if not rec.get("pr"):
        sha = repo.head(ctx.top, ctx.remote_base)
        return sha, gates.passed(name, f"no version pull request was needed; {ctx.remote_base} at {(sha or '')[:9]}")
    number = rec["pr"]
    code, out, err = github.gh(ctx, ["pr", "view", str(number), "--json", "state,mergeCommit"], check=False)
    info = json.loads(out) if code == 0 and out.strip() else {}
    sha = (info.get("mergeCommit") or {}).get("oid")
    if info.get("state") != "MERGED" or not sha:
        why = info.get("state") or (err or out).strip()[:200] or "unknown"
        return None, Gate(
            name,
            False,
            f"the version pull request #{number} is not merged ({why})",
            f"python tools/retrodev land {number} (after the owner's approve), then publish again",
            WAITING,
        )
    return sha, gates.passed(name, f"#{number} merged as {sha[:9]}")


def ci_gate(ctx, sha: str) -> Gate:
    """The required jobs' newest check runs on this exact commit all succeeded."""
    name = f"CI green on {sha[:9]}"
    required = ctx.policy["land"]["required_jobs"]
    path = f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs?per_page=100"
    code, out, err = github.gh(ctx, ["api", path], check=False)
    try:
        runs = json.loads(out).get("check_runs", []) if code == 0 else None
    except (json.JSONDecodeError, AttributeError):
        runs = None
    if runs is None:
        return Gate(name, False, f"gh api {path} failed: {(err or out).strip()[:200]}", "python tools/retrodev doctor")
    states = []
    for job in required:
        mine = sorted((r for r in runs if r.get("name") == job), key=lambda r: r.get("started_at") or "")
        last = mine[-1] if mine else {}
        states.append((job, last.get("status"), last.get("conclusion")))
    pending = [job for job, status, _c in states if status != "completed"]
    failed = [f"{job}: {c}" for job, status, c in states if status == "completed" and c != "success"]
    if failed:
        return Gate(name, False, "; ".join(failed), f"gh run list -c {sha} (fix it on {ctx.base} with a pull request)")
    if pending:
        return Gate(
            name,
            False,
            f"not finished yet: {', '.join(pending)}",
            f"wait for the push run (gh run list -c {sha}), then publish again",
            WAITING,
        )
    return gates.passed(name, ", ".join(required))


def tag_state(ctx, tag: str, sha: str) -> tuple[str, Gate]:
    """'new', 'local' (made here, not pushed), 'pushed' (on the remote at sha); a tag elsewhere is refused."""
    local = repo.head(ctx.top, f"refs/tags/{tag}")
    _code, out, _err = repo.run(["git", "ls-remote", "--tags", ctx.remote, f"refs/tags/{tag}*"], ctx.top)
    remote = {line.split("\t")[1]: line.split("\t")[0] for line in out.splitlines() if "\t" in line}
    pushed = remote.get(f"refs/tags/{tag}^{{}}") or remote.get(f"refs/tags/{tag}")
    for where, at in (("here", local), (ctx.remote, pushed)):
        if at and at != sha:
            return "", Gate(
                f"tag {tag}", False, f"{tag} exists {where} at {at[:9]}, not {sha[:9]}", "ask the owner", OWNER
            )
    found = "pushed" if pushed else ("local" if local else "new")
    return found, gates.passed(f"tag {tag}", {"new": "free", "local": "made here", "pushed": "pushed"}[found])


def main_gate(ctx, sha: str, rc: bool) -> Gate:
    if rc:
        return gates.passed("main untouched", "a release candidate never moves main")
    current = repo.head(ctx.top, f"{ctx.remote}/{MAIN}")
    if not current:
        return Gate("main fast-forwards", False, f"{ctx.remote}/{MAIN} is unknown here", f"git fetch {ctx.remote}")
    if not repo.is_ancestor(ctx.top, current, sha):
        return Gate(
            "main fast-forwards",
            False,
            f"{ctx.remote}/{MAIN} ({current[:9]}) is not an ancestor of {sha[:9]}: main would need a merge or a "
            "rewrite, and it only ever fast-forwards",
            "stop and tell the owner (git log --oneline origin/main ^origin/dev shows what main has)",
            OWNER,
        )
    return gates.passed("main fast-forwards", f"{current[:9]} to {sha[:9]}")


def steps(ctx, version: str, sha: str, rc: bool, tag_now: str) -> list[dict]:
    tag = f"v{version}"
    previous = release.previous_stable(ctx, version)
    create = ["gh", "release", "create", tag, "--verify-tag", "--generate-notes"]
    create += ["--notes-start-tag", f"v{previous}"] if previous else []
    create += ["--draft"] + (["--prerelease"] if rc else [])
    found = []
    if not rc:
        moved = repo.head(ctx.top, f"{ctx.remote}/{MAIN}") == sha
        found.append({"run": ["git", "push", ctx.remote, f"{sha}:main"], "env": {"HERMES_RELEASE": "1"}, "done": moved})
    found.append({"run": ["git", "tag", "-a", tag, sha, "-m", f"Release {version}"], "done": tag_now != "new"})
    found.append({"run": ["git", "push", ctx.remote, f"refs/tags/{tag}"], "done": tag_now == "pushed"})
    view = github.gh(ctx, ["release", "view", tag, "--json", "url"], check=False)
    found.append({"run": create, "done": view[0] == 0})
    return found


def shown(step: dict) -> str:
    words = [f"'{w}'" if (" " in w or not w) else w for w in step["run"]]
    env = " ".join(f"{k}={v}" for k, v in step.get("env", {}).items())
    return (env + " " if env else "") + " ".join(words)


def install_gate(ctx, rec: dict, sha: str, dry_run: bool) -> Gate:
    name = "clean install and update check"
    cached = (rec.get("install") or {}).get(sha)
    if cached and cached.get("ok"):
        return gates.passed(name, f"passed at {cached.get('at')} (on this commit)")
    if dry_run:
        return gates.passed(name, "would run tools/ci/clean_install_check.py --update-from on this commit")
    result = trial.install_check(ctx, sha, None)
    rec.setdefault("install", {})[sha] = {"ok": result["ok"], "at": state.now(), "detail": result["detail"]}
    state.save_release(ctx.top, rec)
    if not result["ok"]:
        return Gate(name, False, result["detail"], "read the update check's FIX above; fix it on dev, then again")
    return gates.passed(name, result["detail"])


def run(ctx, version: str, dry_run: bool = False) -> int:
    rc = release.parse(version)[3] is not None
    rec = state.load_release(ctx.top, version)
    if not dry_run:
        repo.git(["fetch", "--quiet", "--tags", ctx.remote], ctx.top)
    found = []
    if not (rec and rec.get("words")):
        found.append(
            Gate(
                "owner asked for this release",
                False,
                f"no owner's words are recorded for {version} (releases happen only when the owner says so)",
                f'when the owner says \'make a release\': python tools/retrodev release prepare{" --rc" if rc else ""} '
                '--owner-words "<their exact words>"',
                OWNER,
            )
        )
    else:
        found.append(gates.passed("owner asked for this release", f'{rec["at"]}: "{rec["words"]}"'))
    sha, gate = commit_gate(ctx, rec, version)
    found.append(gate)
    tag_now = "new"
    if sha:
        on_base = repo.is_ancestor(ctx.top, sha, ctx.remote_base)
        found.append(
            gates.passed(f"on {ctx.remote_base}", sha[:9])
            if on_base
            else Gate(
                f"on {ctx.remote_base}", False, f"{sha[:9]} is not on {ctx.remote_base}", f"git fetch {ctx.remote}"
            )
        )
        has = release.version_at(ctx, sha)
        want = release.stable(version)
        found.append(
            gates.passed("plugin.yaml says the version", want)
            if has == want
            else Gate("plugin.yaml says the version", False, f"plugin.yaml at {sha[:9]} says {has}", "release prepare")
        )
        found.append(ci_gate(ctx, sha))
        found.append(main_gate(ctx, sha, rc))
        tag_now, gate = tag_state(ctx, f"v{version}", sha)
        found.append(gate)
    gates.enforce(ctx, found, f"release publish {version}")
    assert sha and rec
    gates.enforce(ctx, found + [install_gate(ctx, rec, sha, dry_run)], f"release publish {version}")
    todo = steps(ctx, version, sha, rc, tag_now)
    ctx.out.set(version=version, sha=sha, rc=rc, dry_run=dry_run, commands=[shown(s) for s in todo])
    if dry_run:
        ctx.out.say("would run:")
        for step in todo:
            ctx.out.say(("  (done) " if step["done"] else "  ") + shown(step))
        ctx.out.say("dry run: nothing was pushed, tagged or created")
        return 0
    url = ""
    for step in todo:
        if step["done"]:
            ctx.out.say(f"done already: {shown(step)}")
            continue
        ctx.out.say(f"running: {shown(step)}")
        if step["run"][0] == "gh":
            _code, out, _err = github.gh(ctx, step["run"][1:])
            url = out.strip().splitlines()[-1] if out.strip() else ""
            continue
        env = dict(os.environ, **step.get("env", {}))
        code, out, err = repo.run(step["run"], ctx.top, timeout=300, env=env)
        if code:
            raise Failure(
                f"{shown(step)} failed: {(err or out).strip()[:400]}",
                "read git's message; nothing later ran. Fix it, then python tools/retrodev release publish "
                f"{version} again (it skips the steps that are done)",
            )
    if not url:
        url = github.gh(ctx, ["release", "view", f"v{version}", "--json", "url", "--jq", ".url"])[1].strip()
    rec.update(published_draft={"at": state.now(), "sha": sha, "url": url})
    state.save_release(ctx.top, rec)
    ctx.out.set(url=url)
    ctx.out.say(f"draft release: {url}")
    ctx.out.say(f"next: read the draft, then python tools/retrodev release verify {version} (--publish publishes it)")
    return 0
