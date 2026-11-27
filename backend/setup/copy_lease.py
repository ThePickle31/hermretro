"""A prepared engine copy's lease: a lock file beside the copy (``engine-<name>.lease``) that every worker running in it
holds shared for as long as it runs. The engine process inherits the descriptor (EngineProcess's ``keep_fds``) and its
launcher passes it on to the server (``HERMRETRO_COPY_LEASE_FD``), so a broker killed before its workers leaves them
holding it. Removing or replacing a copy takes the lease exclusively first, and leaves alone a copy whose lease is held:
no worker loses its engine's files.

A copy is published with its lease file. One without was made before leases: workers of that code hold none, so it
counts as in use unless the caller knows that no worker runs (Setup's removal, with the broker stopped). Stdlib only."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# The environment variable naming the lease's descriptor in the engine's launcher (engine/scripts/start-mcp.mjs).
DESCRIPTOR_VARIABLE = "HERMRETRO_COPY_LEASE_FD"
_TRIES = 3  # a lease file removed and made again while a worker waited for it is opened again, this often


def path_for(copy: Path) -> Path:
    return copy.with_name(copy.name + ".lease")


def _open(copy: Path, *, create: bool) -> int:
    return os.open(path_for(copy), os.O_RDWR | os.O_CLOEXEC | (os.O_CREAT if create else 0), 0o600)


def create(copy: Path) -> None:
    """The lease file of a copy being published, so that its workers' leases are seen from the start."""
    os.close(_open(copy, create=True))


def _current(descriptor: int, copy: Path) -> bool:
    """Whether the locked file is still copy's lease file and the copy is still there."""
    try:
        return os.fstat(descriptor).st_ino == os.stat(path_for(copy)).st_ino and copy.is_dir()
    except FileNotFoundError:
        return False


def hold(copy: Path) -> int:
    """A descriptor holding copy's lease shared, for the worker about to start in it to inherit; the caller closes its
    own once the worker runs. Waits while a removal or a replacement holds the lease. FileNotFoundError when the copy
    went meanwhile (choose again)."""
    for _ in range(_TRIES):
        descriptor = _open(copy, create=True)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            if _current(descriptor, copy):
                return descriptor
        except BaseException:
            os.close(descriptor)
            raise
        os.close(descriptor)  # removed (and its lease with it) while this waited
        if not copy.is_dir():
            break
    raise FileNotFoundError(f"the engine copy {copy} went while a worker was starting in it")


@contextmanager
def unused(copy: Path, *, unleased_is_unused: bool = False) -> Iterator[bool]:
    """Whether no worker runs in copy, holding its lease exclusively meanwhile so that none starts in it. A copy not
    there yet is unused; one without a lease file counts as in use unless ``unleased_is_unused``."""
    try:
        descriptor = _open(copy, create=unleased_is_unused or not copy.exists())
    except FileNotFoundError:
        yield False
        return
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            yield True
    finally:
        os.close(descriptor)
