"""release verify <version> [--publish]: read the draft release and prove the user's path before publishing.

Checks, all reported: the release exists (gh release view --json) and its notes are not empty; the tag is on the
remote; for a stable release it points at main's head and plugin.yaml there says the version; for a candidate
it is a prerelease on a base-branch commit. Then `tools/ci/clean_install_check.py --update-from v<previous stable>`
runs on the tagged commit in a throwaway checkout: users of the last release update to it (a pass release publish
kept for that commit and starting release counts, so it runs once per release). With --publish and
everything ok, it says that a published release is immutable and runs `gh release edit v<version> --draft=false`.
--publish also needs the authorization: the owner's words recorded for this version (release prepare), the tag at
the very commit `release publish` approved after all its gates passed (kept in the release record), and the
required CI job green on that commit. So a draft made by hand, or a tag moved since, is never published.
"""

from __future__ import annotations

import json

from . import gates, github, release, release_publish, repo, state
from .gates import Gate
from .output import OWNER, Failure

FIELDS = "tagName,isDraft,isPrerelease,body,url,name"


def release_view(ctx, version: str) -> dict:
    tag = f"v{version}"
    code, out, err = github.gh(ctx, ["release", "view", tag, "--json", FIELDS], check=False)
    try:
        info = json.loads(out) if code == 0 else None
    except ValueError:
        info = None
    if not isinstance(info, dict) or info.get("tagName") != tag or type(info.get("isDraft")) is not bool:
        raise Failure(
            f"could not read {tag} from GitHub ({(err or out).strip()[:200]})",
            f"python tools/retrodev release verify {version}",
        )
    return info


def require_published(version: str, info: dict) -> None:
    if (
        info.get("isDraft") is not False
        or info.get("isPrerelease") is not (release.parse(version)[3] is not None)
        or not isinstance(info.get("url"), str)
        or not info["url"].strip()
    ):
        raise Failure(
            f"could not confirm v{version} is published", f"python tools/retrodev release verify {version} --publish"
        )


def reconcile(ctx, version: str, rec: dict, info: dict | None = None) -> dict | None:
    """Recover the result of publication, not permission to publish a draft."""
    approved = (rec.get("approved") or {}).get("sha")
    tag = f"v{version}"
    if not approved or not rec.get("words"):
        if rec.get("published"):
            raise Failure(f"{tag} has no recorded publication approval", "inspect the release record", OWNER)
        return None
    if info is None:
        info = release_view(ctx, version)
    if info["isDraft"] and not rec.get("published"):
        return None
    require_published(version, info)
    if remote_tag(ctx, tag) != approved:
        raise Failure(f"{tag} does not point at the approved commit", "inspect the remote tag before continuing", OWNER)
    if not rec.get("published"):
        rec["published"] = {"at": state.now(), "sha": approved, "url": info["url"], "reconciled": True}
        state.save_release(ctx.top, rec)
    return info


def remote_tag(ctx, tag: str) -> str | None:
    """The commit the remote's tag points at (peeled), or None."""
    _code, out, _err = repo.run(["git", "ls-remote", "--tags", ctx.remote, f"refs/tags/{tag}*"], ctx.top)
    refs = {line.split("\t")[1]: line.split("\t")[0] for line in out.splitlines() if "\t" in line}
    return refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")


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
    info = release_view(ctx, version)
    ctx.out.set(release=info)
    rec = state.load_release(ctx.top, version) or {"version": version}
    if reconcile(ctx, version, rec, info):
        ctx.out.say(f"{tag} is published already (immutable): {info['url']}")
        ctx.out.set(published=True, url=info["url"])
        return 0
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
        start = release_publish.update_from(ctx, version)
        kept = release_publish.kept_install(rec, sha, start)
        # release publish ran this very check on this commit minutes ago: its pass counts, so it runs once
        result = (
            {"ok": True, "detail": f"{kept['detail']} (release publish's run at {kept.get('at')})"}
            if kept
            else release_publish.install_check(ctx, rec, sha, start)
        )
        detail = f"from {start}: {result['detail']}" if start else result["detail"]
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
        ctx.out.set(published=True, url=info.get("url"))
        return 0
    if not publish:
        ctx.out.say(f"next: read the draft ({info.get('url')}), then release verify {version} --publish")
        ctx.out.set(published=False)
        return 0
    ctx.out.say("publishing: a published release is immutable (its tag and files can never change)")
    code, out, err = github.gh(ctx, ["release", "edit", tag, "--draft=false"], check=False)
    try:
        info = release_view(ctx, version)
        require_published(version, info)
    except Failure:
        if code:
            raise github.failed(["release", "edit", tag, "--draft=false"], err or out) from None
        raise
    if remote_tag(ctx, tag) != sha:
        raise Failure(f"{tag} changed during publication", "inspect the remote tag before continuing", OWNER)
    rec = state.load_release(ctx.top, version) or {"version": version}
    rec["published"] = {"at": state.now(), "sha": sha, "url": info.get("url")}
    if code:
        rec["published"]["reconciled"] = True  # the write returned an error but GitHub applied it
    state.save_release(ctx.top, rec)
    ctx.out.set(release=info, published=True, url=info["url"])
    ctx.out.say(f"published {tag}: {info.get('url')}")
    return 0
