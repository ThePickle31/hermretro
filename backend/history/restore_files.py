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
    # Stamp at backup → most recent stamp after restore removed a name for that inode.
    unlinked: dict[FileStamp, FileStamp] = field(default_factory=dict)
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
    with _open_file(path, dir_fd) as handle:
        measured, _ = _digest_open_file(handle, path, limit, writer, dir_fd, expected_stamp)
    return measured


def _open_file(path, dir_fd):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    return os.fdopen(fd, "rb")


def _digest_open_file(
    handle, path, limit, writer, dir_fd, expected_stamp, *, check=None
) -> tuple[Digest, os.stat_result]:
    digest = hashlib.sha256()
    size = 0
    fd = handle.fileno()
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
    if check is not None:
        check(scan=False)
    info = os.fstat(fd)
    if file_stamp(info) != stamp or file_stamp(os.stat(path, dir_fd=dir_fd, follow_symlinks=False)) != stamp:
        raise OSError(f"{path} changed during the snapshot operation")
    return (size, digest.hexdigest()), info


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

        def check(*, scan=True):
            if scan:
                for _, _, child, _ in ancestors:
                    _check_project_marker(child)
            if directory_id(root.lstat()) != root_id or Path(os.path.realpath(root, strict=True)) != root:
                raise OSError("the project folder changed after backup")
            for parent, name, _, identity in ancestors:
                if directory_id(os.stat(name, dir_fd=parent, follow_symlinks=False)) != identity:
                    raise OSError("the parent folder changed after backup")

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


def _expect_absent(fd: int, name: str) -> None:
    try:
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode):
        raise OSError("a link is in the way")
    raise OSError("a file appeared after backup")


@contextmanager
def _check_live(
    fd: int, name: str, backed_up: tuple[FileStamp, Digest] | None, live: LiveTree, *, check=None, unlink=False
):
    """Validate the current path and hold its inode open through a replacement or deletion."""
    if check is not None:
        check()
    if backed_up is None:
        _expect_absent(fd, name)
        yield
        return

    stamp, digest = backed_up
    with ExitStack() as opened:
        try:
            handle = opened.enter_context(_open_file(name, fd))
            expected = live.unlinked.get(stamp, stamp)
            measured, before = _digest_open_file(handle, name, digest[0], None, fd, expected, check=check)
        except OSError as error:
            raise OSError("the live file changed or could not be verified after backup") from error
        if measured != digest:
            raise OSError("the live file changed after backup")

        yield

        if unlink and before.st_nlink > 1:
            after = os.fstat(handle.fileno())
            updated = file_stamp(after)
            # Unlink and replace remove one name from the verified inode. A remaining name must still
            # match this stamp and the backed-up bytes when restore reaches it.
            if (
                after.st_nlink == before.st_nlink - 1
                and (after.st_mode, after.st_uid, after.st_gid) == (before.st_mode, before.st_uid, before.st_gid)
                and updated[:-1] == expected[:-1]
            ):
                live.unlinked[stamp] = updated


def _put_file(fd, check, name, source, expected, backed_up, live) -> None:
    check()
    partial = f".{uuid4().hex}.hr-restore"
    handle = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
    try:
        with os.fdopen(handle, "wb") as writer:
            if file_digest(source, expected[0], writer) != expected:
                raise OSError("the saved file changed during the restore")
        with _check_live(fd, name, backed_up, live, check=check, unlink=True):
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
                check()
                if directory_id(os.stat(name, dir_fd=fd, follow_symlinks=False)) != live.directories.get(folder):
                    return
                os.rmdir(name, dir_fd=fd)
        except OSError:
            return
        live.directories.pop(folder)
        folder = folder.rpartition("/")[0]


def _restore_files(
    root: Path, wanted: dict[str, Path], digests: dict[str, Digest], live: LiveTree
) -> tuple[int, int, list[str]]:
    removed = changed = 0
    problems = []
    for relative in sorted(live.files.keys() - wanted.keys()):
        try:
            with _parent(root, relative, live) as (fd, check):
                name = relative.rsplit("/", 1)[-1]
                with _check_live(fd, name, live.files[relative], live, check=check, unlink=True):
                    os.unlink(name, dir_fd=fd)
                removed += 1
        except OSError as error:
            problems.append(f"{relative}: {error.strerror or error}")
            continue
        _remove_empty_parents(root, relative, live)

    for relative, source in sorted(wanted.items()):
        expected = digests[relative]
        backed_up = live.files.get(relative)
        try:
            with _parent(root, relative, live, create=True) as (fd, check):
                name = relative.rsplit("/", 1)[-1]
                if backed_up is not None and backed_up[1] == expected:
                    with _check_live(fd, name, backed_up, live):
                        pass
                else:
                    _put_file(fd, check, name, source, expected, backed_up, live)
                    changed += 1
        except OSError as error:
            problems.append(f"{relative}: {error.strerror or error}")
    return changed, removed, problems
