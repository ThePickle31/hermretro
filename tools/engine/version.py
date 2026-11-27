#!/usr/bin/env python3
"""Every change to the engine raises its version (2.0.0, then 2.0.1, 2.0.2 and so on).

    python tools/engine/version.py OLD NEW    fails when NEW changes the engine but not its version

The version has one home, `engine/package.json`: the backend (backend/system/paths.py) and the engine's server read
it there. A change to the engine is a change to a file its manifest records, which is everything under `engine/` but
its record (`ENGINE_RECORD`: `contract/` and `CHANGES.md`), so a note in the changelog needs no new version. The
version's heading in `engine/CHANGES.md` is checked by tests/repo/test_engine_version.py, which tests this too.

CI's job `engine-version` runs it on a pull request with the base (the merge commit's first parent) and the merge
commit, in the repository's root. Paths come from `git diff --no-renames -z`, so a move counts on both sides.
Standard library only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

ENGINE = PurePosixPath(paths.ENGINE_ROOT.relative_to(paths.PLUGIN_ROOT).as_posix())
PACKAGE = ENGINE / "package.json"
VERSION = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def engine_changes(old: str, new: str) -> list[str]:
    """The files under engine/ that differ between the two revisions, but the engine's record."""
    done = git("diff", "--no-color", "--no-renames", "-z", "--name-only", old, new, "--", ENGINE.as_posix())
    if done.returncode:
        sys.exit(
            f"git diff {old} {new} failed: {done.stderr.strip()}\n"
            "FIX: the checkout needs both revisions (actions/checkout with fetch-depth: 2)"
        )
    names = [PurePosixPath(name) for name in done.stdout.split("\0") if name]
    return [name.as_posix() for name in names if name.relative_to(ENGINE).parts[0] not in paths.ENGINE_RECORD]


class Unreadable(Exception):
    """engine/package.json is there but holds no x.y.z version."""


def version_at(revision: str) -> tuple[int, int, int] | None:
    """The engine's version at a revision, or None when it has no engine/package.json there."""
    done = git("show", f"{revision}:{PACKAGE.as_posix()}")
    if done.returncode:
        return None
    try:
        package = json.loads(done.stdout)
    except ValueError:
        package = None
    version = package.get("version") if isinstance(package, dict) else None
    found = VERSION.fullmatch(version) if isinstance(version, str) else None
    if not found:
        raise Unreadable(f"{PACKAGE} at {revision} holds no x.y.z version")
    return tuple(int(part) for part in found.groups())


def problem(old: str, new: str) -> str | None:
    """Why NEW needs a new engine version, or None when it does not."""
    changed = engine_changes(old, new)
    if not changed:
        return None
    named = ", ".join(changed[:5]) + (f" and {len(changed) - 5} more" if len(changed) > 5 else "")
    try:
        before, after = version_at(old), version_at(new)
    except Unreadable as error:
        return f'{error}.\nFIX: give it a "version" such as 2.0.1, above the base\'s'
    if after is None:
        return (
            f"The engine changed ({named}) but {PACKAGE}, the only record of its version, is gone.\n"
            f"FIX: keep {PACKAGE} where it is, with its version raised"
        )
    if before is None or after > before:  # a base without an engine has no version to raise
        return None
    base, current = ".".join(map(str, before)), ".".join(map(str, after))
    moved = f"is still {current}" if after == before else f"went down from {base} to {current}"
    following = f"{before[0]}.{before[1]}.{before[2] + 1}"
    return (
        f"The engine changed ({named}) but its version {moved}.\n"
        f'FIX: set "version" in {PACKAGE} to {following}, start engine/CHANGES.md\'s list for it with '
        f'"## {following}", then python tools/engine/manifest.py write'
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python tools/engine/version.py OLD NEW\nFIX: pass the two revisions", file=sys.stderr)
        return 2
    found = problem(*argv)
    if found:
        print(found, file=sys.stderr)
        return 1
    print("ok: the engine is unchanged or its version went up")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
