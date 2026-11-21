"""Print the preceding published stable commit for a manual verification of HEAD.

Standard input is the paginated GitHub releases response (`gh api --paginate --slurp`). Git supplies
version order and ancestry. HEAD itself is never an upgrade baseline, even when already tagged.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def choose(pages: object) -> str:
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        raise ValueError("expected a paginated GitHub releases response")
    published = set()
    for page in pages:
        for entry in page:
            if not isinstance(entry, dict) or not isinstance(entry.get("tag_name"), str):
                raise ValueError("a GitHub release has no tag name")
            if entry.get("draft") is False and entry.get("prerelease") is False and entry.get("published_at"):
                published.add(entry["tag_name"])
    candidate = git("rev-parse", "HEAD")
    for tag in git("tag", "--merged", candidate, "--list", "v*", "--sort=-v:refname").splitlines():
        if tag in published and TAG.fullmatch(tag):
            baseline = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
            if baseline != candidate:
                return baseline
    raise ValueError("no earlier published stable release is an ancestor of HEAD")


if __name__ == "__main__":
    try:
        print(choose(json.load(sys.stdin)))
    except (ValueError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        sys.exit(
            f"Could not choose an upgrade baseline: {detail}\nFIX: fetch the tags and dispatch on a commit with a published ancestor."
        )
