"""Stopping hermretro's broker so nothing runs from the folders Setup is about to delete: its election lock
(`broker_lock`), and `broker_stopped`, which asks the broker to stop and then holds that lock. Used by Setup's
"Remove downloaded tools" and by the factory reset."""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

from ..broker import BrokerNotRunning, BrokerRestarting, BrokerUnavailable, request_shutdown
from ..hermes import host
from ..system import paths
from . import recovery

BROKER_STOP_WAIT = 15.0  # seconds a stopping broker gets to close its workers

BUSY = "A game is open in a chat or an install is running. Close those chats (or wait for the install), then try again."
WORKER_LEFT = (
    "The last toolchain installer did not confirm it stopped, so the tools folder may still be in use. Quit and "
    "reopen Hermes, then try again."
)


@contextlib.contextmanager
def broker_lock(run: Path, seconds: float | None = None):
    """Hold the broker election lock, waiting for a stopping broker to let go of it. Yields False on timeout."""
    import fcntl

    with open(run / "broker.lock", "a+") as handle:
        deadline = time.monotonic() + (BROKER_STOP_WAIT if seconds is None else seconds)
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    yield False
                    return
                time.sleep(0.1)
        try:
            time.sleep(0.5)  # workers exit when the broker's pipe closes; give them a moment
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextlib.contextmanager
def broker_stopped(*, replace: bool = False):
    """Stop the broker (never start one) and hold its election lock: while it is held, a broker another call starts
    loses the election and exits, so nothing runs from hermretro's folders. Yields None once that holds, else the
    refusal to answer (``code`` BUSY or WORKER_STILL_RUNNING). ``replace`` lets the broker's idle workers close with it
    (a plain stop is refused while any worker lives). Raises BrokerUnavailable when the broker cannot be asked."""
    run = paths.runtime_dir()
    client, error = host.try_connect(run)
    if error is not None and not isinstance(error, BrokerNotRunning):
        raise BrokerUnavailable(str(error)) from error
    if client is not None:
        with client:
            try:
                stopping = request_shutdown(client, replace=replace)
            except BrokerRestarting:
                stopping = False  # a call is still running
            if not stopping:
                yield {"ok": False, "code": "BUSY", "error": BUSY}
                return
    with broker_lock(run) as held:
        if not held:
            yield {"ok": False, "code": "BUSY", "error": BUSY}
        elif recovery.worker_left(recovery.read_journal()):
            # The broker exited, but the installer worker it could not close may still use the folder.
            yield {"ok": False, "code": "WORKER_STILL_RUNNING", "error": WORKER_LEFT}
        else:
            yield None
