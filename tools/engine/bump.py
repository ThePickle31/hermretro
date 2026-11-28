#!/usr/bin/env python3
"""Record a change to the engine: its version, its line in the changelog, its bundle and its manifest.

    python tools/engine/bump.py "<files>: what changed and why"
    python tools/engine/bump.py --base REF "<line>"      the revision whose version to raise (default origin/dev)

A branch's first change to the engine raises the patch version in `engine/package.json` above the base's (2.0.2 to
2.0.3) and starts `engine/CHANGES.md`'s list with that version's heading; a later change on the same branch adds its
line under the same heading. Then it rebuilds `dist/server.js` from the modules (`tools/engine/bundle.mjs`) and writes
the manifest (`tools/engine/manifest.py write`), which the plugin starts the engine against. What it records is what
CI's `engine-version` job (`tools/engine/version.py`) and tests/repo/test_engine_version.py check.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import version  # noqa: E402 - tools/engine/ goes on sys.path first

from backend.system import paths  # noqa: E402 - version puts the repository root on sys.path

ROOT = paths.PLUGIN_ROOT
PACKAGE = ROOT / version.PACKAGE
CHANGES = paths.ENGINE_ROOT / "CHANGES.md"
HEADING = re.compile(r"(?m)^## ([0-9]+\.[0-9]+\.[0-9]+)$")
VERSION_FIELD = re.compile(r'("version"\s*:\s*")([0-9]+\.[0-9]+\.[0-9]+)(")')
WIDTH = 118  # the changelog's own line length


class Refused(Exception):
    """The change cannot be recorded as asked; the message ends with its FIX line."""


def dotted(numbers: tuple[int, int, int]) -> str:
    return ".".join(map(str, numbers))


def next_version(current: tuple[int, int, int], base: tuple[int, int, int] | None) -> tuple[int, int, int]:
    """The version a change goes under: the current one when this branch already raised it above the base's (or
    the base has no engine), otherwise the patch after the base's (a branch behind its base gets past it too)."""
    if base is None or current > base:
        return current
    return (base[0], base[1], base[2] + 1)


def with_version(package: str, new: str) -> str:
    """package.json's text with its version replaced, its formatting kept."""
    changed = VERSION_FIELD.sub(lambda found: found[1] + new + found[3], package, count=1)
    if json.loads(changed).get("version") != new:
        raise Refused(f'{PACKAGE} holds no top-level "version" to raise\nFIX: give it one, such as "version": "2.0.0"')
    return changed


def with_line(changes: str, new: str, line: str) -> str:
    """CHANGES.md's text with the line last under the heading for `new`, which starts the list when it is not
    there yet."""
    entry = textwrap.fill(
        " ".join(line.split()),
        width=WIDTH,
        initial_indent="- ",
        subsequent_indent="  ",
        break_long_words=False,
        break_on_hyphens=False,
    )
    first = HEADING.search(changes)
    if first is None:
        raise Refused(f"{CHANGES} has no version heading\nFIX: start its list with the current version's, ## x.y.z")
    if first[1] != new:
        return f"{changes[: first.start()]}## {new}\n\n{entry}\n\n{changes[first.start() :]}"
    following = HEADING.search(changes, first.end())
    end = following.start() if following else len(changes)
    section = changes[first.end() : end].rstrip("\n")
    return f"{changes[: first.end()]}{section}\n{entry}\n" + (f"\n{changes[end:]}" if following else "")


def base_version(base: str) -> tuple[int, int, int] | None:
    found = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"], cwd=ROOT, capture_output=True
    )
    if found.returncode:
        raise Refused(f"no revision {base} here\nFIX: git fetch origin, or name the base with --base REF")
    return version.version_at(base)


def run(step: list[str], fix: str) -> None:
    """One step, quiet unless it fails."""
    done = subprocess.run(step, cwd=ROOT, capture_output=True, text=True)
    if done.returncode:
        said = (done.stdout + done.stderr).strip()
        raise Refused(f"{' '.join(step)} failed:\n{said}\nFIX: {fix}")


def record(line: str, base: str) -> str:
    """Rebuild the bundle, write the version and the line, then the manifest; the version the change went under.
    The bundle comes first, since a module that does not build stops it with nothing written (the server reads
    its version from package.json as it starts, so the bundle does not hold it)."""
    package = PACKAGE.read_text(encoding="utf-8")
    current = version.VERSION.fullmatch(str(json.loads(package).get("version")))
    if current is None:
        raise Refused(f"{PACKAGE} holds no x.y.z version\nFIX: give it one, such as 2.0.0")
    new = dotted(next_version(tuple(int(part) for part in current.groups()), base_version(base)))
    package, changes = with_version(package, new), with_line(CHANGES.read_text(encoding="utf-8"), new, line)
    run(["node", "tools/engine/bundle.mjs"], "fix what the bundler says, then run this again")
    PACKAGE.write_text(package, encoding="utf-8")
    CHANGES.write_text(changes, encoding="utf-8")
    run(
        [sys.executable, "tools/engine/manifest.py", "write"],
        "python tools/engine/manifest.py write (the rest is done)",
    )
    return new


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a change to the engine.")
    parser.add_argument("line", help='its changelog line: "<files>: what changed and why"')
    parser.add_argument("--base", default="origin/dev", help="the revision whose version to raise")
    args = parser.parse_args(argv)
    if not args.line.strip():
        parser.error("the changelog line is empty")
    os.chdir(ROOT)  # git reads the base in this repository, wherever this was started from
    try:
        new = record(args.line, args.base)
    except Refused as refused:
        print(refused, file=sys.stderr)
        return 1
    print(f"ok: engine {new}, its line in {CHANGES.relative_to(ROOT)}, the bundle and the manifest written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
