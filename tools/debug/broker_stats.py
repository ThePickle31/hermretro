"""Print what a running hermretro broker says about itself, without ever starting one.

    python tools/debug/broker_stats.py                       # the `stats` answer, plus each worker's processes
    python tools/debug/broker_stats.py --activity hermretro <chat or session id>   # also one chat's `activity`
    python tools/debug/broker_stats.py --timeout 10          # wait up to 10 s per step (default 5)

Connects to the broker of this user (its run folder: `backend/system/paths.py` `default_runtime_dir()`, moved by
`HERMRETRO_RUNTIME_DIR`) and sends only read-only operations: `stats` (lanes, their engine worker pids, in-flight
calls, writer leases) and, with `--activity`, the page's `activity` for one chat (memory only: no engine call, no
worker start). For each live engine worker it lists the worker and every process descended from it, found by
walking parent pids in one `ps -A -o pid=,ppid=,pgid=,etime=,command=` snapshot (the same on Linux and macOS), so
the ROM and web compilers, which the engine starts in sessions of their own, are listed too; each line has its
pgid. The connect, the handshake and each request wait at most `--timeout` seconds. It never creates the run
folder. Exit codes: 0 printed, 2 no broker is running (or it refused the handshake), 3 a broker accepted the
connection but did not answer in time or closed it.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.broker import client  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

NO_BROKER = 2
NOT_ANSWERING = 3
DEFAULT_TIMEOUT = 5.0


class NotAnswering(Exception):
    """The broker accepted the connection but did not answer ``step`` in time, or closed the connection."""

    def __init__(self, state_dir: Path, step: str, timeout: float, closed: bool):
        socket_path = Path(state_dir) / "broker.sock"
        if closed:
            message = f"The hermretro broker at {socket_path} closed the connection before answering {step}"
        else:
            message = f"The hermretro broker at {socket_path} accepted but did not answer {step} within {timeout:g} s"
        super().__init__(message)


class TimedClient(client.BrokerClient):
    """``client.BrokerClient`` with a timeout on its socket from the connect on, for this tool only: the plugin's
    own clients keep no timeout of their own (a tool call may run for many minutes)."""

    def __init__(self, state_dir: Path, timeout: float):
        self.state_dir = Path(state_dir)
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        try:
            self.sock.connect(str(self.state_dir / "broker.sock"))
        except TimeoutError as error:
            self.sock.close()
            raise NotAnswering(self.state_dir, "the connect", timeout, closed=False) from error
        except OSError as error:
            self.sock.close()
            raise client.BrokerUnavailable(str(error)) from error
        self.reader = self.sock.makefile("rb")
        try:
            token = (self.state_dir / "broker.token").read_text()
            self.hello = self.ask({"op": "hello", "protocol": paths.PROTOCOL, "token": token}, "hello")
        except Exception:
            self.close()
            raise

    def ask(self, obj: dict, step: str) -> dict:
        """``request`` that names ``step`` when the broker does not answer, or answers with something not JSON."""
        try:
            answer = self.request(obj)
        except client.BrokerUnavailable as error:
            timed_out = isinstance(error.__cause__, TimeoutError)
            raise NotAnswering(self.state_dir, step, self.timeout, closed=not timed_out) from error
        except ValueError as error:  # not JSON
            raise NotAnswering(self.state_dir, step, self.timeout, closed=False) from error
        if not isinstance(answer, dict):
            raise NotAnswering(self.state_dir, step, self.timeout, closed=False)
        return answer


def process_table(ps_output: str | None = None) -> list[dict] | str:
    """One `ps` snapshot as rows of pid, ppid, pgid, elapsed time and command line, or the error text."""
    if ps_output is None:
        try:
            ps_output = subprocess.run(
                ["ps", "-A", "-o", "pid=,ppid=,pgid=,etime=,command="],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError) as error:
            return f"ps failed: {error}"
    rows = []
    for line in ps_output.splitlines():
        fields = line.split(None, 4)
        if len(fields) < 4 or not all(field.isdigit() for field in fields[:3]):
            continue
        rows.append(
            {
                "pid": int(fields[0]),
                "ppid": int(fields[1]),
                "pgid": int(fields[2]),
                "etime": fields[3],
                "command": fields[4] if len(fields) > 4 else "",
            }
        )
    return rows


def descendants(root: int, table: list[dict] | str) -> list[dict]:
    """``root`` and every process descended from it (whatever its session or group), parents before children."""
    if isinstance(table, str):
        return [{"error": table}]
    children: dict[int, list[dict]] = {}
    for row in table:
        children.setdefault(row["ppid"], []).append(row)
    found = [row for row in table if row["pid"] == root]
    seen = {root}
    index = 0
    while index < len(found):
        for child in children.get(found[index]["pid"], []):
            if child["pid"] not in seen:  # a pid reused mid-snapshot cannot loop
                seen.add(child["pid"])
                found.append(child)
        index += 1
    return found


def collect(connection: TimedClient, activity: list[str] | None, ps_output: str | None = None) -> dict:
    stats = connection.ask({"op": "stats"}, "stats")
    report: dict = {
        "run_folder": str(connection.state_dir),
        "hello": {key: connection.hello.get(key) for key in ("pid", "broker_generation", "plugin_root", "protocol")},
        "stats": stats,
        "engine_processes": {},
    }
    lanes = [lane for lane in stats.get("lanes") or [] if isinstance(lane, dict)]
    live = [lane["engine_pid"] for lane in lanes if isinstance(lane.get("engine_pid"), int) and lane.get("alive")]
    if live:
        table = process_table(ps_output)
        for pid in live:
            report["engine_processes"][str(pid)] = descendants(pid, table)
    if activity:
        profile, *ids = activity
        report["activity"] = connection.ask({"op": "activity", "profile": profile, "ids": ids}, "activity")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show a running hermretro broker's stats (read-only).")
    parser.add_argument(
        "--activity",
        nargs="+",
        metavar=("PROFILE", "ID"),
        help="also print the activity of one chat: its profile, then its conversation or session ids",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"seconds to wait for the connect, the handshake and each answer (default {DEFAULT_TIMEOUT:g})",
    )
    args = parser.parse_args(argv)
    if args.activity is not None and len(args.activity) < 2:
        parser.error("--activity needs a profile and at least one chat or session id")
    if not args.timeout > 0:
        parser.error("--timeout must be more than 0")
    state_dir = paths.default_runtime_dir()  # never runtime_dir(): that one creates the folder
    if not (state_dir / "broker.sock").exists():
        print(f"No hermretro broker is running (no {state_dir / 'broker.sock'}).", file=sys.stderr)
        return NO_BROKER
    try:
        connection = TimedClient(state_dir, args.timeout)
    except NotAnswering as error:
        print(f"{error}.", file=sys.stderr)
        return NOT_ANSWERING
    except (client.BrokerUnavailable, OSError) as error:  # refused (a stale socket), or no token
        print(f"No hermretro broker answers at {state_dir}: {error}", file=sys.stderr)
        return NO_BROKER
    with connection:
        if not connection.hello.get("ok"):
            print(f"The hermretro broker at {state_dir} refused the handshake: {connection.hello}", file=sys.stderr)
            return NO_BROKER
        try:
            report = collect(connection, args.activity)
        except NotAnswering as error:
            print(f"{error}.", file=sys.stderr)
            return NOT_ANSWERING
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
