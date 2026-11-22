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
    """The highest vX.Y.Z tag, without its v."""
    stable = [tuple(int(part) for part in match.groups()) for tag in tags if (match := STABLE_TAG.match(tag))]
    return ".".join(map(str, max(stable))) if stable else None


def next_rc(tags: list[str], version: str) -> str:
    """The tag of the next release candidate of ``version``."""
    numbers = [int(match.group(2)) for tag in tags if (match := RC_TAG.match(tag)) and match.group(1) == version]
    return f"v{version}-rc.{max(numbers, default=0) + 1}"


def version_pull_request(version: str) -> None:
    """Open (or find) the pull request that changes only the version line, from a throwaway worktree."""
    branch = f"chore/release-{version}"
    found = json.loads(run("gh", "pr", "list", "--head", branch, "--state", "all", "--json", "number,state,url"))
    if found:
        raise Stop(
            f"the version pull request is {found[0]['url']} ({found[0]['state'].lower()}): merge it when CI is "
            "green, then run this again",
            WAITING,
        )
    with tempfile.TemporaryDirectory(prefix="hermretro-release-") as folder:
        tree = Path(folder) / "tree"
        run("git", "worktree", "add", "-q", "-b", branch, str(tree), f"{REMOTE}/{BASE}")
        try:
            manifest = tree / "plugin.yaml"
            manifest.write_text(with_version(manifest.read_text(encoding="utf-8"), version), encoding="utf-8")
            run("git", "-C", str(tree), "commit", "-q", "-am", f"chore(release): version {version}")
            run("git", "-C", str(tree), "push", "-q", "-u", REMOTE, branch)
        finally:
            run("git", "worktree", "remove", "--force", str(tree))
    url = run(
        "gh",
        "pr",
        "create",
        "--base",
        BASE,
        "--head",
        branch,
        "--title",
        f"chore(release): version {version}",
        "--body",
        f"## Summary\n\nVersion {version}: only plugin.yaml's `version:` line.\n",
    )
    raise Stop(f"opened {url}: merge it when CI is green, then run this again", WAITING)


def ci_state(sha: str) -> str:
    """CI's push run on ``sha``: success, failure, or pending."""
    runs = json.loads(
        run(
            "gh",
            "run",
            "list",
            "--commit",
            sha,
            "--workflow",
            "ci.yml",
            "--event",
            "push",
            "--json",
            "status,conclusion,url",
        )
    )
    if not runs:
        return "pending"
    latest = runs[0]
    if latest["status"] != "completed":
        return "pending"
    return "success" if latest["conclusion"] == "success" else "failure"


def release(rc: bool) -> int:
    run("git", "fetch", "-q", "--tags", REMOTE, BASE, MAIN)
    tags = run("git", "tag", "--list", "v*").split()
    stable = last_stable(tags)
    sha = run("git", "rev-parse", f"{REMOTE}/{BASE}")
    version = manifest_version(run("git", "show", f"{sha}:plugin.yaml"))
    if stable and parse(version) <= parse(stable):
        version_pull_request(next_patch(stable))
    state = ci_state(sha)
    if state != "success":
        raise Stop(f"CI on {BASE} {sha[:12]} is {state}", WAITING if state == "pending" else 1)
    tag = next_rc(tags, version) if rc else f"v{version}"
    if not rc and f"v{version}" not in tags:
        main = run("git", "rev-parse", f"{REMOTE}/{MAIN}")
        if run("git", "merge-base", main, sha) != main:
            raise Stop(f"{MAIN} is not an ancestor of {BASE}: it can only fast-forward")
        # The release is the one push to main (the git hooks some agents run under allow it only here).
        run("git", "push", "-q", REMOTE, f"{sha}:refs/heads/{MAIN}", env={**os.environ, "HERMES_RELEASE": "1"})
        print(f"{MAIN} -> {sha[:12]}")
    if tag not in tags:
        run("git", "tag", tag, sha)
        run("git", "push", "-q", REMOTE, tag, env={**os.environ, "HERMES_RELEASE": "1"})
        print(f"tagged {tag}")
    existing = subprocess.run(
        ["gh", "release", "view", tag, "--json", "url,isDraft"], cwd=ROOT, capture_output=True, text=True
    )
    if existing.returncode == 0:
        print(f"release {tag}: {json.loads(existing.stdout)['url']}")
        return 0
    notes = ["--notes-start-tag", f"v{stable}"] if stable else []
    url = run(
        "gh",
        "release",
        "create",
        tag,
        "--verify-tag",
        "--generate-notes",
        *notes,
        "--draft",
        *(["--prerelease"] if rc else []),
    )
    print(f"draft {tag}: {url}\nread it, then: python tools/release.py --publish {tag}")
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
