"""Source-mode debugging on the real engine: live state read from the running game."""

import json
from pathlib import Path

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
