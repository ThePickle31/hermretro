"""Validate live files against the backup before changing the project."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

DirectoryId = tuple[int, int]
FileStamp = tuple[int, int, int, int, int]
Digest = tuple[int, str]
PROJECT_SUFFIX = ".gbsproj"
_CHUNK = 1024 * 1024


@dataclass
class LiveTree:
    files: dict[str, tuple[FileStamp, Digest]] = field(default_factory=dict)
    directories: dict[str, DirectoryId] = field(default_factory=dict)
    excluded: set[DirectoryId] = field(default_factory=set)
    other_games: set[DirectoryId] = field(default_factory=set)


def directory_id(info: os.stat_result) -> DirectoryId:
    if not stat.S_ISDIR(info.st_mode):
        raise OSError("a link or file is in the way")
    return info.st_dev, info.st_ino


def file_stamp(info: os.stat_result) -> FileStamp:
    if not stat.S_ISREG(info.st_mode):
        raise OSError("a link or file is in the way")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def file_digest(
    path: Path | str, limit: int, writer=None, *, dir_fd: int | None = None, expected_stamp: FileStamp | None = None
) -> Digest:
    """Read a regular file without following a final symlink, optionally copying it in the same pass."""
    digest = hashlib.sha256()
    size = 0
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    with os.fdopen(fd, "rb") as handle:
        stamp = file_stamp(os.fstat(fd))
        if expected_stamp is not None and stamp != expected_stamp:
            raise OSError(f"{path} changed during the snapshot operation")
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            size += len(chunk)
            if size > limit:
                raise OSError(f"{path} became larger during the snapshot operation")
            digest.update(chunk)
            if writer is not None:
                writer.write(chunk)
        if (
            file_stamp(os.fstat(fd)) != stamp
            or file_stamp(os.stat(path, dir_fd=dir_fd, follow_symlinks=False)) != stamp
        ):
            raise OSError(f"{path} changed during the snapshot operation")
    return size, digest.hexdigest()


def _check_project_marker(fd: int) -> None:
    with os.scandir(fd) as entries:
        for entry in entries:
            if entry.name.lower().endswith(PROJECT_SUFFIX) and (
                entry.is_file(follow_symlinks=False) or entry.is_symlink()
            ):
                raise OSError("now part of another game")


@contextmanager
def _parent(root: Path, relative: str, live: LiveTree, *, create: bool = False):
    """Keep each ancestor open and recheck the chain before mutating through its descriptors."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    with ExitStack() as opened:
        root_fd = os.open(root, flags)
        opened.callback(os.close, root_fd)
        root_id = live.directories[""]
        if directory_id(os.fstat(root_fd)) != root_id:
            raise OSError("the project folder changed after backup")
        ancestors = []

        def check():
            if directory_id(root.lstat()) != root_id or Path(os.path.realpath(root, strict=True)) != root:
                raise OSError("the project folder changed after backup")
            for parent, name, child, identity in ancestors:
                if directory_id(os.stat(name, dir_fd=parent, follow_symlinks=False)) != identity:
                    raise OSError("the parent folder changed after backup")
                _check_project_marker(child)

        fd = root_fd
        key = ""
        for part in relative.split("/")[:-1]:
            key = f"{key}/{part}" if key else part
            expected = live.directories.get(key)
            created = False
            try:
                child = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if expected is not None or not create:
                    raise OSError("the parent folder changed after backup") from None
                check()
                os.mkdir(part, dir_fd=fd)
                child = os.open(part, flags, dir_fd=fd)
                created = True
            except OSError as error:
                if error.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise OSError("a link or file is in the way") from error
                raise
            opened.callback(os.close, child)
            identity = directory_id(os.fstat(child))
            if identity in live.excluded:
                raise OSError("a folder is excluded from restores")
            if identity in live.other_games:
                raise OSError("now part of another game")
            if expected is not None and identity != expected:
                raise OSError("the parent folder changed after backup")
            if expected is None and not created and identity not in live.directories.values():
                raise OSError("a parent folder appeared after backup")
            live.directories[key] = identity
            ancestors.append((fd, part, child, identity))
            fd = child
        yield fd, check


def _check_live(fd: int, name: str, backed_up: tuple[FileStamp, Digest] | None) -> None:
    """Check both identity and bytes, including when the original file was replaced with identical content."""
    if backed_up is None:
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        if stat.S_ISLNK(info.st_mode):
            raise OSError("a link is in the way")
        raise OSError("a file appeared after backup")

    stamp, digest = backed_up
    try:
        if file_digest(name, digest[0], dir_fd=fd, expected_stamp=stamp) == digest:
            return
    except OSError as error:
        raise OSError("the live file changed or could not be verified after backup") from error
    raise OSError("the live file changed after backup")


def _put_file(fd, check, name, source, expected, backed_up) -> None:
    check()
    partial = f".{uuid4().hex}.hr-restore"
    handle = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
    try:
        with os.fdopen(handle, "wb") as writer:
            if file_digest(source, expected[0], writer) != expected:
                raise OSError("the saved file changed during the restore")
        _check_live(fd, name, backed_up)
        check()
        if backed_up is None:
            # Install a new file only while the name is still free, including alternate spellings.
            os.link(partial, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        else:
            os.replace(partial, name, src_dir_fd=fd, dst_dir_fd=fd)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(partial, dir_fd=fd)


def _remove_empty_parents(root: Path, relative: str, live: LiveTree) -> None:
    folder = relative.rpartition("/")[0]
    while folder:
        try:
            with _parent(root, folder, live) as (fd, check):
                name = folder.rsplit("/", 1)[-1]
                if directory_id(os.stat(name, dir_fd=fd, follow_symlinks=False)) != live.directories.get(folder):
                    return
                check()
                os.rmdir(name, dir_fd=fd)
        except OSError:
            return
        live.directories.pop(folder)
        folder = folder.rpartition("/")[0]


def _restore_files(
    root: Path, wanted: dict[str, Path], digests: dict[str, Digest], live: LiveTree, *, excluded_top: frozenset[str]
) -> tuple[int, int, list[str]]:
    removed = changed = 0
    problems = []
    for relative in sorted(live.files.keys() - wanted.keys()):
        try:
            with _parent(root, relative, live) as (fd, check):
                name = relative.rsplit("/", 1)[-1]
                _check_live(fd, name, live.files[relative])
                check()
                os.unlink(name, dir_fd=fd)
                removed += 1
        except OSError as error:
            problems.append(f"{relative}: {error.strerror or error}")
            continue
        _remove_empty_parents(root, relative, live)

    for relative, source in sorted(wanted.items()):
        if "/" in relative and relative.split("/", 1)[0] in excluded_top:
            continue  # older snapshots can contain files that are now excluded
        expected = digests[relative]
        backed_up = live.files.get(relative)
        try:
            with _parent(root, relative, live, create=True) as (fd, check):
                name = relative.rsplit("/", 1)[-1]
                if backed_up is not None and backed_up[1] == expected:
                    _check_live(fd, name, backed_up)
                else:
                    _put_file(fd, check, name, source, expected, backed_up)
                    changed += 1
        except OSError as error:
            problems.append(f"{relative}: {error.strerror or error}")
    return changed, removed, problems
