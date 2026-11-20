"""Print what a running hermretro broker says about itself, without ever starting one.

    python tools/debug/broker_stats.py                       # the `stats` answer, plus each worker's processes
    python tools/debug/broker_stats.py --activity hermretro <chat or session id>   # also one chat's `activity`

Connects to the broker of this user (its run folder: `backend/system/paths.py` `default_runtime_dir()`, moved by
`HERMRETRO_RUNTIME_DIR`) and sends only read-only operations: `stats` (lanes, their engine worker pids, in-flight
calls, writer leases) and, with `--activity`, the page's `activity` for one chat (memory only: no engine call, no
worker start). Each live engine worker runs in its own process group (`start_new_session=True` in
`backend/broker/engine.py`, so its group id is its pid); the processes of that group are listed from `ps`, which
reads the same on Linux and macOS. Exits 2 when no broker is running; it never creates the run folder.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

NO_BROKER = 2


def group_members(pgid: int, ps_output: str | None = None) -> list[dict]:
    """The processes whose process group is ``pgid``: pid, group, elapsed time and command line."""
    if ps_output is None:
        try:
            ps_output = subprocess.run(
                ["ps", "-A", "-o", "pid=,pgid=,etime=,command="],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError) as error:
            return [{"error": f"ps failed: {error}"}]
    members = []
    for line in ps_output.splitlines():
        fields = line.split(None, 3)
        if len(fields) < 3 or not (fields[0].isdigit() and fields[1].isdigit()):
            continue
        if int(fields[1]) == pgid:
            members.append(
                {
                    "pid": int(fields[0]),
                    "pgid": int(fields[1]),
                    "etime": fields[2],
                    "command": fields[3] if len(fields) > 3 else "",
                }
            )
    return members


def collect(connection: client.BrokerClient, activity: list[str] | None) -> dict:
    stats = connection.request({"op": "stats"})
    report: dict = {
        "run_folder": str(connection.state_dir),
        "hello": {key: connection.hello.get(key) for key in ("pid", "broker_generation", "plugin_root", "protocol")},
        "stats": stats,
        "engine_groups": {},
    }
    for lane in stats.get("lanes") or []:
        pid = lane.get("engine_pid")
        if isinstance(pid, int) and lane.get("alive"):
            report["engine_groups"][str(pid)] = group_members(pid)
    if activity:
        profile, *ids = activity
        report["activity"] = connection.request({"op": "activity", "profile": profile, "ids": ids})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show a running hermretro broker's stats (read-only).")
    parser.add_argument(
        "--activity",
        nargs="+",
        metavar=("PROFILE", "ID"),
        help="also print the activity of one chat: its profile, then its conversation or session ids",
    )
    args = parser.parse_args(argv)
    if args.activity is not None and len(args.activity) < 2:
        parser.error("--activity needs a profile and at least one chat or session id")
    state_dir = paths.default_runtime_dir()  # never runtime_dir(): that one creates the folder
    if not (state_dir / "broker.sock").exists():
        print(f"No hermretro broker is running (no {state_dir / 'broker.sock'}).", file=sys.stderr)
        return NO_BROKER
    connection, error = client.try_connect(state_dir)
    if connection is None:
        print(f"No hermretro broker answers at {state_dir}: {error}", file=sys.stderr)
        return NO_BROKER
    with connection:
        print(json.dumps(collect(connection, args.activity), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
