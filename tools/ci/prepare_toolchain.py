"""Install the game toolchain the way the hermretro page does (the broker's install), and wait for it.

    python tools/ci/prepare_toolchain.py          # into the hermretro home (HERMRETRO_HOME, else ~/.hermes/hermretro)

For CI and fresh checkouts that need the toolchain for `python tools/check.py acceptance`. Downloads about
700 MB the first time (pinned, every archive checked against its SHA-256); does nothing when it is already
installed. Touches no hardware. Exits non-zero, with the reason, when the install fails.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.broker import client  # noqa: E402
from backend.system import paths  # noqa: E402

LIMIT_SECONDS = 1200
STALL_SECONDS = 420   # no new bytes downloaded and no growth on disk (npm unpacking counts as progress)


def folder_bytes(folder: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def main() -> int:
    print(f"toolchain: {paths.setup_root()}", flush=True)
    broker = client.ensure_broker(wait=60)
    try:
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
            now = (install.get("fraction"), install.get("downloaded_bytes"), install.get("current"),
                   folder_bytes(paths.setup_root()) // 1_000_000)
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
    finally:
        # Never forced: from a checkout a Hermes profile loads, this may be the live broker that chats use; a busy
        # broker refuses a plain shutdown and keeps running, an idle one exits.
        try:
            broker.request({"op": "shutdown"})
        except Exception:  # noqa: BLE001 - the broker already went away; keep the real result
            pass
        broker.close()


if __name__ == "__main__":
    sys.exit(main())
