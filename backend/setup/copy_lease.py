"""A prepared engine copy's lease: a lock file beside the copy (``engine-<name>.lease``) that every worker running in it
holds shared for as long as it runs. The engine process inherits the descriptor (EngineProcess's ``keep_fds``), so a
broker killed before its workers leaves them holding it. Removing or replacing a copy takes the lease exclusively
first, and leaves alone a copy whose lease is held: no worker loses its engine's files. Stdlib only."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def path_for(copy: Path) -> Path:
    return copy.with_name(copy.name + ".lease")


def _open(copy: Path) -> int:
    return os.open(path_for(copy), os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)


def hold(copy: Path) -> int:
    """A descriptor holding copy's lease shared, for the worker about to start in it to inherit; the caller closes its
    own once the worker runs. Waits while a removal or a replacement holds the lease."""
    descriptor = _open(copy)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


@contextmanager
def unused(copy: Path) -> Iterator[bool]:
    """Whether no worker runs in copy, holding its lease exclusively meanwhile so that none starts in it."""
    descriptor = _open(copy)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            yield True
    finally:
        os.close(descriptor)
