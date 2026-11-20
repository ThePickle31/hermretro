"""git helpers: where the main checkout and the worktrees are, what a branch changed, and a digest of the tree.

The main checkout is the parent of git's common directory (shared by every worktree). The tree digest is the
idea of tools/check.py's tree_digest: a content hash of what a commit of this tree would hold (tracked files
plus new files git does not ignore). It is computed from git's own blob ids, hashing only the files git says
differ from the index, so it costs a few milliseconds on the whole repository.
"""

from __future__ import annotations

import fnmatch
import functools
import hashlib
import os
import shlex
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .output import Failure


class GitError(Failure):
    pass


def run(
    command: list[str], cwd: Path | str, timeout: float | None = None, env: dict | None = None, feed: str | None = None
) -> tuple[int, str, str]:
    """Run a command (every git and tool call retrodev makes, except gh and the checks' live output), ``feed`` on its
    stdin (else none). Output that is not UTF-8 (a binary blob, a file name in another encoding) reads with U+FFFD in
    place of the bytes, never an exception: read file contents with blob() instead."""
    try:
        done = subprocess.run(
            command,
            cwd=str(cwd),
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            **({"input": feed} if feed is not None else {"stdin": subprocess.DEVNULL}),
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"{command[0]} did not finish in {timeout:g} s"
    except OSError as error:
        return 127, "", str(error)
    return done.returncode, done.stdout, done.stderr


def git(args: list[str], cwd: Path | str, check: bool = True) -> str:
    """Run git in ``cwd`` and return its stdout; a failure raises GitError with git's own message."""
    code, out, err = run(["git", *args], cwd)
    if check and code:
        raise GitError(
            f"git {shlex.join(args)} failed: {(err or out).strip()}",
            "read git's message above; run the same git command yourself to see the whole state",
        )
    return out


def blob(cwd: Path | str, spec: str) -> bytes | None:
    """The bytes of the blob ``spec`` (``<rev>:<path>``, ``:<path>`` for the index); None when it is not there."""
    try:
        done = subprocess.run(
            ["git", "cat-file", "blob", spec], cwd=str(cwd), capture_output=True, stdin=subprocess.DEVNULL
        )
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def text(data: bytes) -> str | None:
    """``data`` as text, or None for a binary file (a NUL byte anywhere, or bytes that are not UTF-8):
    nothing that counts lines may read it."""
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def ok(args: list[str], cwd: Path | str) -> bool:
    return run(["git", *args], cwd)[0] == 0


def toplevel(cwd: Path | str) -> Path:
    return _toplevel(str(Path(cwd).resolve()))


@functools.cache
def _toplevel(cwd: str) -> Path:
    # A folder's checkout never changes while one command runs, and every command asks many times.
    code, out, _err = run(["git", "rev-parse", "--show-toplevel"], cwd)
    if code:
        raise Failure(
            f"{cwd} is not inside a git checkout of hermretro",
            "cd into the hermretro checkout or one of its worktrees, then run the command again",
        )
    return Path(out.strip()).resolve()


def common_dir(cwd: Path | str) -> Path:
    """git's common directory (the main checkout's .git), shared by every worktree."""
    return _common_dir(str(Path(cwd).resolve()))


@functools.cache
def _common_dir(cwd: str) -> Path:
    out = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd).strip()
    return Path(out).resolve()


def main_checkout(cwd: Path | str) -> Path:
    return common_dir(cwd).parent


def branch(cwd: Path | str) -> str | None:
    """The checked-out branch, or None on a detached HEAD."""
    return git(["symbolic-ref", "--short", "-q", "HEAD"], cwd, check=False).strip() or None


def head(cwd: Path | str, ref: str = "HEAD") -> str | None:
    return git(["rev-parse", "-q", "--verify", ref + "^{commit}"], cwd, check=False).strip() or None


def dirty(cwd: Path | str) -> list[str]:
    """Uncommitted changes, as `git status --porcelain` lines (untracked, not ignored files included)."""
    out = git(["--no-optional-locks", "status", "--porcelain", "--untracked-files=all"], cwd)
    return [line for line in out.splitlines() if line.strip()]


def is_ancestor(cwd: Path | str, older: str, newer: str) -> bool:
    return ok(["merge-base", "--is-ancestor", older, newer], cwd)


@dataclass
class Worktree:
    path: Path
    head: str | None
    branch: str | None
    main: bool


def worktrees(cwd: Path | str) -> list[Worktree]:
    out = git(["worktree", "list", "--porcelain"], cwd)
    found, current = [], {}
    for line in out.splitlines() + [""]:
        if not line:
            if current:
                ref = current.get("branch", "")
                found.append(
                    Worktree(
                        path=Path(current["worktree"]),
                        head=current.get("HEAD"),
                        branch=ref.removeprefix("refs/heads/") or None,
                        main=not found,
                    )
                )
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return found


def remote_ref(remote: str, name: str) -> str:
    return f"refs/remotes/{remote}/{name}"


def merge_base(cwd: Path | str, base: str) -> str | None:
    return git(["merge-base", base, "HEAD"], cwd, check=False).strip() or None


def changed_files(cwd: Path | str, base: str) -> list[str] | None:
    """Files this branch changed since it left ``base`` (committed, uncommitted and new); None without ``base``. A
    renamed file counts at both paths (git's rename detection would list only the new one, so a trigger file moved
    away, or a body naming the old path, would go unseen)."""
    point = merge_base(cwd, base)
    if not point:
        return None
    names = set(git(["diff", "--no-renames", "--name-only", "-z", point], cwd).split("\0"))
    names |= set(git(["ls-files", "-z", "--others", "--exclude-standard"], cwd).split("\0"))
    return sorted(name for name in names if name)


def moved_or_deleted(cwd: Path | str, base: str) -> list[str]:
    """Files the branch moved or deleted since it left ``base`` (an update must cope with them)."""
    point = merge_base(cwd, base)
    if not point:
        return []
    out = git(["diff", "--name-status", "--diff-filter=DR", point], cwd)  # R: "R100<TAB>old<TAB>new"
    return [line.split("\t")[1] for line in out.splitlines() if "\t" in line]


def _blob_id(path: Path) -> str:
    """git's mode and blob id for a file as it is now, as `git ls-files -s` would give them once it is added.

    A symlink is mode 120000 with its target as content; a file is 100755 when its owner may run it, else 100644.
    """
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        mode, data = "120000", os.readlink(path).encode()
    else:
        mode, data = ("100755" if info.st_mode & stat.S_IXUSR else "100644"), path.read_bytes()
    return f"{mode} " + hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def file_ids(cwd: Path | str) -> dict[str, str]:
    """{path: "mode blob-id"} for what a commit of this tree would hold: tracked files plus new, not ignored files.

    The mode is part of a file's identity: an executable bit or a file turned symlink changes the digest.
    """
    root = Path(cwd)
    ids = {}
    for entry in git(["ls-files", "-s", "-z"], root).split("\0"):
        if not entry:
            continue
        meta, _, name = entry.partition("\t")
        mode, sha, _stage = meta.split()
        if mode != "160000":  # a submodule has no content here
            ids[name] = f"{mode} {sha}"
    status = git(
        ["--no-optional-locks", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames"], root
    )
    for entry in status.split("\0"):
        if len(entry) < 4:
            continue
        name = entry[3:]
        path = root / name
        if path.is_symlink() or path.is_file():
            ids[name] = _blob_id(path)
        else:
            ids.pop(name, None)  # deleted in the worktree
    return ids


def head_ids(cwd: Path | str) -> dict[str, str]:
    """{path: "mode blob-id"} of the committed HEAD (what an install from the commit gets), as file_ids."""
    ids = {}
    for entry in git(["ls-tree", "-r", "-z", "--full-tree", "HEAD"], cwd).split("\0"):
        meta, _, name = entry.partition("\t")
        if meta:
            mode, _kind, sha = meta.split()
            if mode != "160000":
                ids[name] = f"{mode} {sha}"
    return ids


def digest(ids: dict[str, str], patterns: list[str] | None = None) -> str:
    """One sha256 over the files matching ``patterns`` (fnmatch, * also matches /; None: every file)."""
    hasher = hashlib.sha256()
    for name in sorted(ids):
        if patterns is None or matches(name, patterns):
            hasher.update(f"{name}\0{ids[name]}\n".encode())
    return hasher.hexdigest()


def matches(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def tree_digest(cwd: Path | str) -> str:
    return digest(file_ids(cwd))
