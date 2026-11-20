"""Does a change need the integration tier (the real-engine run)? CI's job `changes` asks, with two revisions.

    python tools/ci/changes.py [--push] OLD NEW     prints engine=true or engine=false (for $GITHUB_OUTPUT)

A pull request (OLD is the merge commit's first parent, the base) needs it when it touches the backend, the engine,
the player, the toolchain or CI itself (PATHS). A push (--push: the one commit pushed, OLD its parent) always needs
it, as before. Either way, a change whose only difference is the `version:` line of plugin.yaml does not. The
backend does read that line (backend/system/paths.py: PLUGIN_VERSION, and plugin.yaml's bytes in code_fingerprint),
but the engine run only records the value: parsing it is tested by the unit job (tests/repo/test_version.py), and a
changed fingerprint (the broker replaced after an update) by the validate job's update check, which both still run.
Standard library only. Its test: tests/repo/test_ci_changes.py.
"""

from __future__ import annotations

import re
import subprocess
import sys

PATHS = re.compile(
    r"^(backend/|engine/|player/|tests/acceptance/|__init__\.py$|plugin\.yaml$|tools/check\.py$|tools/ci/"
    r"|\.github/(workflows|actions)/|profile/)"
)
# The same line release prepare changes (tools/retrodev/release.py VERSION_LINE).
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


def needs_engine(old: str, new: str, push: bool) -> bool:
    names = [name for name in git("diff", "--no-color", "--name-only", old, new).splitlines() if name]
    plain = git("diff", "--no-color", "--no-ext-diff", "-U0", old, new, "--", "plugin.yaml")
    if names == ["plugin.yaml"] and only_version_line(plain):
        return False
    return push or any(PATHS.match(name) for name in names)


def main(argv: list[str]) -> int:
    push = "--push" in argv
    revisions = [arg for arg in argv if arg != "--push"]
    if len(revisions) != 2:
        print("usage: python tools/ci/changes.py [--push] OLD NEW\nFIX: pass the two revisions", file=sys.stderr)
        return 2
    print("engine=" + ("true" if needs_engine(*revisions, push=push) else "false"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
