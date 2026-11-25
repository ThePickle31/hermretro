"""Independent projects, ROM builds and emulator results on the two chats' worker processes."""

import base64
import hashlib
import json
import os
import signal
import struct
import threading
import time
import urllib.request
from pathlib import Path

from backend import library
from backend.broker.engine import EngineProcess
from backend.library import game_card, layout
from backend.system import paths
from tests.acceptance import build_output
from tests.acceptance.fixture import OWNER_A, OWNER_B, diff, snapshot, structured


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


def played_hash(root: Path) -> str | None:
    """The SHA-256 of the ROM the playable copy in ``root``'s ``build/web`` plays."""
    played = library.web_rom(root)
    return hashlib.sha256(played.read_bytes()).hexdigest() if played else None


def create_and_edit(suite, client_a, client_b):
    ra = client_a.call(
        OWNER_A,
        "project_create",
        {"name": "S01 Project A", "destinationPath": str(suite.project_a), "template": "starter", "select": True},
        origin={"session_id": "sess-A-1"},
    )
    rb = client_b.call(
        OWNER_B,
        "project_create_blank",
        {
            "name": "S01 Project B",
            "destinationPath": str(suite.project_b),
            "gameType": "TOPDOWN",
            "colorMode": "color",
            "select": True,
        },
        origin={"session_id": "sess-B-1"},
    )
    first_status, sb = client_a.call(OWNER_A, "session_status"), client_b.call(OWNER_B, "session_status")
    suite.check(
        "O1",
        "Each owner gets a private engine process with its own selected project",
        ra.get("ok")
        and rb.get("ok")
        and structured(first_status).get("projectRoot") == str(suite.project_a)
        and structured(sb).get("projectRoot") == str(suite.project_b)
        and first_status["lane"]["engine_pid"] != sb["lane"]["engine_pid"],
        a=first_status.get("lane"),
        b=sb.get("lane"),
    )
    made = {str(root): layout.check(root) for root in (suite.project_a, suite.project_b)}
    suite.check(
        "G1",
        "Each new game is made in the game layout: its id, README, changelog and .gitignore",
        all(report["ok"] for report in made.values())
        and all(
            layout.game_identity(root)
            and game_card.load(root).get("id") == layout.game_identity(root)
            and game_card.load(root).get("rom") == "build/game.gbc"
            and game_card.load(root).get("gameVersion") == "0.1.0"
            and (root / "README.md").read_text().startswith(layout.MARKERS[0])
            and all((root / name).is_file() for name in ("CHANGELOG.md", ".gitignore"))
            for root in (suite.project_a, suite.project_b)
        ),
        layout=made,
    )
    check_new_project_defaults(suite, client_b)
    snap_a0, snap_b0 = snapshot(suite.project_a), snapshot(suite.project_b)

    inspect_a = client_a.call(OWNER_A, "variable_inspect")
    edit_a = client_a.call(
        OWNER_A,
        "variable_set",
        {
            "name": "S01 marker A",
            "symbol": "var_s01_marker_a",
            "expectedRevision": structured(inspect_a).get("revision"),
        },
    )
    edited_source, snap_b1 = snapshot(suite.project_a), snapshot(suite.project_b)
    suite.check(
        "O2",
        "A's native edit changes only project A",
        edit_a.get("ok")
        and not edit_a["result"].get("isError")
        and diff(snap_a0, edited_source) != []
        and diff(snap_b0, snap_b1) == [],
        a_changed=diff(snap_a0, edited_source),
        b_changed=diff(snap_b0, snap_b1),
        edit=structured(edit_a) if len(json.dumps(structured(edit_a))) < 1500 else "large",
    )
    return first_status, edited_source


def check_new_project_defaults(suite, client_b):
    authors = {
        root.name: json.loads((root / "project.gbsproj").read_text()).get("author")
        for root in (suite.project_a, suite.project_b)
    }
    fields = {
        item["id"]: item["value"]
        for item in json.loads((suite.project_b / "project" / "engine_field_values.gbsres").read_text())[
            "engineFieldValues"
        ]
    }
    speed = client_b.call(OWNER_B, "settings_update", {"settings": {"startMoveSpeed": 2}})
    settings = json.loads((suite.project_b / "project" / "settings.gbsres").read_text())
    platformer = {key: fields.get(key) for key in ("FEAT_PLATFORM_COYOTE_TIME", "FEAT_PLATFORM_DROP_THROUGH")}
    suite.check(
        "N1",
        "A new game has no template author and GB Studio's platformer defaults, and settings_update sets the "
        "player's move speed",
        set(authors.values()) == {""}
        and set(platformer.values()) == {1}
        and speed.get("ok")
        and not speed["result"].get("isError")
        and settings.get("startMoveSpeed") == 2,
        authors=authors,
        platformer=platformer,
        start_move_speed=settings.get("startMoveSpeed"),
    )


def build_roms(suite, client_a, client_b):
    builds: dict = {}

    def build(label, client, owner):
        start = time.time()
        builds[label] = {"response": client.call(owner, "rom_build", {}), "start": start, "end": time.time()}

    threads = [
        threading.Thread(target=build, args=("A", client_a, OWNER_A)),
        threading.Thread(target=build, args=("B", client_b, OWNER_B)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    rom_a = structured(builds["A"]["response"]).get("outputPath")
    rom_b = structured(builds["B"]["response"]).get("outputPath")
    overlap = min(builds["A"]["end"], builds["B"]["end"]) - max(builds["A"]["start"], builds["B"]["start"])
    hash_a = hashlib.sha256(Path(rom_a).read_bytes()).hexdigest() if rom_a and Path(rom_a).is_file() else None
    hash_b = hashlib.sha256(Path(rom_b).read_bytes()).hexdigest() if rom_b and Path(rom_b).is_file() else None
    suite.check(
        "O3",
        "Both owners build genuine distinct ROMs concurrently with the official compiler",
        bool(
            hash_a
            and hash_b
            and hash_a != hash_b
            and overlap > 0
            and structured(builds["A"]["response"]).get("builder") == "gb-studio-cli"
            and str(rom_a).startswith(str(suite.project_a))
            and str(rom_b).startswith(str(suite.project_b))
        ),
        rom_a=rom_a,
        rom_b=rom_b,
        sha256_a=hash_a,
        sha256_b=hash_b,
        overlap_seconds=round(overlap, 2),
        seconds_a=round(builds["A"]["end"] - builds["A"]["start"], 2),
        seconds_b=round(builds["B"]["end"] - builds["B"]["start"], 2),
    )

    plain = structured(builds["A"]["response"])
    build_output.check(suite, client_b, plain)
    live_1 = client_a.call(OWNER_A, "rom_build", {}, policy={"live_player": True})
    live_1["played"] = played_hash(suite.project_a)
    live_2 = client_a.call(OWNER_A, "rom_build", {}, policy={"live_player": True})
    live_2["played"] = played_hash(suite.project_a)
    player_1, player_2 = live_1.get("player") or {}, live_2.get("player") or {}
    served = None
    if player_1.get("url"):
        try:
            with urllib.request.urlopen(player_1["url"], timeout=10) as page:
                served = page.status
        except OSError as error:
            served = str(error)
    suite.check(
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
    suite.check(
        "V2",
        "After each live build the playable copy plays the very ROM that build made, byte for byte",
        all(
            live["played"] and live["played"] == (structured(live).get("rom") or {}).get("sha256")
            for live in (live_1, live_2)
        ),
        built=[(structured(live).get("rom") or {}).get("sha256") for live in (live_1, live_2)],
        played=[live["played"] for live in (live_1, live_2)],
    )
    client_a.call(OWNER_A, "web_preview_close", {})
    check_rom_after_restart(suite, client_b)
    # A and B were rebuilt, and every build has its own save signature: later checks use these ROMs.
    hash_a = hashlib.sha256(Path(rom_a).read_bytes()).hexdigest()
    hash_b = hashlib.sha256(Path(rom_b).read_bytes()).hexdigest()
    return rom_a, rom_b, hash_a, hash_b


def check_rom_after_restart(suite, client_b):
    """A build's ROM is still the one the playable copy plays when another worker makes the copy. On B, whose worker
    no later check pins."""
    built = structured(client_b.call(OWNER_B, "rom_build", {}))  # the live player off: no copy is made now
    os.kill(client_b.call(OWNER_B, "session_status")["lane"]["engine_pid"], signal.SIGKILL)
    time.sleep(1.0)
    opened = structured(client_b.call(OWNER_B, "web_preview", {}))
    played = played_hash(suite.project_b)
    suite.check(
        "V3",
        "A worker started after a build still plays that build's ROM in the playable copy",
        opened.get("success") is not False and played is not None and played == (built.get("rom") or {}).get("sha256"),
        built=(built.get("rom") or {}).get("sha256"),
        played=played,
        error=built.get("error") or opened.get("error"),
    )
    client_b.call(OWNER_B, "web_preview_close", {})

    # GB Studio compiles the web copy without batteryless saves on purpose: that copy keeps its own ROM.
    settings = suite.project_b / "project" / "settings.gbsres"
    saved = settings.read_text()
    settings.write_text(json.dumps({**json.loads(saved), "batterylessEnabled": True}, indent=2))
    try:
        batteryless = structured(client_b.call(OWNER_B, "rom_build", {}))
        opened = structured(client_b.call(OWNER_B, "web_preview", {}))
        played = played_hash(suite.project_b)
        suite.check(
            "V4",
            "With batteryless saves on, the playable copy keeps GB Studio's own web compile",
            batteryless.get("success") is not False
            and opened.get("success") is not False
            and played is not None
            and played != (batteryless.get("rom") or {}).get("sha256"),
            built=(batteryless.get("rom") or {}).get("sha256"),
            played=played,
        )
        client_b.call(OWNER_B, "web_preview_close", {})
    finally:
        settings.write_text(saved)


def check_emulators(suite, client_a, client_b, rom_a, rom_b, hash_a, hash_b):
    client_a.call(OWNER_A, "emulator_run", {"romPath": rom_a})
    step_a = client_a.call(
        OWNER_A, "emulator_step", {"buttons": ["right"], "frames": 45, "sampleCount": 3, "detail": "full"}
    )
    blocks = [b for b in step_a["result"].get("content", []) if b.get("type") == "image"]
    infos = [png_info(b) for b in blocks]
    samples = structured(step_a).get("samples", [])
    suite.check(
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
    frame_dir = suite.work / "frames"
    frame_dir.mkdir()
    for index, block in enumerate(blocks):
        (frame_dir / f"A-step-{index}.png").write_bytes(base64.b64decode(block["data"]))
    last_frame = check_input_list(suite, client_a, structured(step_a).get("frame"))

    status_b0 = client_b.call(OWNER_B, "session_status")
    run_b = client_b.call(OWNER_B, "emulator_run", {"romPath": rom_b})
    step_b = client_b.call(OWNER_B, "emulator_step", {"buttons": ["down"], "frames": 200, "sampleCount": 1})
    cross = client_b.call(OWNER_B, "emulator_run", {"romPath": rom_a})  # B asks for A's ROM path
    status_a = client_a.call(OWNER_A, "emulator_status")
    sess_a = client_a.call(OWNER_A, "session_status")
    suite.check(
        "O4",
        "B's emulator work never advances, restarts or re-selects A's session",
        structured(status_b0).get("emulatorActive") is False
        and structured(run_b).get("romSha256") == hash_b
        and structured(step_b).get("frame", 0) >= 200
        and structured(status_a).get("frame") == last_frame
        and structured(status_a).get("romSha256") == hash_a
        and structured(status_a).get("activeButtons") == ["right"]
        and structured(sess_a).get("projectRoot") == str(suite.project_a),
        a_frame_after_own_step=last_frame,
        a_frame_after_b_activity=structured(status_a).get("frame"),
        b_frame=structured(step_b).get("frame"),
        b_request_for_a_rom={
            "isError": cross["result"].get("isError") if cross.get("ok") else None,
            "structured": structured(cross) if cross.get("ok") else cross,
        },
    )
    suite.observations["b_request_for_a_rom_path"] = (
        "engine refused" if cross.get("ok") and cross["result"].get("isError") else "see O4 detail"
    )
    return last_frame


def check_input_list(suite, client_a, start):
    """Press, wait and press again in one call: a compact result, samples where asked, enlarged images."""
    inputs = [
        {"buttons": ["a"], "frames": 2},
        {"buttons": [], "frames": 10, "sample": True},
        {"buttons": ["a"], "frames": 2},
        {"buttons": ["right"], "frames": 3},
    ]
    step = client_a.call(OWNER_A, "emulator_step", {"inputs": inputs, "scale": 2})
    result = structured(step)
    infos = [png_info(b) for b in step["result"].get("content", []) if b.get("type") == "image"]
    samples = result.get("samples", [])
    suite.check(
        "M4",
        "One inputs list plays every input in order and returns a compact result with enlarged samples",
        not step["result"].get("isError")
        and result.get("frame") == start + 17
        and result.get("activeButtons") == ["right"]
        and [(s.get("frame"), s.get("inputIndex")) for s in samples] == [(start + 12, 1), (start + 17, 3)]
        and [(i["width"], i["height"]) for i in infos] == [(320, 288), (320, 288)]
        and not {"romSha256", "runtime", "execution", "recording"} & set(result),
        frame=result.get("frame"),
        samples=samples,
        images=infos,
        keys=sorted(result),
    )
    return result.get("frame")


def check_result_fidelity(suite, client_a, rom_a):
    via_broker = client_a.call(OWNER_A, "rom_inspect", {"romPath": rom_a})
    with EngineProcess(paths.ENGINE_ROOT, node=suite.node, client_name="chromatic-studio-acceptance-direct") as direct:
        direct.call_tool("project_select", {"projectPath": str(suite.project_a / "project.gbsproj")})
        direct_result = direct.call_tool("rom_inspect", {"romPath": rom_a})
        direct_error = direct.call_tool(
            "project_select", {"projectPath": str(suite.work / "missing" / "project.gbsproj")}
        )
    broker_error = client_a.call(
        OWNER_A, "project_select", {"projectPath": str(suite.work / "missing" / "project.gbsproj")}
    )
    suite.check(
        "M2",
        "Broker returns byte-equivalent raw results, including a structured engine error",
        via_broker["result"] == direct_result
        and broker_error["result"] == direct_error
        and broker_error["result"].get("isError") is True
        and bool(structured(broker_error).get("code")),
        error_code=structured(broker_error).get("code"),
        result_keys=sorted(via_broker["result"].keys()),
    )
    sess_a2 = client_a.call(OWNER_A, "session_status")
    suite.check(
        "M3",
        "A failed select leaves the previous selection and writer lease intact",
        structured(sess_a2).get("projectRoot") == str(suite.project_a) and sess_a2["lane"]["writer"] is True,
        lane=sess_a2["lane"],
    )


def check_owner_identity(suite, client_a, client_b, first_status):
    spoof = client_b.call(OWNER_B, "session_status", {"conversation_id": "conv-A"})
    sess_b = client_b.call(OWNER_B, "session_status")
    suite.check(
        "I2",
        "Identity placed in tool arguments is rejected by the schema and never reroutes",
        spoof["result"].get("isError") is True
        and spoof["lane"]["owner_key"] == sess_b["lane"]["owner_key"]
        and structured(sess_b).get("projectRoot") == str(suite.project_b),
        engine_message=spoof["result"]["content"][0].get("text", "")[:200],
    )

    rot = client_a.call(OWNER_A, "session_status", origin={"session_id": "sess-A-2-after-compaction"})
    suite.check(
        "I3",
        "A rotated runtime session id maps to the same worker, selection and emulator",
        rot["lane"]["engine_pid"] == first_status["lane"]["engine_pid"]
        and rot["lane"]["engine_generation"] == first_status["lane"]["engine_generation"]
        and structured(rot).get("projectRoot") == str(suite.project_a)
        and structured(rot).get("emulatorActive") is True
        and rot["lane"]["sessions_seen"] == ["sess-A-1", "sess-A-2-after-compaction"],
        lane=rot["lane"],
        note="session ids simulated here; real compaction is layer 2",
    )
