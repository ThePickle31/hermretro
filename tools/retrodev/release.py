"""Releases, only when the owner says 'make a release': prepare the version pull request, then publish, verify.

    release prepare [--rc] [--version X.Y.Z] --owner-words "..."   the chore/release-X.Y.Z pull request
    release publish <version> [--dry-run]                            (release_publish.py) main, tag, draft
    release verify <version> [--publish]                             (release_verify.py) read it, then publish

prepare refuses (exit 3) without the owner's exact words. The version lives only in plugin.yaml; the next one is
the patch after the version on the base branch (another only when the owner names it: --version). It starts a
chore/release-X.Y.Z worktree (start, no plan), changes only the `version:` line, commits, runs check and ships
the pull request 'Release X.Y.Z'; the agent then lands it like any pull request. When the base branch already
carries an untagged version (an earlier release candidate bumped it), no pull request is needed, and the record
says so (no_pr): the usual case, since release next moves dev to the next version right after each release. An open
pull request from chore/release-X.Y.Z (release next's) is recorded instead of opening another. A prepare stopped after recording its branch (check or ship failed) prints the same prepare command
to finish it: run again, it reuses the worktree, checks, ships and records the pull request, or, when the pull
request exists already (even merged), records it (gh pr list --head chore/release-X.Y.Z --state all).
--rc names the next candidate X.Y.Z-rc.M; publishing it tags a base-branch commit and leaves main alone.
"""

from __future__ import annotations

import platform
import re
from pathlib import Path

from . import checks, gates, github, repo, ship, start, state
from .output import OWNER, Failure, quote

VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$")
VERSION_LINE = re.compile(r"^version:[ \t]*[\"']?([^\"'\s#]+)[\"']?.*$", re.MULTILINE)


def parse(version: str) -> tuple[int, int, int, int | None]:
    match = VERSION.match(version or "")
    if not match:
        raise Failure(f"'{version}' is not a release version", "use X.Y.Z (a stable release) or X.Y.Z-rc.M")
    major, minor, patch, rc = match.groups()
    return int(major), int(minor), int(patch), int(rc) if rc else None


def stable(version: str) -> str:
    return version.split("-rc.")[0]


def key(version: str) -> tuple:
    major, minor, patch, rc = parse(version)
    return major, minor, patch, rc is None, rc or 0  # a candidate sorts before its release


def manifest_version(text: str | None) -> str | None:
    match = VERSION_LINE.search(text or "")
    return match.group(1) if match else None


def version_at(ctx, ref: str) -> str | None:
    """The version plugin.yaml holds at a commit or ref."""
    code, out, _err = repo.run(["git", "show", f"{ref}:plugin.yaml"], ctx.top)
    return manifest_version(out) if code == 0 else None


def tags(ctx) -> list[str]:
    """Release versions tagged here (v<version>), oldest first."""
    found = []
    for name in repo.git(["tag", "-l", "v*"], ctx.top).split():
        if VERSION.match(name[1:]):
            found.append(name[1:])
    return sorted(found, key=key)


def previous_stable(ctx, version: str | None = None) -> str | None:
    """The newest stable release older than ``version`` (any, without one)."""
    older = [v for v in tags(ctx) if "-rc." not in v and (version is None or key(v) < key(stable(version)))]
    return older[-1] if older else None


def words_gate(words: str | None) -> str:
    words = (words or "").strip()
    if not words:
        raise Failure(
            "a release happens only when the owner asks for it ('make a release'); no words were given",
            'ask the owner; when they say it: python tools/retrodev release prepare --owner-words "<their exact '
            'words>"',
            OWNER,
        )
    if "release" not in words.lower():
        raise Failure(
            f'"{words}" does not ask for a release (the owner\'s words name it, e.g. "make a release")',
            'pass the owner\'s exact words: --owner-words "<what they said>"; without them, no release',
            OWNER,
        )
    return words


def target(ctx, rc: bool, named: str | None) -> tuple[str, str, bool]:
    """(release version, version on the base branch, whether a version pull request is needed)."""
    current = version_at(ctx, ctx.remote_base)
    if not current or not VERSION.match(current):
        raise Failure(f"plugin.yaml on {ctx.remote_base} has no X.Y.Z version line", "git show origin/dev:plugin.yaml")
    released = set(tags(ctx))
    if named:
        if parse(named)[3] is not None:
            raise Failure("--version takes X.Y.Z; --rc adds the -rc.M", "release prepare --rc --version X.Y.Z ...")
        if key(named) < key(current) or named in released:
            raise Failure(f"{named} is not newer than {current} or is released", "name a newer X.Y.Z (or none)")
        version = named
    elif current in released:
        major, minor, patch, _rc = parse(current)
        version = f"{major}.{minor}.{patch + 1}"  # patch only, unless the owner names another
    else:
        version = current  # moved on already (release next, or a candidate's pull request): release it as is
    needs_pr = version != current
    if rc:
        numbers = [parse(v)[3] or 0 for v in released if stable(v) == version and "-rc." in v]
        version = f"{version}-rc.{max(numbers, default=0) + 1}"
    return version, current, needs_pr


def systems() -> str:
    """The How verified boxes: the system release prepare (and so its checks) ran on is ticked, the other is not."""
    mac = platform.system() == "Darwin"
    linux = f"- [{' ' if mac else 'x'}] Linux" + ("" if mac else f": {platform.machine()}")
    darwin = f"- [{'x' if mac else ' '}] macOS (Apple Silicon / Intel)" + (f": {platform.machine()}" if mac else "")
    return f"{linux}\n{darwin}"


def body(version: str, current: str, words: str, rc: bool) -> str:
    kind = "release candidate" if rc else "release"
    return f"""## Why
The owner asked for a {kind}: "{words}".

## What changed
The `version:` line of plugin.yaml, {current} to {stable(version)}; nothing else.

## How verified
python tools/retrodev check passed on this exact tree (release prepare ran it), on:
{systems()}

## Risk and rollback
The version line only. Rollback: revert this pull request before publishing.

## Not done
Publishing: after this lands, python tools/retrodev release publish {version}, then release verify {version}.
The real-machine checklist (docs/dev/RELEASE-CHECKLIST.md) is run by the owner, or the notes say it was not run.

Made by an agent (Hermes, retrodev release prepare) for the owner.
"""


def set_version(path: Path, version: str) -> None:
    manifest = path / "plugin.yaml"
    text = manifest.read_text(encoding="utf-8")
    new = VERSION_LINE.sub(f"version: {version}", text, count=1)
    if new == text:
        raise Failure(f"{manifest} has no version line to change", "add 'version: X.Y.Z' to plugin.yaml")
    manifest.write_text(new, encoding="utf-8")


def release_only(ctx, path: Path, branch: str) -> None:
    """A release worktree (new or reused) is on its branch, clean, and differs from the base only by plugin.yaml's
    version line: the release pull request's body says exactly that, so nothing else may ride along."""
    redo = f"git worktree remove {path} (after saving anything in it you want), then release prepare again"
    on = repo.git(["branch", "--show-current"], path, check=False).strip()
    if on != branch:
        raise Failure(f"{path} is on '{on or 'a detached HEAD'}', not {branch}", redo)
    dirty = repo.git(["status", "--porcelain"], path, check=False).strip()
    if dirty:
        raise Failure(f"{path} has uncommitted changes:\n{dirty[:600]}", f"commit or drop them elsewhere; {redo}")
    span = f"{ctx.remote_base}...HEAD"  # since the branch left the base
    names = repo.git(["diff", "--name-only", span], path, check=False).split()
    lines = repo.git(["diff", "-U0", span, "--", "plugin.yaml"], path, check=False).splitlines()
    changed = [line for line in lines if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    if set(names) - {"plugin.yaml"} or any(not VERSION_LINE.match(line[1:]) for line in changed):
        shown = ", ".join(names) + ("" if not changed else "; plugin.yaml: " + " | ".join(changed[:6]))
        raise Failure(f"{branch} changes more than plugin.yaml's version line ({shown[:600]})", redo)


def resume_command(version: str, words: str, rc: bool) -> str:
    """The command that finishes (or resumes) an interrupted prepare of this version."""
    flags = " --rc" if rc else ""
    return f"python tools/retrodev release prepare{flags} --version {stable(version)} --owner-words {quote(words)}"


def bind(ctx, record: dict, pr: dict) -> int:
    """An interrupted prepare's pull request, found by its branch: recorded, and the next step named."""
    number = pr["number"]
    record.update(pr=number, no_pr=False)
    state.save_release(ctx.top, record)
    ctx.out.set(pr=number, resumed=True)
    ctx.out.say(f"resumed: {record['branch']} has pull request #{number} ({pr.get('state')}); recorded")
    version = record["version"]
    if pr.get("state") == "MERGED":
        ctx.out.say(f"next: python tools/retrodev release publish {version} --dry-run, then without --dry-run")
    else:
        ctx.out.say(f"next: land #{number} like any pull request, then python tools/retrodev release publish {version}")
    return 0


def prepare(ctx, words: str | None, rc: bool = False, named: str | None = None) -> int:
    words = words_gate(words)
    repo.git(["fetch", "--quiet", "--tags", ctx.remote], ctx.main())
    version, current, needs_pr = target(ctx, rc, named)
    found = state.load_release(ctx.top, version)
    if found and found.get("published"):
        raise Failure(f"{version} is published already", f"python tools/retrodev release verify {version}")
    record = found or {"version": version}
    for chosen in ("sha", "approved"):  # asked again: publish chooses the commit afresh (an existing tag still holds)
        record.pop(chosen, None)
    # An earlier prepare that recorded its branch but not its pull request was interrupted: resume it, even when
    # the base branch says the version already (its pull request may have landed since).
    pending = bool(found and found.get("branch") and not found.get("pr"))
    record.update(words=words, at=state.now(), rc=rc)
    if not (pending and record.get("base_version")):
        record["base_version"] = current
    title = f"Release {stable(version)}"
    branch = f"chore/release-{stable(version)}"
    ctx.out.set(version=version, title=title, pr_needed=needs_pr or pending)
    if pending or needs_pr:  # resumed, or opened already (release next made it right after the last release)
        pr = github.branch_pr(ctx, branch)
        if pr:
            record.update(branch=branch, title=title)
            return bind(ctx, record, pr)
    if not needs_pr:
        record.update(pr=None, branch=None, no_pr=True)  # decided here, explicitly: publish takes the base's head
        state.save_release(ctx.top, record)
        ctx.out.say(f"{ctx.remote_base} already says {stable(version)} (untagged): no version pull request needed")
        ctx.out.say(f"next: python tools/retrodev release publish {version} --dry-run, then without --dry-run")
        return 0
    record.update(branch=branch, title=title, pr=None, no_pr=False)
    state.save_release(ctx.top, record)  # the owner's words are kept even if a step below fails
    ctx.out.say(f'recorded the owner\'s words for {version}: "{record["words"]}"')
    body_file = state.release_path(ctx.top, version).with_suffix(".md")
    state.write_atomic(body_file, body(version, record["base_version"], words, rc))
    _kind, topic = gates.parse_branch(branch, ctx.policy["branches"]["kinds"])
    path = start.worktree_path(ctx, topic)
    if not path.exists():
        start.run(ctx, branch, no_plan=True)
    tree = ctx.at(path)
    release_only(tree, path, branch)
    if version_at(tree, "HEAD") != stable(version):
        set_version(path, stable(version))
        repo.git(["add", "--", "plugin.yaml"], path)
        repo.git(["commit", "--quiet", "-m", title], path)  # only the staged manifest, never commit -a
        release_only(tree, path, branch)
        ctx.out.say(f"committed: {title} (plugin.yaml version {current} to {stable(version)})")
    resume = resume_command(version, words, rc) + " (it resumes: the same worktree, check, ship, the record)"
    try:
        checks.run(tree, [])
        ship.run(tree, title, str(body_file))
    except Failure as failure:
        raise Failure(failure.message, f"{failure.fix}; then {resume}", failure.code, failure.data)
    record = state.load_release(ctx.top, version) or record
    pr = (state.load_branch(ctx.top, branch).get("pr") or {}).get("number")
    record["pr"] = pr
    state.save_release(ctx.top, record)
    ctx.out.set(pr=pr, worktree=str(path))
    ctx.out.say(
        f"next: land it like any pull request (python tools/retrodev approve {pr} --words \"<the owner's words>\", "
        f"then land {pr}), then python tools/retrodev release publish {version}"
    )
    return 0
