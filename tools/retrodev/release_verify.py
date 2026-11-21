"""release verify <version> [--publish]: read the draft release and prove the user's path before publishing.

Checks, all reported: the release exists (gh release view --json) and its notes are not empty; the tag is on the
remote; for a stable release it points at main's head and plugin.yaml there says the version; for a candidate
it is a prerelease on a base-branch commit. Pin the preceding published stable commit and prove it updates to the
candidate. A matching local pass counts; CI evidence is rechecked and otherwise the local upgrade runs. With --publish and
everything ok, it says that a published release is immutable and runs `gh release edit v<version> --draft=false`.
--publish also needs the authorization: the owner's words recorded for this version (release prepare), the tag at
the very commit `release publish` approved after all its gates passed (kept in the release record), and the
required CI job green on that commit. So a draft made by hand, or a tag moved since, is never published.
"""

from __future__ import annotations

import json

from . import gates, github, release, release_ci, release_publish, repo, state
from .gates import Gate
from .output import OWNER, Failure

FIELDS = "tagName,isDraft,isPrerelease,body,url,name"


def remote_tag(ctx, tag: str) -> str | None:
    """The commit the remote's tag points at (peeled), or None."""
    return repo.peeled_remote_tag(ctx.top, ctx.remote, tag)


def remote_head(ctx, branch: str) -> str | None:
    _code, out, _err = repo.run(["git", "ls-remote", "--heads", ctx.remote, f"refs/heads/{branch}"], ctx.top)
    return out.split("\t")[0].strip() or None


def authorized(ctx, version: str, sha: str | None) -> list[Gate]:
    """--publish only: the owner's words, publish's approval of exactly this commit, CI green on it."""
    rec = state.load_release(ctx.top, version) or {}
    prepare = f'python tools/retrodev release prepare{" --rc" if "-rc." in version else ""} --owner-words "..."'
    found = [
        gates.passed("owner asked for this release", f'{rec.get("at")}: "{rec["words"]}"')
        if rec.get("words")
        else Gate(
            "owner asked for this release",
            False,
            f"no owner's words are recorded for {version}: a release is published only when the owner asks",
            f"ask the owner; when they say it: {prepare}, then release publish {version}",
            OWNER,
        )
    ]
    approved = (rec.get("approved") or {}).get("sha")
    name = "release publish approved this commit"
    if not sha or approved != sha:
        why = f"publish approved {approved[:9]}" if approved else "release publish never passed its gates"
        found.append(
            Gate(name, False, f"{why}; the tag is at {(sha or 'nothing')[:9]}", f"release publish {version}", OWNER)
        )
        return found
    found.append(gates.passed(name, f"{sha[:9]} at {rec['approved'].get('at')}"))
    found.append(release_publish.ci_gate(ctx, sha))
    return found


def run(ctx, version: str, publish: bool = False) -> int:
    rc = release.parse(version)[3] is not None
    tag = f"v{version}"
    found: list[Gate] = []
    code, out, err = github.gh(ctx, ["release", "view", tag, "--json", FIELDS], check=False)
    info = json.loads(out) if code == 0 and out.strip() else None
    if info is None:
        raise Failure(
            f"there is no release {tag} on GitHub ({(err or out).strip()[:200]})",
            f"python tools/retrodev release publish {version} (it makes the draft)",
        )
    ctx.out.set(release=info)
    notes = (info.get("body") or "").strip()
    found.append(
        gates.passed("notes", f"{len(notes.splitlines())} line(s)")
        if notes
        else Gate("notes", False, "the release notes are empty", f"gh release edit {tag} --notes-file <file>")
    )
    repo.git(["fetch", "--quiet", "--tags", ctx.remote], ctx.top)
    sha = remote_tag(ctx, tag)
    found.append(
        gates.passed("tag on the remote", (sha or "")[:9])
        if sha
        else Gate("tag on the remote", False, f"{tag} is not on {ctx.remote}", f"release publish {version}")
    )
    if sha and not rc:
        main = remote_head(ctx, "main")
        found.append(
            gates.passed("tag is main's head", sha[:9])
            if main == sha
            else Gate(
                "tag is main's head",
                False,
                f"main is at {(main or 'nothing')[:9]}, the tag at {sha[:9]}",
                f"python tools/retrodev release publish {version} (it fast-forwards main first)",
            )
        )
    elif sha:
        found.append(
            gates.passed("a prerelease on the base branch", sha[:9])
            if info.get("isPrerelease") and repo.is_ancestor(ctx.top, sha, ctx.remote_base)
            else Gate(
                "a prerelease on the base branch",
                False,
                f"prerelease={info.get('isPrerelease')}, {sha[:9]} on {ctx.remote_base}: "
                f"{repo.is_ancestor(ctx.top, sha, ctx.remote_base)}",
                f"gh release edit {tag} --prerelease (a candidate never goes on main)",
            )
        )
    if sha:
        has = release.version_at(ctx, sha)
        found.append(
            gates.passed("plugin.yaml says the version", has or "")
            if has == release.stable(version)
            else Gate("plugin.yaml says the version", False, f"plugin.yaml at the tag says {has}", "ask the owner")
        )
        published = release_ci.prior_release(ctx, sha, version)
        rec = state.load_release(ctx.top, version) or {"version": version}
        result = release_publish.install_check(ctx, rec, sha, published)
        detail = f"from {published.tag}: {result['detail']}"
        found.append(
            gates.passed("update from the last release", detail)
            if result["ok"]
            else Gate("update from the last release", False, detail, "read the update check's FIX above")
        )
    if publish and info.get("isDraft"):
        found += authorized(ctx, version, sha)
    gates.enforce(ctx, found, f"release verify {version}")
    ctx.out.say(f"{tag} checks out: {info.get('url')}")
    if not info.get("isDraft"):
        ctx.out.say("it is published already (published releases are immutable)")
        ctx.out.set(published=True)
        rec = state.load_release(ctx.top, version) or {}
        approved = (rec.get("approved") or {}).get("sha")
        if not rec.get("published") and approved and approved == sha:  # published, but the record was not saved
            rec["published"] = {"at": state.now(), "sha": sha, "url": info.get("url"), "reconciled": True}
            state.save_release(ctx.top, rec)
            ctx.out.say("recorded it as published (the earlier run stopped before saving that)")
        return 0
    if not publish:
        ctx.out.say(f"next: read the draft ({info.get('url')}), then release verify {version} --publish")
        ctx.out.set(published=False)
        return 0
    ctx.out.say("publishing: a published release is immutable (its tag and files can never change)")
    github.gh(ctx, ["release", "edit", tag, "--draft=false"])
    rec = state.load_release(ctx.top, version) or {"version": version}
    rec["published"] = {"at": state.now(), "sha": sha, "url": info.get("url")}
    state.save_release(ctx.top, rec)
    ctx.out.set(published=True)
    ctx.out.say(f"published {tag}: {info.get('url')}")
    return 0
