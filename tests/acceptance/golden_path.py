"""The golden path: one game made from a blank project to a presented build with its report, by a studio chat's
tools and tool hooks as Hermes runs them (tests/acceptance/studio.py; no model). Each step is one function and one
check, in the order of the studio's workflow (backend/hermes/workflow.py); a tool or gate that joins the pipeline
joins it here, as a step of its own or in the step that uses it. A call that does not reach its tool fails its
step's check with the tool, code and error, and ends the path there: every later step depends on it."""

import json
from pathlib import Path

from backend import library
from backend.hermes import host
from backend.history import snapshots
from backend.library import layout, plan_checks
from tests.acceptance.art import coin
from tests.acceptance.audio import wav
from tests.acceptance.studio import Stopped, step, studio_chat
from tests.support import encode_png

CHAT = {"conversation_id": "golden-chat", "session_id": "golden-session", "task_id": "golden-task"}
DOOR = "golden-door"
SONG = {
    "assetPath": "assets/music/golden.uge",
    "name": "Golden",
    "sections": [{"name": "A", "pulse1": "C5:4 E5:4 G5:8", "pulse2": "E4:8 G4:8", "wave": "C3:8 G2:8"}],
}
PLAN = """# Test plan

## Checks

| ID | Given | When | Then | Evidence kind | Status |
|---|---|---|---|---|---|
| T1 | the start scene | the player walks right into the door | the goal scene shows | PyBoy frames | not run |
| F1 | power-on of the exact ROM the user gets | the game is played to its ending in one run | the ending shows | PyBoy frames (one recording from a fresh boot, named as the report's finishRun) | not run |
"""
# Frames from power-on before the route starts, as the route was measured (emulator_run's default, given so the route
# does not move with it).
BOOT_FRAMES = 120
# Walk right from the start tile into the door two tiles away, then wait out the fade into the goal scene.
ROUTE = [{"buttons": ["right"], "frames": 40}, {"buttons": [], "frames": 90}]


def check_golden_path(suite):
    """The steps, in order, in one chat (with a worker of its own)."""
    root = suite.work / "golden"
    with studio_chat(suite, CHAT) as studio:
        try:
            create(suite, studio, root)
            sprite = import_art(suite, studio, root)
            song, chime = import_audio(suite, studio, root)
            author(suite, studio, root, sprite, song, chime)
            first = build(suite, studio, root)
            played = play(suite, studio, first)
            finish = replay_on_rebuild(suite, studio, root, first, played)
            check_audio(suite, studio)
            present(suite, studio, root)
            report(suite, studio, root, played, finish)
        except Stopped:
            pass
        finally:
            studio.call("chromatic_emulator_close")
    suite.observations["golden_path_calls"] = studio.calls


@step(
    "GP1",
    "Golden path, create: a blank project made by the chat's tool is selected, in the game layout and in the library, "
    "with the chat linked",
)
def create(check, studio, root):
    made = studio.engine(
        "chromatic_project_create_blank",
        {
            "name": "Golden Path",
            "destinationPath": str(root),
            "gameType": "TOPDOWN",
            "colorMode": "color",
            "select": True,
        },
    )
    (root / plan_checks.PLAN_FILE).parent.mkdir(parents=True, exist_ok=True)
    (root / plan_checks.PLAN_FILE).write_text(PLAN)  # the agent's own file write, as game-planning has it
    entry = host._registry().get(library.game_id(root)) or {}
    plan = plan_checks.read_plan(root)
    check(
        not made.get("isError")
        and studio.engine("chromatic_session_status").get("projectRoot") == str(root)
        and layout.check(root)["ok"]
        and (entry.get("chat") or {}).get("conversationId") == CHAT["conversation_id"]
        and plan is not None
        and plan.checks == ["T1", "F1"],
        made=made.get("error") or made.get("projectRoot"),
        chat=entry.get("chat"),
    )


@step("GP2", "Golden path, art: a drawn sprite imports with its palette slot")
def import_art(check, studio, root):
    (root / "art").mkdir()
    (root / "art" / "door.png").write_bytes(encode_png(16, 16, coin))
    imported = studio.engine(
        "chromatic_asset_import",
        {
            "assetPath": "assets/sprites/door.png",
            "kind": "sprite",
            "sourcePath": "art/door.png",
            "sprite": {"profile": "static", "paletteIndex": 2},
        },
    )
    sidecar_path = root / "assets/sprites/door.png.gbsres"
    sidecar = json.loads(sidecar_path.read_text()) if sidecar_path.is_file() else {}
    slots = {
        tile.get("paletteIndex")
        for state in sidecar.get("states", [])
        for animation in state.get("animations", [])
        for frame in animation.get("frames", [])
        for tile in frame.get("tiles", [])
    }
    check(
        imported.get("paletteIndex") == 2 and imported.get("analysis", {}).get("status") == "valid" and slots == {2},
        imported=imported.get("error") or imported.get("analysis"),
        slots=sorted(slots, key=str),
    )
    return imported.get("id")


@step(
    "GP3",
    "Golden path, audio: a song composed from note lists and an imported sound effect, each with how to play it",
)
def import_audio(check, studio, root):
    song = studio.engine("chromatic_music_compose", SONG)
    (root / "sounds").mkdir()
    (root / "sounds" / "chime.wav").write_bytes(wav(0.25))
    chime = studio.engine(
        "chromatic_asset_import",
        {"assetPath": "assets/sounds/chime.wav", "kind": "sound", "sourcePath": "sounds/chime.wav"},
    )
    check(
        song.get("kind") == "music"
        and (song.get("playEvent") or {}).get("command") == "EVENT_MUSIC_PLAY"
        and chime.get("kind") == "sound"
        and bool(chime.get("playEvent")),
        song=song.get("error") or song.get("playEvent"),
        chime=chime.get("error") or chime.get("playEvent"),
    )
    return song, chime


@step(
    "GP4",
    "Golden path, scenes: a second scene, and each scene's edits applied from an operations file in the game, read "
    "back: the door actor wears the imported sprite and the goal scene's script plays the chime",
)
def author(check, studio, root, sprite, song, chime):
    """The start scene plays the song and has a door two tiles right of the player that leads to the goal scene,
    which plays the chime: each scene's edits in an operations file in the game's scratch/ folder."""
    settings = studio.engine("chromatic_project_inspect")["settings"]
    start, x, y = settings["startSceneId"], settings["startX"], settings["startY"]
    background = studio.engine("chromatic_project_inventory")["scenes"][0]["backgroundId"]
    goal = studio.engine("chromatic_scene_create", {"name": "Goal", "backgroundId": background}).get("scene") or {}
    operations = {
        start: [
            {"type": "script.edit", "action": "insert", "target": {"sceneId": start}, "index": 0,
             "event": {"id": "golden-music", **song.get("playEvent", {})}},
            {"type": "trigger.create", "id": DOOR, "name": "Door", "x": x + 2, "y": y, "width": 1, "height": 1},
            {"type": "scene.transition", "target": {"sceneId": start, "triggerId": DOOR},
             "destinationSceneId": goal.get("id"), "x": 2, "y": 2, "direction": "down"},
            # Past the door, so it never stands in the player's way.
            {"type": "actor.create", "name": "Door", "x": x + 4, "y": y, "spriteSheetId": sprite},
        ],
        goal.get("id"): [
            {"type": "script.edit", "action": "insert", "target": {"sceneId": goal.get("id")}, "index": 0,
             "event": {"id": "golden-chime", **chime.get("playEvent", {})}},
        ],
    }  # fmt: skip
    applied = {scene: apply(studio, root, scene, edits) for scene, edits in operations.items()}
    created = (applied[start].get("operationResults") or [{}])[-1].get("resourceId")
    door = studio.engine("chromatic_actor_inspect", {"sceneId": start, "actorId": created}).get("actor") or {}
    script = studio.engine("chromatic_script_inspect", {"target": {"sceneId": goal.get("id")}}).get("events") or []
    played = next((event for event in script if event.get("id") == "golden-chime"), {})
    expected = chime.get("playEvent") or {}
    check(
        bool(goal.get("id"))
        and all(
            not result.get("isError") and len(result.get("operationResults") or []) == len(operations[scene])
            for scene, result in applied.items()
        )
        and door.get("spriteSheetId") == sprite
        and played.get("command") == expected.get("command")
        and all((played.get("args") or {}).get(key) == value for key, value in (expected.get("args") or {}).items()),
        applied={scene: result.get("error") or result.get("changedPaths") for scene, result in applied.items()},
        door=door.get("spriteSheetId"),
        chime=played,
    )


def apply(studio, root, scene, operations):
    """``chromatic_scene_apply`` with its operations written to a file in the game's scratch/ folder first."""
    (root / "scratch").mkdir(exist_ok=True)
    (root / "scratch" / "ops.json").write_text(json.dumps({"operations": operations}))
    return studio.engine("chromatic_scene_apply", {"sceneId": scene, "operationsPath": "scratch/ops.json"})


@step(
    "GP5",
    "Golden path, build: the game's ROM builds where the game keeps it, with source debugging; the library records "
    "the build and the build hook keeps its snapshot",
)
def build(check, studio, root):
    built = studio.engine("chromatic_rom_build")
    rom = built.get("outputPath")
    game = library.game_id(root)
    entry = host._registry().get(game) or {}
    kept = snapshots.list_snapshots(host._data_dir() / "snapshots", game)
    check(
        built.get("success") is True
        and rom == str(root / library.canonical_rom(root))
        and bool(built.get("debugArtifacts"))
        and (entry.get("lastBuild") or {}).get("ok") is True
        and (entry.get("lastBuild") or {}).get("rom") == rom
        and len(kept) == 1,
        build=built.get("error") or built.get("diagnostics"),
        last_build=entry.get("lastBuild"),
        snapshots=len(kept),
    )
    return {"path": rom, "sha256": (built.get("rom") or {}).get("sha256")}


@step(
    "GP6",
    "Golden path, play: a recorded run from power-on walks the route given as one inputs list into the goal scene "
    "and is stopped as passed",
)
def play(check, studio, rom):
    """One recorded run from power-on, the route as one inputs list, stopped as passed once the goal scene shows:
    the finish run of this ROM."""
    booted = studio.engine(
        "chromatic_emulator_run",
        {"romPath": rom["path"], "restart": True, "initialFrames": BOOT_FRAMES, "recording": {}},
    )
    stepped = studio.engine("chromatic_emulator_step", {"inputs": ROUTE})
    there = studio.engine("chromatic_emulator_debug", {"includeScene": True, "variableIds": []})
    stopped = studio.engine("chromatic_emulator_recording", {"action": "stop", "outcome": "passed"})
    recording = (booted.get("recording") or {}).get("recordingPath")
    check(
        booted.get("romSha256") == rom["sha256"]
        and stepped.get("advancedFrames") == sum(item["frames"] for item in ROUTE)
        and (stepped.get("recordingSpan") or {}).get("recordingPath") == recording
        and scene_name(there) == "Goal"
        and bool(recording)
        and stopped.get("status") == "stopped",
        frame=stepped.get("frame"),
        scene=scene_name(there),
        player=(there.get("live") or {}).get("player"),
        stopped=stopped.get("error") or stopped.get("status"),
    )
    return {"recording": recording, "frame": stepped.get("frame")}


def scene_name(debugged: dict):
    return (debugged.get("scene") or {}).get("name")


@step(
    "GP7",
    "Golden path, rebuild: after a fix that changes nothing on screen, the recorded run replays onto the new ROM "
    "frame for frame and is recorded again there",
)
def replay_on_rebuild(check, studio, root, first, played):
    """A fix that changes nothing on screen (the door's name), a rebuild, and the recorded run replayed onto it:
    the replay is recorded as a run of its own, from power-on of the new ROM."""
    start = studio.engine("chromatic_project_inspect")["settings"]["startSceneId"]
    renamed = apply(studio, root, start, [{"type": "trigger.update", "triggerId": DOOR, "name": "Goal Door"}])
    rebuilt = studio.engine("chromatic_rom_build")
    rom = {"path": rebuilt.get("outputPath"), "sha256": (rebuilt.get("rom") or {}).get("sha256")}
    replayed = studio.engine(
        "chromatic_emulator_replay", {"romPath": rom["path"], "recordingPath": played["recording"]}
    )
    replay = replayed.get("replay") or {}
    check(
        not renamed.get("isError")
        and rebuilt.get("success") is True
        and rom["sha256"] not in (None, first["sha256"])
        and replayed.get("romSha256") == rom["sha256"]
        and replay.get("status") == "matched"
        and replay.get("coverage") == "every-frame"
        and (replay.get("source") or {}).get("recordingPath") == played["recording"]
        and replayed.get("frame") == played["frame"]
        and (replayed.get("recording") or {}).get("recordingPath") not in (None, played["recording"]),
        renamed=renamed.get("error"),
        roms=[first["sha256"], rom["sha256"]],
        replay=replay,
    )
    return (replayed.get("recording") or {}).get("recordingPath")


@step(
    "GP8",
    "Golden path, audio: at the end of the replayed run the sound hardware is on and playing the song, and the "
    "run is stopped as passed",
)
def check_audio(check, studio):
    """The song the start scene began still plays where the run ends; then the replayed run is stopped as passed."""
    audio = studio.engine("chromatic_emulator_audio")
    stopped = studio.engine("chromatic_emulator_recording", {"action": "stop", "outcome": "passed"})
    active = [channel.get("channel") for channel in audio.get("channels") or [] if channel.get("active")]
    check(
        audio.get("power") is True
        and audio.get("active") is True
        and len(active) >= 2
        and stopped.get("status") == "stopped",
        audio={key: audio.get(key) for key in ("frame", "active", "power", "error")},
        active=active,
        stopped=stopped.get("error") or stopped.get("status"),
    )


@step(
    "GP9",
    "Golden path, present: with the game card filled in, the fresh playable copy is shown to the user",
)
def present(check, studio, root):
    (root / "art" / "cover.png").write_bytes(encode_png(160, 144, cover))
    card = studio.call(
        "chromatic_game_info",
        {
            "title": "Golden Path",
            "tagline": "Walk through the door to win.",
            "description": "A one-room walk to a door, made to carry a game through every step of the studio.",
            "genres": ["Adventure"],
            "cover": "art/cover.png",
        },
    )
    shown = studio.call("chromatic_present_game", {"note": "Walk right."})
    entry = host._registry().get(library.game_id(root)) or {}
    check(
        card.get("ok") is True
        and shown.get("ok") is True
        and (shown.get("studio") or {}).get("playerUrl", "").endswith("/index.html")
        and (entry.get("presented") or {}).get("note") == "Walk right.",
        card=card.get("problems") or card.get("missing") or card.get("error"),
        shown=shown.get("error") or shown.get("studio"),
    )


def cover(x, y):
    return [(24, 40, 80, 255), (240, 200, 80, 255), (120, 200, 120, 255)][(x // 16 + y // 16) % 3]


@step(
    "GP10",
    "Golden path, report: the build report takes the replay on this ROM as its finish run, with every check of "
    "the test plan, and refuses the run recorded on the earlier ROM",
)
def report(check, studio, root, played, finish):
    """The report names the replay's recording as its finish run; the first run, made on the earlier ROM, is no
    finish run of this build."""
    card = {
        "title": "Golden Path",
        "summary": "A door that leads to the goal scene.",
        "changes": [{"kind": "added", "text": "The door and the goal scene.", "asset": "assets/sprites/door.png"}],
        "tested": ["Walked into the door from power-on."],
        "checks": [
            {"id": "T1", "text": "Walking into the door shows the goal scene.", "result": "passed"},
            {"id": "F1", "text": "Played from power-on to the goal scene.", "result": "passed"},
        ],
        "difficulty": "Under a second of walking right; nothing to tune.",
    }
    earlier = studio.call("chromatic_build_report", {**card, "finishRun": played["recording"]})
    reported = studio.call("chromatic_build_report", {**card, "finishRun": finish})
    run = (reported.get("report") or {}).get("finishRun") or {}
    check(
        earlier.get("code") == "INVALID_REPORT"
        and studio.outcomes[-2:] == [("chromatic_build_report", "error"), ("chromatic_build_report", "ok")]
        and "another ROM" in " ".join(earlier.get("problems") or [])
        and reported.get("ok") is True
        and reported.get("project") == str(root)
        and run.get("outcome") == "passed"
        and Path(run.get("recordingPath", "")) == Path(finish).resolve()
        and not reported.get("warnings"),
        earlier=earlier.get("problems"),
        outcomes=studio.outcomes[-2:],
        reported=reported.get("problems") or reported.get("warnings") or run,
    )
