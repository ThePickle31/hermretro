"""Publish the staged studio profile without replacing someone else's directory."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import stat
import tempfile
from pathlib import Path

from ..hermes import api as hermes_api
from ..system.rename import rename_unoccupied


_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_GATEWAY_LOCK = "gateway.lock"
_RECEIPT = ".hermretro-publication.json"


def _entry(name: str, directory: int) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _same(left: os.stat_result | None, right: os.stat_result | None) -> bool:
    return left is right if left is None or right is None else os.path.samestat(left, right)


def _inode(info: os.stat_result) -> list[int]:
    return [info.st_dev, info.st_ino]


def require_profiles_directory(parent: Path, profiles: int, *, follow_symlinks: bool = False) -> None:
    try:
        info = parent.stat(follow_symlinks=follow_symlinks)
    except FileNotFoundError:
        info = None
    if not _same(info, os.fstat(profiles)):
        raise FileExistsError(f"The profiles directory {parent} changed.")


def profile_entry(target: Path, profiles: int) -> os.stat_result | None:
    require_profiles_directory(target.parent, profiles)
    return _entry(target.name, profiles)


def require_entry(target: Path, profiles: int, expected: os.stat_result | None) -> None:
    if not _same(profile_entry(target, profiles), expected):
        raise _occupied(target)


def _leftover(target: Path, entry: os.stat_result) -> bool:
    return stat.S_ISDIR(entry.st_mode) and not hermes_api.profile_has_identity(target)


def _occupied(target: Path) -> FileExistsError:
    return FileExistsError(f"The profile path {target} is occupied.")


def creation_candidate(target: Path, profiles: int, deleted: Tombstone) -> os.stat_result | None:
    """Only an absent destination or a tombstoned directory with no profile identity can be used."""
    entry = profile_entry(target, profiles)
    if entry is not None and (deleted.identity is None or not _leftover(target, entry)):
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
def _archive_leftover(target: Path, profiles: int, expected: os.stat_result, deleted: Tombstone):
    """Keep the old directory intact, including files a former writer may still have open."""
    deleted.check()
    with contextlib.ExitStack() as handles:
        old = handles.enter_context(open_profile(target, profiles, expected))
        if not _leftover(target, expected):
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
            require_entry(target, profiles, expected)
            deleted.check()
            if not _same(_entry(_GATEWAY_LOCK, old), lock_info) or not _leftover(target, expected):
                raise _occupied(target)
            rename_unoccupied(target.name, target.name, source_dir=profiles, target_dir=archive_fd)
            try:
                # A replacement at the source can win the race with rename. Keep it intact
                # and put it back only if the original name is still free.
                if (
                    not _same(_entry(target.name, archive_fd), expected)
                    or not _same(_entry(_GATEWAY_LOCK, old), lock_info)
                    or hermes_api.profile_has_identity(archive / target.name)
                ):
                    raise _occupied(target)
                deleted.check()
                yield
            except BaseException:
                with contextlib.suppress(OSError):
                    rename_unoccupied(target.name, target.name, source_dir=archive_fd, target_dir=profiles)
                raise


@contextlib.contextmanager
def profiles_directory(target: Path):
    """Resolve and pin the profiles parent without following the Studio entry."""
    target = target.parent.resolve(strict=True) / target.name
    profiles = os.open(target.parent, _DIRECTORY)
    try:
        yield target, profiles
    finally:
        os.close(profiles)


def lock_profiles(profiles: int) -> None:
    """Share one lock for publication and repair, released with the parent fd."""
    fcntl.flock(profiles, fcntl.LOCK_EX)


@contextlib.contextmanager
def open_profile(target: Path, profiles: int, expected: os.stat_result):
    try:
        directory = os.open(target.name, _DIRECTORY, dir_fd=profiles)
    except OSError as error:
        raise _occupied(target) from error
    try:
        if not _same(os.fstat(directory), expected):
            raise _occupied(target)
        require_entry(target, profiles, expected)
        yield directory
    finally:
        os.close(directory)


class Tombstone:
    """Snapshot Hermes's deletion marker without following links."""

    def __init__(self, target: Path, profiles: int):
        self.target = target
        self.profiles = profiles
        self.marker = hermes_api.profile_tombstone(target)
        with self._directory() as deleted:
            self.identity = self._identity(deleted)

    @contextlib.contextmanager
    def _directory(self):
        try:
            directory = os.open(self.marker.parent.name, _DIRECTORY, dir_fd=self.profiles)
        except FileNotFoundError:
            yield None
        else:
            try:
                yield directory
            finally:
                os.close(directory)

    def _identity(self, deleted: int | None) -> list[int] | None:
        if deleted is None or (marker := _entry(self.marker.name, deleted)) is None:
            return None
        if not stat.S_ISREG(marker.st_mode):
            raise _occupied(self.target)
        # Hermes may rewrite the same file when it deletes this name again.
        return [*_inode(os.fstat(deleted)), *_inode(marker), marker.st_ctime_ns, marker.st_mtime_ns, marker.st_size]

    def _receipt(self, profile: os.stat_result, receipt: os.stat_result) -> dict:
        return {"profile": _inode(profile), "tombstone": self.identity, "receipt": _inode(receipt)}

    def record(self, staging: Path) -> None:
        if self.identity is not None:
            with (staging / _RECEIPT).open("x", encoding="utf-8") as receipt:
                json.dump(self._receipt(staging.lstat(), os.fstat(receipt.fileno())), receipt)

    def matches_receipt(self, profile: os.stat_result) -> bool:
        if self.identity is None:
            return False
        try:
            with open_profile(self.target, self.profiles, profile) as directory:
                fd = os.open(_RECEIPT, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
                with os.fdopen(fd, "rb") as reader:
                    info = os.fstat(reader.fileno())
                    return (
                        stat.S_ISREG(info.st_mode)
                        and info.st_nlink == 1
                        and json.loads(reader.read(512)) == self._receipt(profile, info)
                    )
        except (OSError, ValueError):
            return False

    def _check(self, deleted: int | None) -> None:
        if (
            (deleted is not None and not _same(_entry(self.marker.parent.name, self.profiles), os.fstat(deleted)))
            or (deleted is None and _entry(self.marker.parent.name, self.profiles) is not None)
            or self._identity(deleted) != self.identity
        ):
            raise _occupied(self.target)

    def check(self) -> None:
        with self._directory() as deleted:
            self._check(deleted)

    def clear(self, profile: os.stat_result) -> None:
        """Make the exact published directory live, if its predecessor's marker is still there."""
        with self._directory() as deleted:
            require_entry(self.target, self.profiles, profile)
            self._check(deleted)
            if deleted is not None and self.identity is not None:
                os.unlink(self.marker.name, dir_fd=deleted)


def publish(staging: Path, target: Path, expected: os.stat_result | None, profiles: int, deleted: Tombstone) -> None:
    """Publish the prepared directory before making its name live in Hermes."""
    require_entry(target, profiles, expected)
    staged = staging.lstat()
    archive = (
        _archive_leftover(target, profiles, expected, deleted) if expected is not None else contextlib.nullcontext()
    )
    with archive:
        deleted.check()
        rename_unoccupied(staging.name, target.name, source_dir=profiles, target_dir=profiles)
    # A failure after the rename leaves the receipt in the published directory for the next setup.
    deleted.clear(staged)


def discard_generated_file(path: Path, parent: int, is_generated) -> None:
    """Discard only the generated file, keeping a replacement even if its name changes mid-move."""
    if not is_generated(path.name, parent):
        return
    with _holding_dir(path.parent, label="repair") as (_, held):
        try:
            rename_unoccupied(path.name, path.name, source_dir=parent, target_dir=held)
        except FileNotFoundError:
            return
        try:
            if is_generated(path.name, held):
                os.unlink(path.name, dir_fd=held)
                return
        finally:
            if _entry(path.name, held) is not None:
                with contextlib.suppress(FileExistsError):
                    rename_unoccupied(path.name, path.name, source_dir=held, target_dir=parent)
