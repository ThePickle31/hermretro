"""Worker restart, broker crash, recording-lease recovery and clean shutdown."""

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from unittest import mock

from backend.broker.client import ensure_broker
from tests.acceptance.fixture import OWNER_A, alive, diff, fallback_dirs, snapshot, structured, wait_gone


def session_processes(leader: int) -> list[dict]:
    """Processes in the group a worker or the broker leads (each starts in its own session, so its group)."""
    listing = subprocess.run(["ps", "-A", "-o", "pid=,pgid=,rss=,comm="], capture_output=True, text=True).stdout
    found = []
    for line in listing.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[1] == str(leader):
            found.append({"pid": int(parts[0]), "comm": Path(parts[3]).name, "rss_kb": int(parts[2])})
    return found


def check_worker_restart(suite, client_a):
    a_pid = client_a.call(OWNER_A, "session_status")["lane"]["engine_pid"]
    os.kill(a_pid, signal.SIGKILL)
    time.sleep(1.0)
    after_crash = client_a.call(OWNER_A, "session_status")
    suite.check(
        "R0",
        "A crashed worker is replaced: selection restored, emulator reported as reset",
        after_crash.get("ok")
        and after_crash["lane"]["engine_pid"] != a_pid
        and after_crash["lane"]["engine_generation"] == 2
        and structured(after_crash).get("projectRoot") == str(suite.project_a)
        and structured(after_crash).get("emulatorActive") is False
        and "restarted" in (after_crash.get("notice") or ""),
        notice=after_crash.get("notice"),
    )


def check_broker_crash(suite, control, broker_pid):
    stats = control.request({"op": "stats"})
    cost = []
    for lane in stats["lanes"]:
        procs = session_processes(lane["engine_pid"]) if lane["engine_pid"] else []
        cost.append(
            {
                "owner_key": lane["owner_key"],
                "processes": procs,
                "total_rss_mb": round(sum(p["rss_kb"] for p in procs) / 1024, 1),
            }
        )
    suite.observations["worker_cost"] = cost
    trace = [json.loads(line) for line in (suite.state / "trace.jsonl").read_text().splitlines()]
    suite.observations["worker_ready_seconds"] = [
        r["ready_seconds"] for r in trace if r.get("event") == "worker_started"
    ]
    suite.observations["broker_rss_mb"] = round(
        next((p["rss_kb"] for p in session_processes(broker_pid) if p["pid"] == broker_pid), 0) / 1024, 1
    )

    worker_pids = sorted({p["pid"] for lane in cost for p in lane["processes"]})
    private_temp = fallback_dirs(broker_pid)
    suite.check(
        "T1",
        "Workers of a broker with a deep TMPDIR get short private temp folders of their own",
        bool(private_temp)
        and all(len(os.fsencode(p)) <= 64 and p.stat().st_mode & 0o777 == 0o700 for p in private_temp),
        folders=[str(p) for p in private_temp],
    )
    os.kill(broker_pid, signal.SIGKILL)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and any(alive(p) for p in worker_pids + [broker_pid]):
        time.sleep(0.2)
    survivors = [p for p in worker_pids if alive(p)]
    suite.check(
        "R1",
        "After SIGKILL of the broker no engine, compiler or emulator process is orphaned",
        not survivors and not alive(broker_pid),
        killed_broker_pid=broker_pid,
        worker_processes=len(worker_pids),
        survivors=survivors,
    )


def check_restarted_brokers(suite, broker_pid, rom_a):
    snap_before_restart = snapshot(suite.project_a)
    client = ensure_broker(suite.state)
    suite.brokers.add(client.hello["pid"])
    fresh_status = client.call(OWNER_A, "session_status")
    reselect = client.call(OWNER_A, "project_select", {"projectPath": str(suite.project_a / "project.gbsproj")})
    names = [v.get("name") for v in structured(client.call(OWNER_A, "variable_inspect")).get("variables", [])]
    suite.check(
        "R2",
        "A new broker reports lost process-local state honestly; native source is intact and reselectable",
        client.hello["pid"] != broker_pid
        and structured(fresh_status).get("selected") is False
        and structured(fresh_status).get("emulatorActive") is False
        and reselect.get("ok")
        and not reselect["result"].get("isError")
        and diff(snap_before_restart, snapshot(suite.project_a)) == []
        and {"S01 marker A", "S01 child leased", "S01 A second edit", "S01 C after handoff"} <= set(names),
        new_broker_pid=client.hello["pid"],
        variables=names,
    )
    # The killed emulator never releases its recording lease; the next broker must clear it, not refuse.
    client.call(OWNER_A, "emulator_run", {"romPath": rom_a})
    lease_path = suite.project_a / "artifacts" / ".recording-access" / "lease.json"
    held_by = json.loads(lease_path.read_text())["pid"] if lease_path.exists() else None
    killed_broker = client.hello["pid"]
    groups = [lane["engine_pid"] for lane in client.request({"op": "stats"})["lanes"] if lane["engine_pid"]]
    client.close()
    os.kill(killed_broker, signal.SIGKILL)
    for group in groups:
        try:
            os.killpg(group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and (alive(killed_broker) or (held_by and alive(held_by))):
        time.sleep(0.1)
    orphaned = lease_path.exists() and held_by is not None and not alive(held_by)
    with mock.patch.dict(
        os.environ, {"TMPDIR": str(suite.compiler_temp)}
    ):  # its clean stop must remove its temp folders
        client = ensure_broker(suite.state)
    final_pid = client.hello["pid"]
    suite.brokers.add(final_pid)
    client.call(OWNER_A, "project_select", {"projectPath": str(suite.project_a / "project.gbsproj")})
    rerun = client.call(OWNER_A, "emulator_run", {"romPath": rom_a})
    trace = [json.loads(line) for line in (suite.state / "trace.jsonl").read_text().splitlines()]
    cleared = [r for r in trace if r.get("event") == "stale_lease_check" and r.get("pid") == held_by]
    new_holder = json.loads(lease_path.read_text())["pid"] if lease_path.exists() else None
    suite.check(
        "R4",
        "After broker and workers are SIGKILLed together, the orphaned emulator lease is cleared "
        "automatically and the game's emulator starts again",
        orphaned
        and rerun.get("ok")
        and not rerun["result"].get("isError")
        and bool(cleared)
        and cleared[-1].get("cleared") is True
        and cleared[-1].get("owner") == "dead"
        and "cleared automatically" in (rerun.get("notice") or "")
        and new_holder not in (None, held_by),
        lease_left_by=held_by,
        orphaned_before_restart=orphaned,
        notice=rerun.get("notice"),
        check_event=cleared[-1] if cleared else None,
        new_lease_holder=new_holder,
    )
    client.call(OWNER_A, "emulator_close", {})
    suite.check("R5", "Closing the emulator releases its lease", not lease_path.exists())
    polite = client.request({"op": "shutdown"})
    suite.check(
        "R2b",
        "A broker with a live worker refuses a non-forced shutdown",
        polite.get("denied", {}).get("code") == "BUSY",
        response=polite,
    )
    in_use = fallback_dirs(final_pid)
    client.request({"op": "shutdown", "force": True})
    client.close()
    stopped = wait_gone([final_pid], 15)
    suite.check(
        "R3",
        "Clean shutdown removes the socket and token",
        stopped and not (suite.state / "broker.sock").exists() and not (suite.state / "broker.token").exists(),
    )
    left = fallback_dirs(final_pid)
    suite.check(
        "T2",
        "A clean shutdown removes the private temp folders the broker made for its workers",
        stopped and bool(in_use) and not left,
        in_use=[str(p) for p in in_use],
        left=[str(p) for p in left],
    )
