"""python tools/release.py [--rc] [--publish VERSION]: make a release, only when the owner asks for one.

Run it again after each step; it picks up where things are:

  1. When `dev` still says the last released version, it opens the version pull request
     (chore/release-X.Y.Z, only plugin.yaml's `version:` line) and stops: merge it when CI is green, then run again.
  2. It waits for CI on `dev`'s head to pass (exit 2 while it runs).
  3. A release fast-forwards `main` to that commit (never for --rc), tags it vX.Y.Z (or vX.Y.Z-rc.N) and pushes the tag.
  4. It makes the GitHub release as a draft, its notes generated from the pull request titles since the last
     stable release (grouped by .github/release.yml), and prints its address.

`--publish vX.Y.Z` publishes that draft once the owner has read it (published releases cannot change).
Versions are patch-only. Exit codes: 0 done, 1 failed, 2 waiting (run again later). Standard library, git and gh.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTE, BASE, MAIN = "origin", "dev", "main"
VERSION_LINE = re.compile(r"^version:[ \t]*[\"']?([^\"'\s#]+)[\"']?.*$", re.MULTILINE)
STABLE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
RC_TAG = re.compile(r"^v(\d+\.\d+\.\d+)-rc\.(\d+)$")
WAITING = 2


class Stop(Exception):
    """A step that cannot go on: its message, and the exit code."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def run(*command: str, env: dict | None = None) -> str:
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env)
    if done.returncode:
        raise Stop(f"{' '.join(command)} failed: {(done.stderr or done.stdout).strip()}")
    return done.stdout.strip()


def manifest_version(text: str) -> str:
    match = VERSION_LINE.search(text)
    if not match:
        raise Stop("plugin.yaml has no version: line")
    return match.group(1)


def with_version(text: str, version: str) -> str:
    """plugin.yaml's text with only the version on its version line changed."""
    match = VERSION_LINE.search(text)
    if not match:
        raise Stop("plugin.yaml has no version: line")
    return text[: match.start(1)] + version + text[match.end(1) :]


def parse(version: str) -> tuple[int, int, int]:
    match = STABLE_TAG.match(f"v{version}")
    if not match:
        raise Stop(f"{version!r} is not X.Y.Z")
    return tuple(int(part) for part in match.groups())


def next_patch(version: str) -> str:
    major, minor, patch = parse(version)
    return f"{major}.{minor}.{patch + 1}"


def last_stable(tags: list[str]) -> str | None:
    """The highest vX.Y.Z of ``tags``, without its v."""
    stable = [tuple(int(part) for part in match.groups()) for tag in tags if (match := STABLE_TAG.match(tag))]
    return ".".join(map(str, max(stable))) if stable else None


def last_rc(tags: list[str], version: str) -> str | None:
    """The newest release candidate tag of ``version``."""
    numbers = [int(match.group(2)) for tag in tags if (match := RC_TAG.match(tag)) and match.group(1) == version]
    return f"v{version}-rc.{max(numbers)}" if numbers else None


def next_rc(tags: list[str], version: str) -> str:
    """The tag of the next release candidate of ``version``."""
    latest = last_rc(tags, version)
    return f"v{version}-rc.{int(latest.rsplit('.', 1)[1]) + 1 if latest else 1}"


def remote_tags() -> dict[str, str]:
    """The tags on the remote, each with its commit: a tag only made here (its push failed) does not count."""
    found: dict[str, str] = {}
    for line in run("git", "ls-remote", "--tags", REMOTE, "v*").splitlines():
        sha, ref = line.split("\t")
        name = ref.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            found[name[:-3]] = sha  # an annotated tag's commit
        else:
            found.setdefault(name, sha)
    return found


def github_releases() -> dict[str, bool]:
    """GitHub's releases by tag: True once published, False while a draft."""
    listed = json.loads(run("gh", "release", "list", "--limit", "200", "--json", "tagName,isDraft"))
    return {item["tagName"]: not item["isDraft"] for item in listed}


def version_pull_request(version: str) -> None:
    """Find, or open, the pull request that changes only the version line; always stops (the owner's CI to wait on)."""
    branch = f"chore/release-{version}"
    prs = json.loads(run("gh", "pr", "list", "--head", branch, "--base", BASE, "--state", "all", "--json", "state,url"))
    if live := [pr for pr in prs if pr["state"] == "OPEN"]:
        raise Stop(f"the version pull request is {live[0]['url']}: merge it when CI is green, then run again", WAITING)
    if closed := [pr for pr in prs if pr["state"] == "CLOSED"]:
        raise Stop(
            f"{closed[0]['url']} was closed without merging: reopen it, or delete the branch {branch} on "
            f"{REMOTE}, then run again"
        )
    if run("git", "ls-remote", "--heads", REMOTE, branch):
        # An earlier run pushed the branch, then stopped before the pull request: open it if it is only the version.
        run("git", "fetch", "-q", REMOTE, branch)
        changed = run("git", "diff", "--name-only", f"{REMOTE}/{BASE}...{REMOTE}/{branch}").split()
        said = manifest_version(run("git", "show", f"{REMOTE}/{branch}:plugin.yaml"))
        if changed != ["plugin.yaml"] or said != version:
            raise Stop(
                f"{REMOTE}/{branch} changes {changed} to version {said}, not only the version line to {version}: "
                "delete that branch, then run again"
            )
    else:
        with tempfile.TemporaryDirectory(prefix="hermretro-release-") as folder:
            tree = Path(folder) / "tree"
            run("git", "worktree", "add", "-q", "-B", branch, str(tree), f"{REMOTE}/{BASE}")
            try:
                manifest = tree / "plugin.yaml"
                manifest.write_text(with_version(manifest.read_text(encoding="utf-8"), version), encoding="utf-8")
                run("git", "-C", str(tree), "commit", "-q", "-am", f"chore(release): version {version}")
                run("git", "-C", str(tree), "push", "-q", "-u", REMOTE, branch)
            finally:
                run("git", "worktree", "remove", "--force", str(tree))
    title, body = (
        f"chore(release): version {version}",
        f"## Summary\n\nVersion {version}: only plugin.yaml's `version:` line.\n",
    )
    url = run("gh", "pr", "create", "--base", BASE, "--head", branch, "--title", title, "--body", body)
    raise Stop(f"opened {url}: merge it when CI is green, then run again", WAITING)


def ci_state(sha: str) -> str:
    """CI's push run on ``sha``: success, failure, or pending."""
    fields = ["--workflow", "ci.yml", "--event", "push", "--json", "status,conclusion"]
    runs = json.loads(run("gh", "run", "list", "--commit", sha, *fields))
    if not runs or runs[0]["status"] != "completed":
        return "pending"
    return "success" if runs[0]["conclusion"] == "success" else "failure"


def release(rc: bool) -> int:
    """Each run reads where the release stands (the tags on the remote, GitHub's releases, main) and does what is left."""
    run("git", "fetch", "-q", REMOTE, BASE, MAIN)
    tags, made = remote_tags(), github_releases()
    published = last_stable([tag for tag, done in made.items() if done])
    dev, main = run("git", "rev-parse", f"{REMOTE}/{BASE}"), run("git", "rev-parse", f"{REMOTE}/{MAIN}")
    version = manifest_version(run("git", "show", f"{dev}:plugin.yaml"))
    if published and parse(version) <= parse(published):
        version_pull_request(next_patch(published))
    if rc:
        # An unpublished candidate is finished, not replaced by a new number.
        latest = last_rc(list(tags), version)
        tag = latest if latest and not made.get(latest) else next_rc(list(tags), version)
    else:
        tag = f"v{version}"
    sha = tags.get(tag)
    if sha is None:
        # main moves only at a release: when it already says this version, an earlier run moved it and stopped.
        sha = main if not rc and manifest_version(run("git", "show", f"{main}:plugin.yaml")) == version else dev
        state = ci_state(sha)
        if state != "success":
            raise Stop(f"CI on {sha[:12]} is {state}", WAITING if state == "pending" else 1)
        if not rc and main != sha:
            if run("git", "merge-base", main, sha) != main:
                raise Stop(f"{MAIN} is not an ancestor of {sha[:12]}: it can only fast-forward")
            # The release is the one push to main (the git hooks some agents run under allow it only here).
            run("git", "push", "-q", REMOTE, f"{sha}:refs/heads/{MAIN}", env={**os.environ, "HERMES_RELEASE": "1"})
            print(f"{MAIN} -> {sha[:12]}")
        run("git", "tag", "-f", tag, sha)  # replaces a tag an earlier run made here but could not push
        run("git", "push", "-q", REMOTE, f"refs/tags/{tag}", env={**os.environ, "HERMES_RELEASE": "1"})
        print(f"tagged {tag} at {sha[:12]}")
    if tag in made:
        state = "published" if made[tag] else f"a draft: read it, then python tools/release.py --publish {tag}"
        print(f"release {tag} is {state}")
        return 0
    notes = ["--notes-start-tag", f"v{published}"] if published else []
    kind = ["--prerelease"] if rc else []
    url = run("gh", "release", "create", tag, "--verify-tag", "--generate-notes", *notes, "--draft", *kind)
    print(
        f"draft {tag}: {url}\nput the checklist's result in its notes, read it, then: python tools/release.py --publish {tag}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python tools/release.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--rc", action="store_true", help="a release candidate: tag dev's head, main stays")
    parser.add_argument("--publish", metavar="VERSION", help="publish the draft vX.Y.Z")
    args = parser.parse_args(argv)
    try:
        if args.publish:
            tag = args.publish if args.publish.startswith("v") else f"v{args.publish}"
            print(run("gh", "release", "edit", tag, "--draft=false"))
            return 0
        return release(args.rc)
    except Stop as stop:
        print(stop, file=sys.stderr if stop.code == 1 else sys.stdout)
        return stop.code


if __name__ == "__main__":
    sys.exit(main())
