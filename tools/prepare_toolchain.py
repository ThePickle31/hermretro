"""Install the game toolchain the way the hermretro page does (the broker's install), and wait for it.

    python tools/prepare_toolchain.py          # into the hermretro home (HERMRETRO_HOME, else ~/.hermes/hermretro)

For CI and fresh checkouts that need the toolchain for `python tools/check.py acceptance`. Downloads about
700 MB the first time (pinned, every archive checked against its SHA-256); does nothing when it is already
installed. Touches no hardware. Exits non-zero, with the reason, when the install fails.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapter import client, paths  # noqa: E402

LIMIT_SECONDS = 1500


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
        while True:
            status = broker.request({"op": "install_status"})
            install = status.get("install") or {}
            state = install.get("state")
            line = f"{state} {round(100 * (install.get('fraction') or 0))}% {install.get('current') or ''}".strip()
            if line != last:
                print(f"{time.monotonic() - began:6.0f} s  {line}", flush=True)
                last = line
            if state in ("done", "failed", "idle") and time.monotonic() - began > 2:
                break
            if time.monotonic() - began > LIMIT_SECONDS:
                print("install did not finish in time", file=sys.stderr)
                return 1
            time.sleep(5)
        if state != "done":
            print("install failed: " + json.dumps(install)[:1500], file=sys.stderr)
            return 1
        return 0
    finally:
        broker.request({"op": "shutdown", "force": True})
        broker.close()


if __name__ == "__main__":
    sys.exit(main())
