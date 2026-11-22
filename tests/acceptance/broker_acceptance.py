#!/usr/bin/env python3
"""Broker acceptance run against the real engine, compiler and emulator. Nothing is mocked.

Covers election, identity, private workers, lossless results, writer handoff, delegated
children, hardware gating, worker and broker crash recovery. It does not cover anything that
needs Hermes itself (host-injected identity, real compaction, pixels reaching a model).

    python tests/acceptance/broker_acceptance.py
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
HANDOFF = 3.0
os.environ["HERMRETRO_WRITER_HANDOFF_SECONDS"] = str(HANDOFF)

from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.client import BrokerClient, ensure_broker, spawn_broker  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.engine import EngineProcess  # noqa: E402 - the repository root goes on sys.path first
from backend.system import host as host_os  # noqa: E402 - the repository root goes on sys.path first

RUN = time.strftime("%Y%m%dT%H%M%S")
# Resolved: on macOS /tmp and /var are links into /private, and the engine reports real paths.
WORK = Path(tempfile.mkdtemp(prefix=f"chromatic-acceptance-{RUN}-")).resolve()
STATE = WORK / "state"
STATE.mkdir(mode=0o700)
NODE = paths.find_node()["path"]
ENGINE = paths.ENGINE_ROOT
HW = {"hardware_enabled": True}

checks: list[dict] = []
observations: dict = {}
BROKERS: set[int] = set()  # every broker this run started: their fallback temp folders are this run's


def check(check_id: str, title: str, passed: bool, **detail) -> bool:
    checks.append({"id": check_id, "title": title, "passed": bool(passed), "detail": detail})
    print(("PASS " if passed else "FAIL ") + check_id + " " + title, flush=True)
    return bool(passed)


def structured(response: dict) -> dict:
    return (response.get("result") or {}).get("structuredContent") or {}


def snapshot(root: Path) -> dict[str, str]:
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and not rel.startswith(("build/", ".chromatic", "artifacts/", "captures/")):
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def diff(before: dict, after: dict) -> list[str]:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def png_info(block: dict) -> dict:
    data = base64.b64decode(block["data"], validate=True)
    ok = data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24]) if ok else (0, 0)
    return {
        "png": ok,
        "width": width,
        "height": height,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "mimeType": block.get("mimeType"),
    }


def alive(pid: int) -> bool:
    """Running and not a zombie (`ps` works the same on Linux and macOS)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


def fallback_dirs(broker: int) -> list[Path]:
    """The private temp folders one broker made for its workers (``hrt-<pid>-`` in the system temp root),
    only those this user owns."""
    root = Path(host_os.SYSTEM_TEMP).resolve()
    found = []
    for path in root.glob(f"hrt-{broker}-*"):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid():
            found.append(path)
    return sorted(found)


def wait_gone(pids, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and any(alive(p) for p in pids):
        time.sleep(0.1)
    return not any(alive(p) for p in pids)


def stop_brokers() -> None:
    """Teardown: ask the broker to stop (it closes its workers and their temp folders), kill only what this run
    started and would not stop, then remove the temp folders brokers killed on purpose could not."""
    try:
        with BrokerClient(STATE) as last:
            last.request({"op": "shutdown", "force": True})
    except Exception:  # noqa: BLE001 - no broker running is the usual case
        pass
    if not wait_gone(BROKERS, 10):
        for pid in BROKERS:
            command = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True)
            if alive(pid) and "backend.broker" in command.stdout:
                os.kill(pid, signal.SIGKILL)
        wait_gone(BROKERS, 5)
    for pid in BROKERS:
        for path in fallback_dirs(pid):
            shutil.rmtree(path, ignore_errors=True)


def session_processes(leader: int) -> list[dict]:
    """Processes in the group a worker or the broker leads (each starts in its own session, so its group)."""
    listing = subprocess.run(["ps", "-A", "-o", "pid=,pgid=,rss=,comm="], capture_output=True, text=True).stdout
    found = []
    for line in listing.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[1] == str(leader):
            found.append({"pid": int(parts[0]), "comm": Path(parts[3]).name, "rss_kb": int(parts[2])})
    return found


def main() -> int:
    A = {"profile": "s01-profile", "conversation_id": "conv-A"}
    B = {"profile": "s01-profile", "conversation_id": "conv-B"}
    C = {"profile": "s01-profile", "conversation_id": "conv-C"}
    proj_a, proj_b = WORK / "projA", WORK / "projB"

    # --- election: racing lazy starts converge on exactly one broker ----------
    clients: list[BrokerClient] = []
    errors: list[str] = []

    def racer():
        try:
            clients.append(ensure_broker(STATE))
        except Exception as error:  # noqa: BLE001 - every racer's failure is collected and reported
            errors.append(repr(error))

    # Model the deep TMPDIR inherited from a Desktop or gateway launch. Only the broker's engine needs a
    # short path; leave sockets and test fixtures in their own short workspace. Fallback folders go to the system
    # temp root under the broker's pid; stop_brokers() removes those of brokers this run kills on purpose.
    deep_temp = WORK / ("nested-" + "x" * 120)
    deep_temp.mkdir()
    observations["inherited_compiler_tmp_bytes"] = len(os.fsencode(deep_temp))
    with mock.patch.dict(os.environ, {"TMPDIR": str(deep_temp)}):
        threads = [threading.Thread(target=racer) for _ in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
    pids = {c.hello.get("pid") for c in clients}
    gens = {c.hello.get("broker_generation") for c in clients}
    check(
        "E1",
        "Four racing lazy starts converge on one broker",
        not errors and len(clients) == 4 and len(pids) == 1 and len(gens) == 1,
        broker_pids=sorted(pids),
        errors=errors,
    )
    broker_pid = pids.pop()
    BROKERS.add(broker_pid)
    loser = spawn_broker(STATE, NODE)
    loser_code = loser.wait(timeout=10)
    check(
        "E2",
        "A second broker loses the election and exits before starting workers",
        loser_code == 3,
        exit_code=loser_code,
    )
    bad = BrokerClient(STATE, token="0" * 64)
    check(
        "E3",
        "Wrong handshake token is refused",
        bad.hello.get("ok") is False and bad.hello.get("denied", {}).get("code") == "UNAUTHENTICATED",
        response=bad.hello,
    )
    bad.close()
    for extra in clients[2:]:
        extra.close()
    ca, cb = clients[0], clients[1]  # two independent connections, as two chats would hold
    control = BrokerClient(STATE)

    # --- identity fails closed --------------------------------------------------
    before_lanes = len(control.request({"op": "stats"})["lanes"])
    r_none = ca.call(None, "session_status")
    r_empty = ca.call({"profile": "s01-profile", "conversation_id": ""}, "session_status")
    r_noprofile = ca.call({"conversation_id": "conv-A"}, "session_status")
    after_lanes = len(control.request({"op": "stats"})["lanes"])
    check(
        "I1",
        "Missing or empty owner identity is denied without dispatch or worker start",
        all(
            r.get("dispatched") is False and r.get("denied", {}).get("code") == "IDENTITY_REQUIRED"
            for r in (r_none, r_empty, r_noprofile)
        )
        and before_lanes == after_lanes == 0,
        lanes_before=before_lanes,
        lanes_after=after_lanes,
    )

    # --- two owners, two real projects -------------------------------------------
    ra = ca.call(
        A,
        "project_create",
        {"name": "S01 Project A", "destinationPath": str(proj_a), "template": "starter", "select": True},
        origin={"session_id": "sess-A-1"},
    )
    rb = cb.call(
        B,
        "project_create_blank",
        {
            "name": "S01 Project B",
            "destinationPath": str(proj_b),
            "gameType": "TOPDOWN",
            "colorMode": "color",
            "select": True,
        },
        origin={"session_id": "sess-B-1"},
    )
    sa, sb = ca.call(A, "session_status"), cb.call(B, "session_status")
    check(
        "O1",
        "Each owner gets a private engine process with its own selected project",
        ra.get("ok")
        and rb.get("ok")
        and structured(sa).get("projectRoot") == str(proj_a)
        and structured(sb).get("projectRoot") == str(proj_b)
        and sa["lane"]["engine_pid"] != sb["lane"]["engine_pid"],
        a=sa.get("lane"),
        b=sb.get("lane"),
    )
    snap_a0, snap_b0 = snapshot(proj_a), snapshot(proj_b)

    # --- A edits native source; B is untouched -------------------------------------
    inspect_a = ca.call(A, "variable_inspect")
    edit_a = ca.call(
        A,
        "variable_set",
        {
            "name": "S01 marker A",
            "symbol": "var_s01_marker_a",
            "expectedRevision": structured(inspect_a).get("revision"),
        },
    )
    snap_a1, snap_b1 = snapshot(proj_a), snapshot(proj_b)
    check(
        "O2",
        "A's native edit changes only project A",
        edit_a.get("ok")
        and not edit_a["result"].get("isError")
        and diff(snap_a0, snap_a1) != []
        and diff(snap_b0, snap_b1) == [],
        a_changed=diff(snap_a0, snap_a1),
        b_changed=diff(snap_b0, snap_b1),
        edit=structured(edit_a) if len(json.dumps(structured(edit_a))) < 1500 else "large",
    )

    # --- concurrent real official builds ---------------------------------------------
    builds: dict = {}

    def build(label, client, owner):
        start = time.time()
        builds[label] = {"response": client.call(owner, "rom_build", {}), "start": start, "end": time.time()}

    tb = [threading.Thread(target=build, args=("A", ca, A)), threading.Thread(target=build, args=("B", cb, B))]
    [t.start() for t in tb]
    [t.join() for t in tb]
    rom_a = structured(builds["A"]["response"]).get("outputPath")
    rom_b = structured(builds["B"]["response"]).get("outputPath")
    overlap = min(builds["A"]["end"], builds["B"]["end"]) - max(builds["A"]["start"], builds["B"]["start"])
    hash_a = hashlib.sha256(Path(rom_a).read_bytes()).hexdigest() if rom_a and Path(rom_a).is_file() else None
    hash_b = hashlib.sha256(Path(rom_b).read_bytes()).hexdigest() if rom_b and Path(rom_b).is_file() else None
    check(
        "O3",
        "Both owners build genuine distinct ROMs concurrently with the official compiler",
        bool(
            hash_a
            and hash_b
            and hash_a != hash_b
            and overlap > 0
            and structured(builds["A"]["response"]).get("builder") == "gb-studio-cli"
            and str(rom_a).startswith(str(proj_a))
            and str(rom_b).startswith(str(proj_b))
        ),
        rom_a=rom_a,
        rom_b=rom_b,
        sha256_a=hash_a,
        sha256_b=hash_b,
        overlap_seconds=round(overlap, 2),
        seconds_a=round(builds["A"]["end"] - builds["A"]["start"], 2),
        seconds_b=round(builds["B"]["end"] - builds["B"]["start"], 2),
    )

    # -- V1: the player the user watches follows every build ------------------------------
    plain = structured(builds["A"]["response"])
    live_1 = ca.call(A, "rom_build", {}, policy={"live_player": True})
    live_2 = ca.call(A, "rom_build", {}, policy={"live_player": True})
    player_1, player_2 = live_1.get("player") or {}, live_2.get("player") or {}
    served = None
    if player_1.get("url"):
        try:
            with urllib.request.urlopen(player_1["url"], timeout=10) as page:
                served = page.status
        except OSError as error:
            served = str(error)
    check(
        "V1",
        "With the live player on, each successful build also refreshes the playable copy at one stable "
        "address; without it a build starts no player",
        "player" not in builds["A"]["response"]
        and plain.get("success") is not False
        and player_1.get("ready") is True
        and player_1.get("first") is True
        and player_2.get("ready") is True
        and player_2.get("first") is False
        and player_1.get("url") == player_2.get("url")
        and served == 200,
        first=player_1.get("first"),
        second_first=player_2.get("first"),
        same_url=player_1.get("url") == player_2.get("url"),
        http=served,
    )
    ca.call(A, "web_preview_close", {})
    hash_a = hashlib.sha256(Path(rom_a).read_bytes()).hexdigest()  # A was rebuilt; later checks use this ROM

    # --- real frames, lossless, private emulator state ---------------------------------
    ca.call(A, "emulator_run", {"romPath": rom_a})
    step_a = ca.call(A, "emulator_step", {"buttons": ["right"], "frames": 45, "sampleCount": 3})
    blocks = [b for b in step_a["result"].get("content", []) if b.get("type") == "image"]
    infos = [png_info(b) for b in blocks]
    samples = structured(step_a).get("samples", [])
    check(
        "M1",
        "Real PNG frame bytes arrive intact and match the engine's own per-sample hashes",
        len(infos) == 3
        and all(i["png"] and (i["width"], i["height"]) == (160, 144) for i in infos)
        and [i["sha256"] for i in infos] == [s.get("sha256") for s in samples]
        and structured(step_a).get("romSha256") == hash_a
        and structured(step_a).get("genuineEmulatorFrames") is True,
        frames=infos,
        engine_sample_hashes=[s.get("sha256") for s in samples],
        frame_numbers=[s.get("frame") for s in samples],
    )
    frame_dir = WORK / "frames"
    frame_dir.mkdir()
    for index, block in enumerate(blocks):
        (frame_dir / f"A-step-{index}.png").write_bytes(base64.b64decode(block["data"]))
    frame_a = structured(step_a).get("frame")

    status_b0 = cb.call(B, "session_status")
    run_b = cb.call(B, "emulator_run", {"romPath": rom_b})
    step_b = cb.call(B, "emulator_step", {"buttons": ["down"], "frames": 200, "sampleCount": 1})
    cross = cb.call(B, "emulator_run", {"romPath": rom_a})  # B asks for A's ROM path
    status_a = ca.call(A, "emulator_status")
    sess_a = ca.call(A, "session_status")
    check(
        "O4",
        "B's emulator work never advances, restarts or re-selects A's session",
        structured(status_b0).get("emulatorActive") is False
        and structured(run_b).get("romSha256") == hash_b
        and structured(step_b).get("frame", 0) >= 200
        and structured(status_a).get("frame") == frame_a
        and structured(status_a).get("romSha256") == hash_a
        and structured(status_a).get("activeButtons") == ["right"]
        and structured(sess_a).get("projectRoot") == str(proj_a),
        a_frame_after_own_step=frame_a,
        a_frame_after_b_activity=structured(status_a).get("frame"),
        b_frame=structured(step_b).get("frame"),
        b_request_for_a_rom={
            "isError": cross["result"].get("isError") if cross.get("ok") else None,
            "structured": structured(cross) if cross.get("ok") else cross,
        },
    )
    observations["b_request_for_a_rom_path"] = (
        "engine refused" if cross.get("ok") and cross["result"].get("isError") else "see O4 detail"
    )

    # --- lossless: broker result equals a direct private engine result -------------------
    via_broker = ca.call(A, "rom_inspect", {"romPath": rom_a})
    with EngineProcess(ENGINE, node=NODE, client_name="chromatic-studio-acceptance-direct") as direct:
        direct.call_tool("project_select", {"projectPath": str(proj_a / "project.gbsproj")})
        direct_result = direct.call_tool("rom_inspect", {"romPath": rom_a})
        direct_error = direct.call_tool("project_select", {"projectPath": str(WORK / "missing" / "project.gbsproj")})
    broker_error = ca.call(A, "project_select", {"projectPath": str(WORK / "missing" / "project.gbsproj")})
    check(
        "M2",
        "Broker returns byte-equivalent raw results, including a structured engine error",
        via_broker["result"] == direct_result
        and broker_error["result"] == direct_error
        and broker_error["result"].get("isError") is True
        and bool(structured(broker_error).get("code")),
        error_code=structured(broker_error).get("code"),
        result_keys=sorted(via_broker["result"].keys()),
    )
    sess_a2 = ca.call(A, "session_status")
    check(
        "M3",
        "A failed select leaves the previous selection and writer lease intact",
        structured(sess_a2).get("projectRoot") == str(proj_a) and sess_a2["lane"]["writer"] is True,
        lane=sess_a2["lane"],
    )

    # --- spoofed identity in tool arguments has no routing effect -------------------------
    spoof = cb.call(B, "session_status", {"conversation_id": "conv-A"})
    sess_b = cb.call(B, "session_status")
    check(
        "I2",
        "Identity placed in tool arguments is rejected by the schema and never reroutes",
        spoof["result"].get("isError") is True
        and spoof["lane"]["owner_key"] == sess_b["lane"]["owner_key"]
        and structured(sess_b).get("projectRoot") == str(proj_b),
        engine_message=spoof["result"]["content"][0].get("text", "")[:200],
    )

    # --- runtime session rotation keeps the durable lane (simulated ids) -------------------
    rot = ca.call(A, "session_status", origin={"session_id": "sess-A-2-after-compaction"})
    check(
        "I3",
        "A rotated runtime session id maps to the same worker, selection and emulator",
        rot["lane"]["engine_pid"] == sa["lane"]["engine_pid"]
        and rot["lane"]["engine_generation"] == sa["lane"]["engine_generation"]
        and structured(rot).get("projectRoot") == str(proj_a)
        and structured(rot).get("emulatorActive") is True
        and rot["lane"]["sessions_seen"] == ["sess-A-1", "sess-A-2-after-compaction"],
        lane=rot["lane"],
        note="session ids simulated here; real compaction is layer 2",
    )

    # --- delegated child leases --------------------------------------------------------------
    child = {"session_id": "sess-child-1", "task_id": "task-child-1", "delegated": True}
    orphan = ca.call({"profile": "s01-profile", "conversation_id": "conv-nobody"}, "session_status", origin=child)
    child_read = ca.call(A, "variable_inspect", origin=child)
    child_write = ca.call(
        A,
        "variable_set",
        {"name": "child no lease", "expectedRevision": structured(child_read).get("revision")},
        origin=child,
    )
    child_grant_self = ca.request({"op": "grant_lease", "owner": A, "task_id": "task-child-1", "origin": child})
    snap_a2 = snapshot(proj_a)
    grant = ca.request({"op": "grant_lease", "owner": A, "task_id": "task-child-1", "mode": "write"})
    child_write2 = ca.call(
        A,
        "variable_set",
        {
            "name": "S01 child leased",
            "symbol": "var_s01_child",
            "expectedRevision": structured(child_read).get("revision"),
        },
        origin=child,
    )
    child_select = ca.call(A, "project_select", {"projectPath": str(proj_b / "project.gbsproj")}, origin=child)
    child_close = ca.call(A, "emulator_close", origin=child)
    ca.request({"op": "revoke_lease", "owner": A, "task_id": "task-child-1"})
    child_write3 = ca.call(A, "variable_set", {"name": "after revoke"}, origin=child)
    still_running = ca.call(A, "emulator_status")
    check(
        "L1",
        "Delegated child: read allowed, write needs a parent-granted lease, parent-only actions refused",
        orphan.get("denied", {}).get("code") == "NO_PARENT_LANE"
        and child_read.get("ok")
        and child_write.get("denied", {}).get("code") == "LEASE_REQUIRED"
        and child_grant_self.get("denied", {}).get("code") == "PARENT_ONLY"
        and diff(snap_a1, snap_a2) == []
        and grant.get("ok")
        and child_write2.get("ok")
        and not child_write2["result"].get("isError")
        and child_select.get("denied", {}).get("code") == "PARENT_ONLY"
        and child_close.get("denied", {}).get("code") == "PARENT_ONLY"
        and child_write3.get("denied", {}).get("code") == "LEASE_REQUIRED"
        and structured(still_running).get("frame") == frame_a,
        codes={
            "orphan": orphan.get("denied"),
            "no_lease": child_write.get("denied"),
            "self_grant": child_grant_self.get("denied"),
            "select": child_select.get("denied"),
            "close": child_close.get("denied"),
            "after_revoke": child_write3.get("denied"),
        },
    )

    # --- two conversations on the same project root -------------------------------------------
    cc = BrokerClient(STATE)
    sel_c = cc.call(C, "project_select", {"projectPath": str(proj_a / "project.gbsproj")})
    read_c = cc.call(C, "variable_inspect")
    stale_revision = structured(read_c).get("revision")
    inspect_a2 = ca.call(A, "variable_inspect")
    edit_a2 = ca.call(
        A,
        "variable_set",
        {
            "name": "S01 A second edit",
            "symbol": "var_s01_a_two",
            "expectedRevision": structured(inspect_a2).get("revision"),
        },
    )
    snap_a3 = snapshot(proj_a)
    write_c = cc.call(C, "variable_set", {"name": "C conflicting", "expectedRevision": stale_revision})
    build_c = cc.call(C, "rom_build", {})
    check(
        "W1",
        "While one conversation is writing, a second one on the same root can read but not write or build",
        sel_c.get("ok")
        and not sel_c["result"].get("isError")
        and sel_c["lane"]["writer"] is False
        and read_c.get("ok")
        and edit_a2.get("ok")
        and not edit_a2["result"].get("isError")
        and write_c.get("dispatched") is False
        and write_c.get("denied", {}).get("code") == "PROJECT_WRITER_BUSY"
        and build_c.get("denied", {}).get("code") == "PROJECT_WRITER_BUSY"
        and diff(snap_a3, snapshot(proj_a)) == [],
        c_lane=sel_c.get("lane"),
        denial=write_c.get("denied"),
    )
    time.sleep(HANDOFF + 0.5)
    stale_write = cc.call(C, "variable_set", {"name": "C stale", "expectedRevision": stale_revision})
    snap_a4 = snapshot(proj_a)
    fresh = cc.call(C, "variable_inspect")
    fresh_write = cc.call(
        C,
        "variable_set",
        {"name": "S01 C after handoff", "symbol": "var_s01_c", "expectedRevision": structured(fresh).get("revision")},
    )
    a_right_after = ca.call(A, "variable_set", {"name": "A too soon"})
    check(
        "W2",
        "A quiet writer yields after the handoff interval; the engine still rejects the stale revision",
        stale_write.get("ok")
        and stale_write["result"].get("isError") is True
        and structured(stale_write).get("code") == "STALE_RESOURCE"
        and fresh_write.get("ok")
        and not fresh_write["result"].get("isError")
        and fresh_write["lane"]["writer"] is True
        and a_right_after.get("denied", {}).get("code") == "PROJECT_WRITER_BUSY",
        stale_engine_error=structured(stale_write),
        files_changed_by_fresh_write=diff(snap_a4, snapshot(proj_a)),
    )

    # --- hardware stays off unless the caller's policy enables it ----------------------------------
    off = {tool: ca.call(A, tool, {}) for tool in ("device", "setup", "flash", "play", "device_capture")}
    unknown = ca.call(A, "not_a_real_tool", {})
    child_hw = ca.call(A, "device", {"command": "status"}, origin=child, policy=HW)
    child_prepare = ca.call(A, "toolchain_prepare", {"components": ["emulator"]}, origin=child)
    # 'device status' reads platform and driver requirements without touching USB.
    on_status = ca.call(A, "device", {"command": "status"}, policy=HW)
    check(
        "P1",
        "Hardware tools are refused before dispatch unless enabled; children can never use them",
        all(r.get("dispatched") is False and r["denied"]["code"] == "HARDWARE_DISABLED" for r in off.values())
        and unknown.get("denied", {}).get("code") == "UNKNOWN_TOOL"
        and child_hw.get("denied", {}).get("code") == "PARENT_ONLY"
        and child_prepare.get("denied", {}).get("code") == "PARENT_ONLY"
        and on_status.get("dispatched") is True
        and on_status.get("ok") is True,
        enabled_device_status_is_error=on_status.get("result", {}).get("isError"),
        enabled_device_status=json.dumps(structured(on_status))[:600],
    )

    # --- desktop lookup and dependency doctor ---------------------------------------------------------
    by_conversation = control.request({"op": "lane_status", "profile": "s01-profile", "session_id": "conv-A"})
    by_session = control.request(
        {"op": "lane_status", "profile": "s01-profile", "session_id": "sess-A-2-after-compaction"}
    )
    other_profile = control.request({"op": "lane_status", "profile": "someone-else", "session_id": "conv-A"})
    doctor = control.request({"op": "doctor"})
    components = {c["id"]: c["status"] for c in structured(doctor).get("components", [])}
    check(
        "D1",
        "Lane lookup works by conversation or runtime session id and is profile-scoped; doctor reports",
        (by_conversation.get("lane") or {}).get("selected_root") == str(proj_a)
        and (by_conversation.get("lane") or {}).get("emulator_active") is True
        and (by_session.get("lane") or {}).get("selected_root") == str(proj_a)
        and other_profile.get("lane") is None
        and components.get("runtime") == "ready",
        components=components,
    )

    # -- D2: the desktop panel's view -------------------------------------------------------
    seen = control.request({"op": "activity", "profile": "s01-profile", "ids": ["conv-A"]})
    tools_seen = [event["tool"] for event in seen.get("events") or []]
    frame = seen.get("frame") or {}
    fallback = control.request({"op": "activity", "profile": "s01-profile", "ids": ["a-chat-with-no-worker"]})
    elsewhere = control.request({"op": "activity", "profile": "someone-else", "ids": ["conv-A"]})
    check(
        "D2",
        "The panel view reports a chat's project, build, latest real frame and log from memory; "
        "an unknown chat falls back to the most recent one; other profiles see nothing",
        seen.get("matched") == "chat"
        and bool(seen["lane"]["project_root"])
        and "rom_build" in tools_seen
        and (seen.get("build") or {}).get("ok") is True
        and frame.get("mimeType") == "image/png"
        and len(frame.get("data") or "") > 200
        and fallback.get("matched") == "recent"
        and fallback.get("lane") is not None
        and elsewhere.get("lane") is None,
        tools=tools_seen[-8:],
        build=seen.get("build"),
        frame_tool=frame.get("tool"),
        fallback=fallback.get("matched"),
        elsewhere=elsewhere.get("matched"),
    )

    # --- a worker that dies is replaced, selection restored, and the loss is reported -----------------
    a_pid = ca.call(A, "session_status")["lane"]["engine_pid"]
    os.kill(a_pid, signal.SIGKILL)
    time.sleep(1.0)
    after_crash = ca.call(A, "session_status")
    check(
        "R0",
        "A crashed worker is replaced: selection restored, emulator reported as reset",
        after_crash.get("ok")
        and after_crash["lane"]["engine_pid"] != a_pid
        and after_crash["lane"]["engine_generation"] == 2
        and structured(after_crash).get("projectRoot") == str(proj_a)
        and structured(after_crash).get("emulatorActive") is False
        and "restarted" in (after_crash.get("notice") or ""),
        notice=after_crash.get("notice"),
    )

    # --- measured cost ---------------------------------------------------------------------------------
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
    observations["worker_cost"] = cost
    trace = [json.loads(line) for line in (STATE / "trace.jsonl").read_text().splitlines()]
    observations["worker_ready_seconds"] = [r["ready_seconds"] for r in trace if r.get("event") == "worker_started"]
    observations["broker_rss_mb"] = round(
        next((p["rss_kb"] for p in session_processes(broker_pid) if p["pid"] == broker_pid), 0) / 1024, 1
    )

    # --- crash: SIGKILL the broker; workers must not be orphaned -----------------------------------------
    worker_pids = sorted({p["pid"] for lane in cost for p in lane["processes"]})
    private_temp = fallback_dirs(broker_pid)
    check(
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
    check(
        "R1",
        "After SIGKILL of the broker no engine, compiler or emulator process is orphaned",
        not survivors and not alive(broker_pid),
        killed_broker_pid=broker_pid,
        worker_processes=len(worker_pids),
        survivors=survivors,
    )
    for client in (ca, cb, cc, control):
        client.close()
    snap_before_restart = snapshot(proj_a)
    c2 = ensure_broker(STATE)
    BROKERS.add(c2.hello["pid"])
    fresh_status = c2.call(A, "session_status")
    reselect = c2.call(A, "project_select", {"projectPath": str(proj_a / "project.gbsproj")})
    names = [v.get("name") for v in structured(c2.call(A, "variable_inspect")).get("variables", [])]
    check(
        "R2",
        "A new broker reports lost process-local state honestly; native source is intact and reselectable",
        c2.hello["pid"] != broker_pid
        and structured(fresh_status).get("selected") is False
        and structured(fresh_status).get("emulatorActive") is False
        and reselect.get("ok")
        and not reselect["result"].get("isError")
        and diff(snap_before_restart, snapshot(proj_a)) == []
        and {"S01 marker A", "S01 child leased", "S01 A second edit", "S01 C after handoff"} <= set(names),
        new_broker_pid=c2.hello["pid"],
        variables=names,
    )
    # --- a gateway restart under systemd: broker AND workers SIGKILLed at once (KillMode=mixed) -------------
    # The killed emulator never releases its recording lease; the next broker must clear it, not refuse.
    c2.call(A, "emulator_run", {"romPath": rom_a})
    lease_path = proj_a / "artifacts" / ".recording-access" / "lease.json"
    held_by = json.loads(lease_path.read_text())["pid"] if lease_path.exists() else None
    killed_broker = c2.hello["pid"]
    groups = [lane["engine_pid"] for lane in c2.request({"op": "stats"})["lanes"] if lane["engine_pid"]]
    c2.close()
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
    with mock.patch.dict(os.environ, {"TMPDIR": str(deep_temp)}):  # its clean stop must remove its temp folders
        c2 = ensure_broker(STATE)
    final_pid = c2.hello["pid"]
    BROKERS.add(final_pid)
    c2.call(A, "project_select", {"projectPath": str(proj_a / "project.gbsproj")})
    rerun = c2.call(A, "emulator_run", {"romPath": rom_a})
    trace = [json.loads(line) for line in (STATE / "trace.jsonl").read_text().splitlines()]
    cleared = [r for r in trace if r.get("event") == "stale_lease_check" and r.get("pid") == held_by]
    new_holder = json.loads(lease_path.read_text())["pid"] if lease_path.exists() else None
    check(
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
    c2.call(A, "emulator_close", {})
    check("R5", "Closing the emulator releases its lease", not lease_path.exists())
    polite = c2.request({"op": "shutdown"})
    check(
        "R2b",
        "A broker with a live worker refuses a non-forced shutdown",
        polite.get("denied", {}).get("code") == "BUSY",
        response=polite,
    )
    in_use = fallback_dirs(final_pid)
    c2.request({"op": "shutdown", "force": True})
    c2.close()
    stopped = wait_gone([final_pid], 15)
    check(
        "R3",
        "Clean shutdown removes the socket and token",
        stopped and not (STATE / "broker.sock").exists() and not (STATE / "broker.token").exists(),
    )
    left = fallback_dirs(final_pid)
    check(
        "T2",
        "A clean shutdown removes the private temp folders the broker made for its workers",
        stopped and bool(in_use) and not left,
        in_use=[str(p) for p in in_use],
        left=[str(p) for p in left],
    )

    passed = all(c["passed"] for c in checks)
    evidence_file = write_evidence(passed)
    print(
        json.dumps(
            {
                "passed": passed,
                "checks": f"{sum(c['passed'] for c in checks)}/{len(checks)}",
                "evidence": str(evidence_file),
            },
            indent=2,
        )
    )
    return 0 if passed else 1


def write_evidence(passed: bool, crashed: str | None = None) -> Path:
    trace_file = STATE / "trace.jsonl"
    trace = [json.loads(line) for line in trace_file.read_text().splitlines()] if trace_file.exists() else []
    evidence = {
        "suite": "broker acceptance (real engine, outside Hermes)",
        "run": RUN,
        "passed": passed,
        "checks_passed": sum(c["passed"] for c in checks),
        "checks_total": len(checks),
        "crashed": crashed,
        "backend": {
            "version": paths.PLUGIN_VERSION,
            "protocol": paths.PROTOCOL,
            "code_fingerprint": paths.code_fingerprint(),
        },
        "engine": paths.verify_engine(),
        "host": {
            "node": subprocess.run([NODE, "--version"], capture_output=True, text=True).stdout.strip(),
            "python": sys.version.split()[0],
            "platform": sys.platform,
        },
        "not_covered": [
            "Anything that needs Hermes itself",
            "Browser player and annotations",
            "Long-operation recovery",
            "Any hardware operation beyond a no-USB status read",
        ],
        "checks": checks,
        "observations": observations,
        "trace_events": len(trace),
        "trace_tail": trace[-40:] if not passed else [],
    }
    out = REPO / "notes" / "evidence"  # git-ignored: run evidence stays local
    out.mkdir(parents=True, exist_ok=True)
    # Keep the home directory (and so the user name) out of it, in case it is shared.
    (out / "broker-acceptance.json").write_text(
        json.dumps(evidence, indent=2, default=str).replace(str(Path.home()), "~") + "\n"
    )
    return out / "broker-acceptance.json"


def run() -> int:
    try:
        return main()
    except Exception:  # noqa: BLE001 - keep what happened for the evidence file, then fail
        import traceback

        crashed = traceback.format_exc()
        print(crashed, file=sys.stderr, flush=True)
        write_evidence(False, crashed)
        return 1
    finally:
        stop_brokers()
        shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(run())
