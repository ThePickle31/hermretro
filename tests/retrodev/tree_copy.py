"""Copying the tree into a short temp folder for the scaffold tests (test_scaffold_tree.py, scaffold_moves.py):
the folder chosen by free space, git's own words in every failed command."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


def run(command: list[str], cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL)


GIB = 1024**3


def git_ok(case: unittest.TestCase, tree: Path, env: dict, command: list[str]) -> None:
    """git ``command`` in the copy; a failure shows git's own words (a full disk, a missing identity)."""
    done = run(["git", *command], tree, env)
    case.assertEqual(done.returncode, 0, f"git {' '.join(command)}:\n{done.stdout}{done.stderr}")


def copy_base(short: str | None, free=lambda path: shutil.disk_usage(path).free) -> tuple[str | None, str]:
    """Where the copy goes: the short folder, unless it has under 1 GB free (a small tmpfs fills up mid-copy), then
    the default temp folder, else /tmp. (folder, a note saying so when it fell back)."""
    if not short or free(short) >= GIB:
        return short, ""
    for other in (tempfile.gettempdir(), "/tmp"):
        if Path(other).is_dir() and os.path.realpath(other) != os.path.realpath(short) and free(other) >= GIB:
            return other, f"{short} has under 1 GB free: the tree's copy goes in {other} instead"
    return short, f"{short} has under 1 GB free and no other temp folder has more: the copy may fail there"


def copy_tree(source: Path, target: Path, env: dict) -> None:
    listing = run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], source, env).stdout
    names = [name for name in listing.split("\0") if name and (source / name).is_file()]
    file_list = target.parent / "files.txt"
    file_list.write_text("\0".join(names))
    subprocess.run(
        ["tar", "--null", "-T", str(file_list), "-cf", str(target.parent / "tree.tar")], cwd=source, check=True
    )
    target.mkdir()
    subprocess.run(["tar", "-xf", str(target.parent / "tree.tar")], cwd=target, check=True)
