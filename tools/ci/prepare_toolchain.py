"""Install the game toolchain the way the hermretro page does (the broker's install), and wait for it.

    HERMRETRO_DEPS_ROOT=<folder> python tools/ci/prepare_toolchain.py   # on a developer machine
    python tools/ci/prepare_toolchain.py                                # in GitHub Actions: the hermretro home

For CI and fresh checkouts that need the toolchain for `python tools/check.py acceptance`. Downloads about
700 MB the first time (pinned, every archive checked against its SHA-256); does nothing when it is already
installed. Touches no hardware. Exits non-zero, with the reason, when the install fails.

The install runs in a broker of its own, started in a new private folder and stopped at the end: a broker that is
already running (the one an installed hermretro's chats use) is never reused, replaced or stopped. Everything the
install writes (the toolchain, its journal, the prepared engine) lands in the destination. Outside GitHub Actions
that has to be named with HERMRETRO_DEPS_ROOT, then given to the acceptance run the same way: the default,
`<hermretro home>/.cache`, belongs to the installed plugin, whose page installs it.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import backend.hermes  # noqa: E402, F401 - tells backend.system how to ask Hermes for its home
from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

LIMIT_SECONDS = 1200
STALL_SECONDS = 420  # no new bytes downloaded and no growth on disk (npm unpacking counts as progress)
# Where the private broker's folder is made: /tmp, since a macOS TMPDIR is too long for the broker's Unix socket.
STATE_PARENT = Path("/tmp")


def folder_bytes(folder: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def refusal(environ) -> str | None:
    """Why this run must not start, or None. GitHub Actions runs on a throwaway machine, so its default home is
    the run's own; anywhere else the destination must be named."""
    if environ.get("GITHUB_ACTIONS") == "true" or environ.get("HERMRETRO_DEPS_ROOT"):
        return None
    return (
        f"refusing to install into {paths.DEPS_ROOT}: outside CI the toolchain goes in a folder you name, "
        "never the installed hermretro's own (its page installs that one)\n"
        "FIX: HERMRETRO_DEPS_ROOT=<folder> python tools/ci/prepare_toolchain.py, "
        "then HERMRETRO_DEPS_ROOT=<folder> python tools/check.py acceptance"
    )


def wait_for_install(broker) -> int:
    started = broker.request({"op": "install_start"})
    if not started.get("ok"):
        print("install did not start: " + json.dumps(started)[:600], file=sys.stderr)
        return 1
    began = time.monotonic()
    last = None
    progress, moved = None, time.monotonic()
    while True:
        status = broker.request({"op": "install_status"})
        install = status.get("install") or {}
        state = install.get("state")
        line = f"{state} {round(100 * (install.get('fraction') or 0))}% {install.get('current') or ''}".strip()
        if line != last:
            print(f"{time.monotonic() - began:6.0f} s  {line}", flush=True)
            last = line
        if state in ("done", "failed"):
            break
        now = (
            install.get("fraction"),
            install.get("downloaded_bytes"),
            install.get("current"),
            folder_bytes(paths.setup_root()) // 1_000_000,
        )
        if now != progress:
            progress, moved = now, time.monotonic()
        elif time.monotonic() - moved > STALL_SECONDS:
            print(f"install made no progress for {STALL_SECONDS} s: " + json.dumps(install)[:1500], file=sys.stderr)
            return 1
        if time.monotonic() - began > LIMIT_SECONDS:
            print("install did not finish in time", file=sys.stderr)
            return 1
        time.sleep(5)
    if state != "done":
        print("install failed: " + json.dumps(install)[:1500], file=sys.stderr)
        return 1
    return 0


def stop(broker) -> bool:
    """Ask this run's own broker to stop; whether it agreed. Never forced: one still installing (a run that gave
    up on it) refuses, finishes and exits by itself once idle."""
    try:
        return client.request_shutdown(broker)
    except Exception:  # noqa: BLE001 - the broker already went away; keep the real result
        return False
    finally:
        broker.close()


def main() -> int:
    reason = refusal(os.environ)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    if os.environ.get("HERMRETRO_DEPS_ROOT"):
        # Absolute, as this process resolved it: the broker runs from the plugin folder and reads it again.
        os.environ["HERMRETRO_DEPS_ROOT"] = str(paths.DEPS_ROOT)
    print(f"toolchain: {paths.setup_root()}", flush=True)
    state = Path(tempfile.mkdtemp(prefix="hermretro-prepare-", dir=STATE_PARENT))
    broker, code = None, 1
    try:
        broker = client.ensure_broker(state, wait=60)
        code = wait_for_install(broker)
    finally:
        if broker is not None and stop(broker) and code == 0:
            shutil.rmtree(state, ignore_errors=True)
        else:
            print(f"the broker's trace and logs: {state}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
