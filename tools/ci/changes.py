"""What does a change need beyond the checks every run has? CI's job `changes` asks, with two revisions.

    python tools/ci/changes.py [--push] OLD NEW     prints engine= and upgrade= (true or false) lines
                                                    for $GITHUB_OUTPUT

engine: the integration tier (the real-engine run). A pull request (OLD is the merge commit's first parent, the
base) needs it when it touches the backend, the engine, the player, the toolchain or CI itself (ENGINE). A push
(--push: the one commit pushed, OLD its parent) always needs it, as before. Either way, a change whose only
difference is the `version:` line of plugin.yaml does not. The backend does read that line
(backend/system/paths.py: PLUGIN_VERSION, and plugin.yaml's bytes in code_fingerprint), but the engine run only
records the value: parsing it is tested by the unit job (tests/repo/test_version.py), and a changed fingerprint
(the broker replaced after an update) by the update job's check, which both still run.

upgrade: the update-dev job's update from dev as it is now to this commit (the update from the newest
published release always runs). A pull request needs it when it deletes or moves a file (a running process may
load it by path) or touches what is installed, run or registered, or the ignore rules the update check judges
leftover files by (UPGRADE), unless only the version line changed.

Paths come from `git diff --no-renames -z`: a move is its deletion and its addition, so both sides count, and no
file name can split a line. Standard library only. Its test: tests/repo/test_ci_changes.py.
"""

from __future__ import annotations

import re
import subprocess
import sys

ENGINE = re.compile(
    r"^(backend/|engine/|player/|tests/acceptance/|__init__\.py$|plugin\.yaml$|tools/check\.py$|tools/ci/"
    r"|\.github/(workflows|actions)/|profile/)"
)
# A clean install already checks the generated page bundle. The extra dev upgrade is for registration, the
# backend and broker, installer inputs and the update flow itself, not an ordinary generated bundle change. Ignore
# rules too (any .gitignore): the update check judges each ignored leftover file by them.
UPGRADE = re.compile(
    r"^(__init__\.py$|plugin\.yaml$|backend/|engine/|player/web/|page/app/update/|profile/|skills/|tools/layout\.toml$"
    r"|tools/ci/|\.github/workflows/ci\.yml$|\.github/actions/|(.+/)?\.gitignore$)"
)
# The same line tools/release.py changes (VERSION_LINE there).
VERSION_LINE = re.compile(r"^version:[ \t]*[\"']?([^\"'\s#]+)[\"']?.*$")


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True)
    if done.returncode:
        sys.exit(
            f"git {' '.join(args)} failed: {done.stderr.strip()}\nFIX: the checkout needs both revisions "
            "(actions/checkout with fetch-depth: 2)"
        )
    return done.stdout


def only_version_line(diff: str) -> bool:
    """A `git diff -U0` of plugin.yaml that removes one `version:` line and adds one, and changes nothing else."""
    changed = [line for line in diff.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    removed = [line[1:] for line in changed if line[0] == "-"]
    added = [line[1:] for line in changed if line[0] == "+"]
    return len(removed) == len(added) == 1 and all(VERSION_LINE.match(line) for line in removed + added)


def changed(old: str, new: str) -> list[tuple[str, str]]:
    """(status letter, path) for each file that differs, a move as its deletion and its addition."""
    fields = git("diff", "--no-color", "--no-renames", "-z", "--name-status", old, new).split("\0")
    pairs = list(zip(fields[0::2], fields[1::2], strict=False))
    return [(status[:1], path) for status, path in pairs if status and path]


def decide(old: str, new: str, push: bool) -> dict[str, bool]:
    files = changed(old, new)
    names = [path for _, path in files]
    plain = git("diff", "--no-color", "--no-ext-diff", "--no-renames", "-U0", old, new, "--", "plugin.yaml")
    if names == ["plugin.yaml"] and only_version_line(plain):
        return {"engine": False, "upgrade": False}
    return {
        "engine": push or any(ENGINE.match(name) for name in names),
        "upgrade": push or any(status == "D" or UPGRADE.match(name) for status, name in files),
    }


def main(argv: list[str]) -> int:
    push = "--push" in argv
    revisions = [arg for arg in argv if arg != "--push"]
    if len(revisions) != 2:
        print("usage: python tools/ci/changes.py [--push] OLD NEW\nFIX: pass the two revisions", file=sys.stderr)
        return 2
    for name, needed in decide(*revisions, push=push).items():
        print(f"{name}={'true' if needed else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
