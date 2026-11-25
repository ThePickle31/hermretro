"""Worker restart, broker crash, recording-lease recovery, replaced watched folders and clean shutdown."""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

from backend.broker.client import ensure_broker
from tests.acceptance.fixture import OWNER_A, OWNER_B, alive, diff, fallback_dirs, snapshot, structured, wait_gone


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


def until(read, done, seconds: float = 15.0):
    """`read()` again until `done` accepts its value or `seconds` pass; the last value."""
    deadline = time.monotonic() + seconds
    value = read()
    while not done(value) and time.monotonic() < deadline:
        time.sleep(0.1)
        value = read()
    return value


def check_watched_folder_replaced(suite, client_b):
    """Project folders the engine watches that become files, other folders or unwatchable leave the same engine
    serving. The build's debug folder removed for a file; an asset folder moved away and replaced by another folder,
    then by a file, whose sprites follow each time; a folder that cannot be watched (unreadable: on Linux the watch
    fails) leaves the project read in full until it goes, then the watch starts again and sees the next outside edit;
    the project folder replaced by a copy is read again. Node's own recursive watcher on Linux (Node 24.22, 26.9 and
    newer) threw on these and ended the engine."""

    def sprites():
        """The inventory's sprite paths, or None when the call fails."""
        response = client_b.call(
            OWNER_B, "project_inventory", {"resourceTypes": ["asset"], "assetTypes": ["sprite"], "limit": 250}
        )
        listed = structured(response).get("assets")
        if (response.get("result") or {}).get("isError") or not isinstance(listed, list):
            return None
        return {asset.get("resourcePath") for asset in listed}

    def refreshed_state():
        return (structured(client_b.call(OWNER_B, "project_refresh", {"mode": "strong"})).get("indexStats") or {}).get(
            "state"
        )

    def index_stats():
        status = client_b.call(OWNER_B, "session_status", {"includeIndexStats": True})
        return structured(status).get("indexStats") or {}

    def listing(*present, absent=()):
        return lambda found: (
            found is not None and all(p in found for p in present) and not any(p in found for p in absent)
        )

    watched, replacement, fresh, copied = (
        "assets/sprites/watched/watched.png",
        "assets/sprites/watched/replacement.png",
        "assets/sprites/fresh.png",
        "assets/sprites/copied.png",
    )
    engine = client_b.call(OWNER_B, "session_status")["lane"]["engine_pid"]
    debug = Path(structured(client_b.call(OWNER_B, "rom_build", {}))["debugArtifacts"]["directory"])
    shutil.rmtree(debug)
    debug.write_text("not a folder")
    sprite_folder = suite.project_b / "assets" / "sprites"
    sprite = next(sprite_folder.glob("*.png"))
    folder = sprite_folder / "watched"
    folder.mkdir()
    shutil.copy(sprite, folder / "watched.png")
    added = until(sprites, listing(watched))
    folder.rename(suite.work / "watched-away")
    folder.mkdir()
    shutil.copy(sprite, folder / "replacement.png")
    replaced = until(sprites, listing(replacement, absent=[watched]))
    folder.rename(suite.work / "replacement-away")
    folder.write_text("not a folder")
    after = until(sprites, listing(absent=[watched, replacement]))

    locked = debug.parent / "locked"
    locked.mkdir(mode=0)
    can_fail = sys.platform == "linux" and not os.access(locked, os.R_OK)  # root reads it; macOS watches natively
    expected = "invalidated" if can_fail else "ready"
    while_locked = until(refreshed_state, lambda state: state == expected)
    locked.rmdir()
    watched_again = until(refreshed_state, lambda state: state == "ready")
    before_edit = index_stats()
    shutil.copy(sprite, sprite_folder / "fresh.png")
    edited = until(sprites, listing(fresh))
    after_edit = index_stats()
    seen_by_watch = after_edit.get("dirtyEvents", 0) > before_edit.get("dirtyEvents", 0) and after_edit.get(
        "fallbackFullRebuilds"
    ) == before_edit.get("fallbackFullRebuilds")

    copy = suite.work / "projB-copy"
    shutil.copytree(suite.project_b, copy, symlinks=True)
    shutil.copy(sprite, copy / copied)
    suite.project_b.rename(suite.work / "projB-replaced")
    copy.rename(suite.project_b)
    root_replaced = until(sprites, listing(copied))

    status = client_b.call(OWNER_B, "session_status")
    debug.unlink()
    folder.unlink()
    for name in (fresh, copied):
        (suite.project_b / name).unlink()
    restored = until(sprites, listing(absent=[fresh, copied]))
    rebuilt = structured(client_b.call(OWNER_B, "rom_build", {}))
    suite.check(
        "R6",
        "Watched folders that become files or other folders, or cannot be watched, and a replaced project folder leave "
        "the same engine serving: the inventory follows each change, an unwatchable folder leaves the project read in "
        "full until it goes, the watch then sees an outside edit, and the next build succeeds",
        status.get("ok") is True
        and status["lane"]["engine_pid"] == engine
        and listing(watched)(added)
        and listing(replacement, absent=[watched])(replaced)
        and listing(absent=[watched, replacement])(after)
        and while_locked == expected
        and watched_again == "ready"
        and listing(fresh)(edited)
        and seen_by_watch
        and listing(copied)(root_replaced)
        and listing(absent=[fresh, copied])(restored)
        and rebuilt.get("success") is True,
        engine_pid={"before": engine, "after": (status.get("lane") or {}).get("engine_pid")},
        status=status.get("denied") or status.get("notice"),
        inventory={
            name: None if found is None else sorted(found)
            for name, found in {
                "added": added,
                "replaced": replaced,
                "after": after,
                "edited": edited,
                "root_replaced": root_replaced,
                "restored": restored,
            }.items()
        },
        index_state={"while_locked": while_locked, "expected": expected, "after": watched_again},
        edit_stats={
            key: (before_edit.get(key), after_edit.get(key)) for key in ("dirtyEvents", "fallbackFullRebuilds")
        },
        rebuilt={key: rebuilt.get(key) for key in ("success", "error")},
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
        "A new broker reports lost process-local state honestly, selects the game for its own conversation again; "
        "native source is intact and reselectable",
        client.hello["pid"] != broker_pid
        and structured(fresh_status).get("projectRoot") == str(suite.project_a)
        and structured(fresh_status).get("emulatorActive") is False
        and reselect.get("ok")
        and not reselect["result"].get("isError")
        and diff(snap_before_restart, snapshot(suite.project_a)) == []
        and {"S01 marker A", "S01 child leased", "S01 A second edit"} <= set(names),
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
