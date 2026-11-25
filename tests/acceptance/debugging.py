"""Source-mode debugging on the real engine: live state read from the running game."""

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
    """A debug build run in source mode reports live actors, the text box and menu that own input, and the player
    walking once they close. On B, which no later check plays."""
    authored = author_scene(client_b)
    built = structured(client_b.call(OWNER_B, "rom_build", {"captureDebugArtifacts": True}))
    client_b.call(
        OWNER_B,
        "emulator_run",
        {"romPath": built.get("outputPath"), "restart": True, "initialFrames": 120, "debugMode": "source"},
    )
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
