"""Publish the staged studio profile without replacing someone else's directory."""

from __future__ import annotations

import contextlib
import fcntl
import os
import stat
import tempfile
from pathlib import Path

from ..hermes import api as hermes_api
from ..system.rename import rename_unoccupied


_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_GATEWAY_LOCK = "gateway.lock"


def _entry(name: str, directory: int) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _same(left: os.stat_result | None, right: os.stat_result | None) -> bool:
    return left is right if left is None or right is None else os.path.samestat(left, right)


def _leftover(target: Path, entry: os.stat_result) -> bool:
    return (
        stat.S_ISDIR(entry.st_mode)
        and hermes_api.profile_is_deleted(target)
        and not hermes_api.profile_has_identity(target)
    )


def _occupied(target: Path) -> FileExistsError:
    return FileExistsError(f"The profile path {target} is occupied.")


def creation_candidate(target: Path) -> os.stat_result | None:
    """Only an absent destination or a tombstoned directory with no profile identity can be used."""
    try:
        entry = target.lstat()
    except FileNotFoundError:
        return None
    if not _leftover(target, entry):
        raise _occupied(target)
    return entry


@contextlib.contextmanager
def _holding_dir(target: Path, *, label: str):
    directory = Path(tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}-{label}-"))
    try:
        fd = os.open(directory, _DIRECTORY)
        try:
            yield directory, fd
        finally:
            os.close(fd)
    finally:
        with contextlib.suppress(OSError):
            directory.rmdir()  # Never remove any directory tree moved here.


@contextlib.contextmanager
def _archive_leftover(target: Path, profiles: int, expected: os.stat_result):
    """Keep the old directory intact, including files a former writer may still have open."""
    with contextlib.ExitStack() as handles:
        try:
            old = os.open(target.name, _DIRECTORY, dir_fd=profiles)
        except OSError as error:
            raise _occupied(target) from error
        handles.callback(os.close, old)
        if not _same(os.fstat(old), expected) or not _leftover(target, expected):
            raise _occupied(target)

        # Hermes checks this same flock. Hold it through publication and pin its inode with
        # the directory fd instead of rewriting the native lock record or probing and releasing.
        try:
            lock = os.open(_GATEWAY_LOCK, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=old)
        except OSError as error:
            raise _occupied(target) from error
        handles.callback(os.close, lock)
        lock_info = os.fstat(lock)
        if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_nlink != 1:
            raise _occupied(target)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise _occupied(target) from error

        with _holding_dir(target, label="deleted") as (archive, archive_fd):
            if (
                not _same(_entry(target.name, profiles), expected)
                or not _same(_entry(_GATEWAY_LOCK, old), lock_info)
                or not _leftover(target, expected)
            ):
                raise _occupied(target)
            rename_unoccupied(target.name, target.name, source_dir=profiles, target_dir=archive_fd)
            try:
                # A replacement at the source can win the race with rename. Keep it intact
                # and put it back only if the original name is still free.
                if (
                    not _same(_entry(target.name, archive_fd), expected)
                    or not _same(_entry(_GATEWAY_LOCK, old), lock_info)
                    or hermes_api.profile_has_identity(archive / target.name)
                    or not hermes_api.profile_is_deleted(target)
                ):
                    raise _occupied(target)
                yield
            except BaseException:
                with contextlib.suppress(OSError):
                    rename_unoccupied(target.name, target.name, source_dir=archive_fd, target_dir=profiles)
                raise


@contextlib.contextmanager
def publication_lock(target: Path):
    """Serialize creates by plugin hosts sharing the profiles directory."""
    profiles = os.open(target.parent, _DIRECTORY)
    try:
        fcntl.flock(profiles, fcntl.LOCK_EX)
        yield profiles
    finally:
        os.close(profiles)


@contextlib.contextmanager
def tombstone(target: Path, profiles: int):
    """Clear only the deletion marker that was present when this create started."""
    marker = hermes_api.profile_tombstone(target)
    try:
        deleted = os.open(marker.parent.name, _DIRECTORY, dir_fd=profiles)
    except FileNotFoundError:
        deleted = None
    try:
        before = _entry(marker.name, deleted) if deleted is not None else None
        if before is not None and not stat.S_ISREG(before.st_mode):
            raise _occupied(target)

        def clear():
            if deleted is None:
                if hermes_api.profile_is_deleted(target):
                    raise _occupied(target)
                return
            after = _entry(marker.name, deleted)
            if (
                not _same(_entry(marker.parent.name, profiles), os.fstat(deleted))
                or not _same(before, after)
                or (before is not None and before.st_ctime_ns != after.st_ctime_ns)
            ):
                raise _occupied(target)
            if before is not None:
                os.unlink(marker.name, dir_fd=deleted)

        yield clear
    finally:
        if deleted is not None:
            os.close(deleted)


def publish(staging: Path, target: Path, expected: os.stat_result | None, profiles: int, clear_tombstone) -> None:
    """Publish the prepared directory before making its name live in Hermes."""
    if not _same(_entry(target.name, profiles), expected):
        raise _occupied(target)
    staged = staging.lstat()
    archive = _archive_leftover(target, profiles, expected) if expected is not None else contextlib.nullcontext()
    with archive:
        rename_unoccupied(staging.name, target.name, source_dir=profiles, target_dir=profiles)
        try:
            if not _same(target.lstat(), staged):
                raise _occupied(target)
            clear_tombstone()
        except BaseException:
            if _same(_entry(target.name, profiles), staged):
                # A replacement could still win the source rename. Park it in a directory
                # that is never recursively cleaned, rather than in the staging directory.
                with _holding_dir(target, label="unpublished") as (_, archive_fd):
                    rename_unoccupied(target.name, target.name, source_dir=profiles, target_dir=archive_fd)
            raise


def discard_generated_file(path: Path, is_generated) -> None:
    """Discard only the generated file, keeping a replacement even if its name changes mid-move."""
    if not is_generated(path):
        return
    parent = os.open(path.parent, _DIRECTORY)
    try:
        with _holding_dir(path, label="repair") as (holding, held):
            try:
                rename_unoccupied(path.name, path.name, source_dir=parent, target_dir=held)
            except FileNotFoundError:
                return
            try:
                if is_generated(holding / path.name):
                    os.unlink(path.name, dir_fd=held)
                    return
            finally:
                if _entry(path.name, held) is not None:
                    with contextlib.suppress(FileExistsError):
                        rename_unoccupied(path.name, path.name, source_dir=held, target_dir=parent)
    finally:
        os.close(parent)
