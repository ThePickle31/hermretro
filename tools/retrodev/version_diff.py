"""Whether a range of commits changes only plugin.yaml's ``version:`` line: what a release's version pull request may
change. release run, the release guard and land's release-approval gate ask it of exact commits; CI's
tools/ci/changes.py applies the same rule to its integration tier (kept apart: tools/ci and retrodev import nothing
of each other).
"""

from __future__ import annotations

import re

from . import repo

# diff output to parse, whatever the user's git config says (color.ui=always would prefix every line with escapes)
PLAIN = ("--no-color", "--no-ext-diff")

VERSION_LINE = re.compile(r"^version:[ \t]*[\"']?([^\"'\s#]+)[\"']?.*$")  # release.VERSION_LINE, one line at a time


def only_version_line(diff: str) -> bool:
    """A `git diff -U0` of plugin.yaml that removes one `version:` line and adds one, and changes nothing else."""
    changed = [line for line in diff.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    removed = [line[1:] for line in changed if line[0] == "-"]
    added = [line[1:] for line in changed if line[0] == "+"]
    return len(removed) == len(added) == 1 and all(VERSION_LINE.match(line) for line in removed + added)


def beyond_version(top, old: str, new: str) -> str | None:
    """None when ``old``..``new`` changes only plugin.yaml's version line; else what it changes besides."""
    names = repo.git(["diff", *PLAIN, "--name-only", old, new], top).split()
    diff = repo.git(["diff", *PLAIN, "-U0", old, new, "--", "plugin.yaml"], top)
    if names == ["plugin.yaml"] and only_version_line(diff):
        return None
    lines = [line for line in diff.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    return (", ".join(names) or "no file") + ("; plugin.yaml: " + " | ".join(lines[:6]) if lines else "")
