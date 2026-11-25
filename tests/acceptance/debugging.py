"""Source-mode debugging on the real engine: live state read from the running game."""

import json
from pathlib import Path

from tests.acceptance.checkpoints import SMALL
from tests.acceptance.fixture import OWNER_B, structured

MENU = {
    "id": "acceptance-live-menu",
    "command": "EVENT_MENU",
    "args": {
        "variable": "0",
        "items": 2,
        "option1": "YES",
        "option2": "NO",
        "layout": "menu",
        "cancelOnLastOption": False,
        "cancelOnB": True,
    },
}


def author_scene(client_b):
    """Give B's start scene two actors on one tile, a text box and then a menu that stores its choice in "Oil"."""

    def call(tool, args=None):
        return structured(client_b.call(OWNER_B, tool, args or {}))

    inventory = call("project_inventory")
    # The scene the game starts in: earlier stages add scenes of their own to B.
    scene = call("project_inspect")["settings"]["startSceneId"]
    sprite = next(asset["id"] for asset in inventory["assets"] if asset.get("type") == "sprite")
    revision = call("variable_inspect")["revision"]
    for variable_id, name, symbol in (("0", "Oil", "var_lantern_oil"), ("1", "Fuel", "var_oil")):
        revision = call(
            "variable_set", {"variableId": variable_id, "name": name, "symbol": symbol, "expectedRevision": revision}
        )["revision"]
    for name, direction in (("Guide", "left"), ("Twin", "right")):
        call(
            "actor_create",
            {"sceneId": scene, "name": name, "x": 4, "y": 6, "direction": direction, "spriteSheetId": sprite},
        )
    call("dialogue_update", {"sceneId": scene, "text": "Hi"})
    script = call("script_inspect", {"target": {"sceneId": scene}})
    edit = call(
        "script_edit",
        {"action": "insert", "target": {"sceneId": scene}, "expectedRevision": script["revision"], "event": MENU},
    )
    return edit.get("event", {}).get("id") == MENU["id"]


def debug(client_b, **query):
    return structured(client_b.call(OWNER_B, "emulator_debug", {"referenceLimit": 0, "variableIds": [], **query}))


def ui(result):
    return (result.get("live") or {}).get("ui") or {}


def step(client_b, *inputs):
    client_b.call(
        OWNER_B, "emulator_step", {"inputs": [{"buttons": buttons, "frames": frames} for buttons, frames in inputs]}
    )


def until_dialogue(client_b, dialogue, **query):
    """Step four frames at a time (at most 40 times) until the dialogue is in the given state."""
    for _ in range(40):
        result = debug(client_b, **query)
        if ui(result).get("dialogue") == dialogue:
            break
        step(client_b, ([], 4))
    return result


def check_live_state(suite, client_b):
    """A build run as it comes (debug artifacts and source mode are the defaults) reports live actors, the text box
    and menu that own input, and the player walking once they close. On B, which no later check plays."""
    authored = author_scene(client_b)
    built = structured(client_b.call(OWNER_B, "rom_build", {"detail": "full"}))
    client_b.call(OWNER_B, "emulator_run", {"romPath": built.get("outputPath"), "restart": True, "initialFrames": 120})
    text = until_dialogue(client_b, "waiting", actors="all", variableNames=["oil", "LANTERN_OIL"])
    step(client_b, (["a"], 2), ([], 1))
    menu = until_dialogue(client_b, "menu", actors=["guide"])
    step(client_b, (["down", "a"], 1))
    down_and_a = debug(client_b)
    step(client_b, ([], 10), (["a"], 1))
    chosen = debug(client_b)
    step(client_b, ([], 30), (["right"], 20))
    walking = debug(client_b, actors="all")
    unknown = client_b.call(OWNER_B, "emulator_debug", {"variableNames": ["no such variable"]})
    # Earlier stages may have placed their own actors in B's start scene; this check is about its two.
    actors = {
        actor.get("name"): actor
        for actor in (text.get("live") or {}).get("actors") or []
        if actor.get("name") in ("Guide", "Twin")
    }
    player = (walking.get("live") or {}).get("player") or {}
    suite.check(
        "M9",
        "A source-mode debug read maps both actors on one tile to their own slots, reports the text box and then the "
        "menu as owning input (Down with A keeps the menu open), and the player walking once they close",
        authored
        and (built.get("debugArtifacts") or {}).get("liveStateLayout") == "gbstudio-4.3.0-e1-live-v2"
        and {name: (actor.get("x"), actor.get("y"), actor.get("direction")) for name, actor in actors.items()}
        == {"Guide": (4, 6, "left"), "Twin": (4, 6, "right")}
        and ui(text) == {"overlayOpen": True, "dialogue": "waiting", "waitingForInput": True, "buttons": ["a"]}
        and [variable.get("symbol") for variable in text.get("variables") or []] == ["var_lantern_oil"]
        and ui(menu).get("menuOptions") == 2
        and ui(menu).get("buttons") == ["a", "b"]
        and [actor.get("name") for actor in (menu.get("live") or {}).get("actors") or []] == ["Guide"]
        and ui(down_and_a).get("dialogue") == "menu"
        and ui(chosen).get("waitingForInput") is False
        and ui(chosen).get("dialogue") != "menu"
        and player.get("direction") == "right"
        and player.get("moving") is True
        and (walking.get("live") or {}).get("sceneLoading") is False
        and ui(walking) == {"overlayOpen": False, "dialogue": "none", "waitingForInput": False, "buttons": []}
        and (walking.get("live") or {}).get("scripts") == {"running": 0, "locked": False}
        and unknown["result"].get("isError") is True
        and "Authored variables: Oil (ID 0), Fuel (ID 1)" in str(structured(unknown).get("error")),
        text=text.get("live"),
        menu=menu.get("live"),
        down_and_a=down_and_a.get("live"),
        chosen=chosen.get("live"),
        walking=walking.get("live"),
        error=text.get("error") or walking.get("error") or structured(unknown).get("error"),
    )


def run(client_b, build_arguments):
    built = structured(client_b.call(OWNER_B, "rom_build", build_arguments))
    started = structured(
        client_b.call(
            OWNER_B, "emulator_run", {"romPath": built.get("outputPath"), "restart": True, "initialFrames": 120}
        )
    )
    return built, started


def check_debug_defaults(suite, client_b):
    """A build captures debug artifacts unless told not to, emulator_run picks source mode for it by itself, and the
    build and debug results stay short unless asked for in full."""
    built, started = run(client_b, {})
    compact, full = debug(client_b), debug(client_b, detail="full")
    plain, plain_started = run(client_b, {"captureDebugArtifacts": False})
    refused = client_b.call(OWNER_B, "emulator_debug", {})
    suite.check(
        "M16",
        "A default build reports only its debug folder and that source debugging is available, emulator_run starts it "
        "in source mode, a debug read leaves out the build identity and standing limitations until detail:'full', and "
        "captureDebugArtifacts:false gives a ROM-only run",
        set(built.get("debugArtifacts") or {}) == {"directory"}
        and Path(built["debugArtifacts"]["directory"], "symbols.noi").is_file()
        and built.get("sourceDebug") == {"available": True}
        and started.get("debugMode") == "source"
        and "sourceDebug" not in started
        and compact.get("mode") == "source"
        and not {"identity", "limitations"} & set(compact)
        and compact.get("references") == []
        and (full.get("identity") or {}).get("romSha256") == started.get("romSha256")
        and len(full.get("limitations") or []) >= 1
        and len(json.dumps(compact)) < len(json.dumps(full))
        and not {"debugArtifacts", "sourceDebug"} & set(plain)
        and plain_started.get("debugMode") == "rom"
        and refused["result"].get("isError") is True
        and structured(refused).get("code") == "SOURCE_DEBUG_DISABLED",
        built={key: built.get(key) for key in ("debugArtifacts", "sourceDebug", "error")},
        started={key: started.get(key) for key in ("debugMode", "sourceDebug", "error")},
        compact_keys=sorted(compact),
        full_keys=sorted(full),
        compact_bytes=len(json.dumps(compact)),
        full_bytes=len(json.dumps(full)),
        plain_keys=sorted(plain),
        plain_mode=plain_started.get("debugMode"),
        refused=structured(refused),
    )


def recorded_menu_step(client_b, rom):
    """On a recorded run, a multi-input step whose last input closes the menu, read by the step and then paused; a
    debug read that fails on a neutral step, then a checkpoint; and the single form with variableIds and no scene."""
    client_b.call(OWNER_B, "emulator_run", {"romPath": rom, "restart": True, "initialFrames": 120, "recording": SMALL})
    until_dialogue(client_b, "waiting")
    step(client_b, (["a"], 2), ([], 1))
    menu = until_dialogue(client_b, "menu")
    closing = client_b.call(
        OWNER_B,
        "emulator_step",
        {
            "inputs": [{"buttons": [], "frames": 10}, {"buttons": ["a"], "frames": 1}],
            "debug": {"variableNames": ["oil"]},
        },
    )
    paused = debug(client_b, variableNames=["oil"])
    observed = structured(client_b.call(OWNER_B, "emulator_observe", {"includeImages": False}))
    failed = structured(
        client_b.call(
            OWNER_B,
            "emulator_step",
            {"buttons": [], "frames": 1, "includeImages": False, "debug": {"actors": ["nobody"]}},
        )
    )
    checkpoint = structured(client_b.call(OWNER_B, "emulator_checkpoint", {"action": "save"}))
    single = structured(
        client_b.call(
            OWNER_B,
            "emulator_step",
            {
                "buttons": [],
                "frames": 1,
                "includeImages": False,
                "debug": {"variableIds": ["0"], "includeScene": False},
            },
        )
    )
    return {
        "menu": ui(menu).get("dialogue"),
        "closing": structured(closing),
        "images": [item for item in closing["result"].get("content") or [] if item.get("type") == "image"],
        "paused": paused,
        "observed": observed.get("samples") or [],
        "failed": failed,
        "checkpoint": checkpoint,
        "single": single,
    }


def recorded_menu_step_ok(recorded):
    closing, paused, single = recorded["closing"], recorded["paused"], recorded["single"]
    state, span = closing.get("debug") or {}, closing.get("recordingSpan") or {}
    last = (closing.get("samples") or [{}])[-1]
    oil = [{key: variable.get(key) for key in ("id", "name", "value")} for variable in paused.get("variables") or []]
    return (
        recorded["menu"] == "menu"
        and ui(state).get("dialogue") not in (None, "menu")
        and state.get("live") == paused.get("live")
        and state.get("variables") == oil
        and closing.get("frame") == paused.get("frame") == last.get("frame")
        and len(recorded["images"]) == 1
        and [sample.get("sha256") for sample in recorded["observed"]] == [last.get("sha256")]
        and span.get("toFrame") == closing.get("frame")
        and span.get("fromFrame") == closing.get("frame") - 11
        and span.get("toActionIndex", 0) > span.get("fromActionIndex", 0)
        and "session" not in closing
        and (recorded["failed"].get("debug") or {}).get("code") == "SOURCE_DEBUG_ACTOR_UNAVAILABLE"
        and recorded["failed"].get("advancedFrames") == 1
        and bool(recorded["checkpoint"].get("checkpointId"))
        and set(single.get("debug") or {}) == {"live", "variables"}
        and [variable.get("id") for variable in single["debug"]["variables"]] == ["0"]
    )


def largest_step(client_b):
    """The largest step result a debug request can ask for: 64 inputs and 8 samples in full detail, every actor and up
    to 32 named variables (those the build allocates), without images."""
    variables = structured(client_b.call(OWNER_B, "emulator_debug", {"referenceLimit": 0})).get("variables") or []
    inputs = [{"buttons": [], "frames": 1, **({"sample": True} if index % 8 == 7 else {})} for index in range(64)]
    return structured(
        client_b.call(
            OWNER_B,
            "emulator_step",
            {
                "inputs": inputs,
                "detail": "full",
                "includeImages": False,
                "debug": {"actors": "all", "variableIds": [variable["id"] for variable in variables][:32]},
            },
        )
    )


def check_step_live_state(suite, client_b):
    """A step's debug request returns, on its last frame, the live state emulator_debug reads there, in less than the
    step and a separate debug read take together; a refusal is data in the step's result, which still ran. Starts on
    the ROM-only run check_debug_defaults left."""
    query = {"actors": "all", "variableNames": ["oil"]}
    step_args = {"inputs": [{"buttons": [], "frames": 2}], "includeImages": False}
    rom_only = client_b.call(OWNER_B, "emulator_step", {**step_args, "debug": {}})
    built, _ = run(client_b, {})
    plain = client_b.call(OWNER_B, "emulator_step", step_args)
    stepped = client_b.call(OWNER_B, "emulator_step", {**step_args, "debug": query})
    read = client_b.call(OWNER_B, "emulator_debug", {**query, "referenceLimit": 0})
    default = structured(client_b.call(OWNER_B, "emulator_step", {**step_args, "debug": {}}))
    unknown = client_b.call(OWNER_B, "emulator_step", {**step_args, "debug": {"actors": ["nobody"]}})
    largest = largest_step(client_b)
    recorded = recorded_menu_step(client_b, built.get("outputPath"))
    with_debug, debugged = structured(stepped), structured(read)
    live_state = with_debug.get("debug") or {}
    bytes_of = {
        name: len(json.dumps(structured(result))) for name, result in (("step", plain), ("step_debug", stepped))
    }
    bytes_of["debug"] = len(json.dumps(debugged))
    bytes_of["largest"] = len(json.dumps(largest))
    suite.observations["step_live_state_bytes"] = bytes_of
    suite.check(
        "M24",
        "emulator_step with debug returns the live player, ui, scene, actors and named variables emulator_debug reads "
        "on the same frame, compactly; debug:{} names no variables; an unknown actor or a ROM-only session is reported "
        "in debug and the step still advanced; on a recording, a multi-input step whose last input closes the menu "
        "reads what a paused read then reads, with its image and recordingSpan, a failed read leaves a checkpoint "
        "possible, the single form takes variableIds without the scene, and the largest result stays under 32 KiB",
        live_state.get("live") == debugged.get("live")
        and (live_state.get("live") or {}).get("player") is not None
        and live_state.get("scene") == {key: (debugged.get("scene") or {}).get(key) for key in ("id", "name", "type")}
        and live_state.get("variables")
        == [{key: variable.get(key) for key in ("id", "name", "value")} for variable in debugged.get("variables") or []]
        and [variable.get("name") for variable in live_state.get("variables") or []] == ["Oil"]
        and debugged.get("frame") == with_debug.get("frame") == (structured(plain).get("frame") or 0) + 2
        and bytes_of["step_debug"] < bytes_of["step"] + bytes_of["debug"]
        and "variables" not in (default.get("debug") or {})
        and {"live", "scene"} <= set(default.get("debug") or {})
        and unknown["result"].get("isError") is not True
        and (structured(unknown).get("debug") or {}).get("code") == "SOURCE_DEBUG_ACTOR_UNAVAILABLE"
        and structured(unknown).get("advancedFrames") == 2
        and rom_only["result"].get("isError") is not True
        and (structured(rom_only).get("debug") or {}).get("code") == "SOURCE_DEBUG_DISABLED"
        and structured(rom_only).get("advancedFrames") == 2
        and recorded_menu_step_ok(recorded)
        and "error" not in (largest.get("debug") or {})
        and bytes_of["largest"] < 32 * 1024,
        step_debug=live_state,
        debug={key: debugged.get(key) for key in ("frame", "scene", "live", "variables", "error")},
        default=default.get("debug"),
        unknown=structured(unknown).get("debug") or structured(unknown),
        rom_only=structured(rom_only).get("debug") or structured(rom_only),
        bytes=bytes_of,
        recorded={key: value for key, value in recorded.items() if key != "images"},
        largest_debug=largest.get("debug"),
    )


def check_debug_fallbacks(suite, client_b):
    """Source debugging that was only a default never costs a run: a default build whose debug folder cannot be written
    still succeeds and says why, a ROM path through a symbolic link starts in source mode, and a replay after the
    source changed runs in ROM mode and says why."""
    built, _ = run(client_b, {})
    rom = Path(built["outputPath"])
    folder = Path(built["debugArtifacts"]["directory"])
    # Read-only, so no capture can write there.
    folder.chmod(0o500)
    try:
        blocked = structured(client_b.call(OWNER_B, "rom_build", {}))
        required = structured(client_b.call(OWNER_B, "rom_build", {"captureDebugArtifacts": True}))
    finally:
        folder.chmod(0o700)
    rebuilt, _ = run(client_b, {})
    link = suite.work / "linked-build"
    link.symlink_to(rom.parent, target_is_directory=True)
    linked = structured(
        client_b.call(
            OWNER_B,
            "emulator_run",
            {"romPath": str(link / rom.name), "restart": True, "initialFrames": 60, "recording": {}},
        )
    )
    client_b.call(OWNER_B, "emulator_step", {"inputs": [{"buttons": [], "frames": 30}]})
    revision = structured(client_b.call(OWNER_B, "variable_inspect", {}))["revision"]
    client_b.call(OWNER_B, "variable_set", {"variableId": "1", "name": "Spare", "expectedRevision": revision})
    replayed = structured(client_b.call(OWNER_B, "emulator_replay", {"romPath": str(rom), "includeImages": False}))
    suite.check(
        "M17",
        "A default build whose debug folder cannot be written still succeeds and reports why source debugging is off (an "
        "explicit captureDebugArtifacts:true fails), emulator_run through a symbolic link starts the ROM in source "
        "mode, and a replay after a source edit runs in ROM mode with the stale-source reason",
        blocked.get("success") is True
        and "debugArtifacts" not in blocked
        and (blocked.get("sourceDebug") or {}).get("available") is False
        and "No debug artifacts were captured" in str((blocked.get("sourceDebug") or {}).get("reason"))
        and required.get("success") is False
        and rebuilt.get("sourceDebug") == {"available": True}
        and linked.get("debugMode") == "source"
        and replayed.get("debugMode") == "rom"
        and (replayed.get("sourceDebug") or {}).get("code") == "SOURCE_DEBUG_STALE_SOURCE",
        blocked={key: blocked.get(key) for key in ("success", "debugArtifacts", "sourceDebug", "error")},
        required={key: required.get(key) for key in ("success", "stderr", "error")},
        rebuilt=rebuilt.get("sourceDebug"),
        linked={key: linked.get(key) for key in ("debugMode", "sourceDebug", "error")},
        replayed={key: replayed.get(key) for key in ("debugMode", "sourceDebug", "error")},
    )
