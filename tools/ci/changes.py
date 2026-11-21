"""What does a change need beyond the checks every run has? CI's job `changes` asks, with two revisions.

    python tools/ci/changes.py [--push] OLD NEW     prints engine=, scaffold= and upgrade= (true or false) lines
                                                    for $GITHUB_OUTPUT

engine: the integration tier (the real-engine run). A pull request (OLD is the merge commit's first parent, the
base) needs it when it touches the backend, the engine, the player, the toolchain or CI itself (ENGINE). A push
(--push: the one commit pushed, OLD its parent) always needs it, as before. Either way, a change whose only
difference is the `version:` line of plugin.yaml does not. The backend does read that line
(backend/system/paths.py: PLUGIN_VERSION, and plugin.yaml's bytes in code_fingerprint), but the engine run only
records the value: parsing it is tested by the unit job (tests/repo/test_version.py), and a changed fingerprint
(the broker replaced after an update) by the validate job's update check, which both still run.

scaffold: the page job's nested scaffold run (RD_SCAFFOLD_FULL=nested: every `retrodev new` kind, on the real
features and pages too, then the full suites in that grown copy) instead of its smoke (one `new` of every kind,
focused checks). A pull request needs it when it touches what `new` is or reads, the checks that judge it, or the
tests the grown copy runs that read the surrounding tree (SCAFFOLD); every push to dev runs it.

upgrade: the validate job's extra update from dev as it is now to this commit (the update from the newest
published release always runs). A pull request needs it when it deletes or moves a file (a running process may
load it by path) or touches what is installed, run or registered (UPGRADE), unless only the version line changed.

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
# retrodev itself and its templates, the files `new` parses (as tools/retrodev/policy.toml's scaffold triggers), the
# checks that judge the copy, the tests run in the grown copy that read the tree, and CI's own decision.
SCAFFOLD = re.compile(
    r"^(tools/retrodev/|tools/check\.py$|tools/bundle/|tools/py/|tools/npm/|tools/layout\.toml$|tests/retrodev/|tests/repo/"
    r"|tests/support\.py$|tests/page/(harness|shells|sdk-stub|aliases)\.mjs$|tests/page/preview/"
    r"|backend/features\.py$|page/pages/index\.js$|page/pages/build/transcript/step-words\.js$|plugin\.yaml$"
    r"|docs/dev/(ARCHITECTURE|CONTRACT|STUDIO-PAGES)\.md$|tools/ci/changes\.py$|\.github/workflows/ci\.yml$)"
)
# A clean install already checks the generated page bundle. The extra dev upgrade is for registration, the
# backend and broker, installer inputs and the update flow itself, not an ordinary generated bundle change.
UPGRADE = re.compile(
    r"^(__init__\.py$|plugin\.yaml$|backend/|engine/|player/web/|page/app/update/|profile/|skills/|tools/layout\.toml$"
    r"|tools/ci/|\.github/workflows/ci\.yml$|\.github/actions/)"
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
        return {"engine": False, "scaffold": push, "upgrade": False}
    return {
        "engine": push or any(ENGINE.match(name) for name in names),
        "scaffold": push or any(SCAFFOLD.match(name) for name in names),
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
