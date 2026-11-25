"""Script events through the real engine: the event catalog against the toolchain's GB Studio, event_describe, the
authoring skill's cookbook recipes building in their places, and rom_build's authoring warnings."""

import importlib.util
import json
import re
from pathlib import Path

from tests.acceptance.fixture import OWNER_E, structured

ROOT = Path(__file__).resolve().parents[2]
COOKBOOK = ROOT / "skills" / "authoring" / "references" / "event-cookbook.md"
WARNINGS = {"TEXT_IN_LOGO_SCENE", "TEXT_VARIABLE_TOKEN", "ACTORS_OVER_MENU", "DEPRECATED_EVENT"}


def call(client, tool: str, arguments: dict | None = None) -> dict:
    response = client.call(OWNER_E, tool, arguments or {})
    result = response.get("result") or {}
    return {**structured(response), "failed": bool(result.get("isError"))}


def catalog_module():
    spec = importlib.util.spec_from_file_location("event_catalog", ROOT / "tools" / "engine" / "event_catalog.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recipes() -> dict[str, list[list[dict]]]:
    """The cookbook's event lists by section heading, in order."""
    sections = re.split(r"^## ", COOKBOOK.read_text(), flags=re.M)[1:]
    return {
        section.splitlines()[0]: [json.loads(block) for block in re.findall(r"```json\n(.*?)```", section, re.S)]
        for section in sections
    }


def check_events(suite, client):
    check_catalog(suite)
    check_describe(suite, client)
    root = suite.work / "projE"
    call(
        client,
        "project_create_blank",
        {
            "name": "E01 Events",
            "destinationPath": str(root),
            "gameType": "TOPDOWN",
            "colorMode": "color",
            "select": True,
        },
    )
    inventory = call(client, "project_inventory")
    start = inventory["scenes"][0]
    sprite = next(asset["id"] for asset in inventory["assets"] if asset["type"] == "sprite")
    clean = check_recipes(suite, client, start, sprite)
    check_warnings(suite, client, start, sprite, clean)


def check_catalog(suite):
    module = catalog_module()
    source = module.toolchain_gb_studio()
    if not (source / "src" / "lib" / "events").is_dir():
        suite.check(
            "C1",
            "The event catalog matches the toolchain's GB Studio",
            True,
            skipped=f"no GB Studio source at {source}",
        )
        return
    generated = module.generate(source)
    suite.check(
        "C1",
        "The event catalog matches the toolchain's GB Studio event definitions",
        generated == module.CATALOG.read_text(),
        source=str(source),
        generated_events=len(json.loads(generated)["events"]),
    )


def check_describe(suite, client):
    listing = call(client, "event_describe")  # before any project is selected: the catalog needs none
    described = call(
        client, "event_describe", {"events": ["EVENT_ACTOR_SET_DIRECTION", "EVENT_MENU", "EVENT_IF_VALUE"]}
    )
    sound = call(client, "event_describe", {"query": "play sound"})
    current = call(client, "event_describe", {"query": "if variable"})
    by_event = {entry["event"]: entry for entry in described.get("events", [])}
    direction = {field["key"]: field for field in by_event.get("EVENT_ACTOR_SET_DIRECTION", {}).get("fields", [])}
    menu = {field["key"]: field for field in by_event.get("EVENT_MENU", {}).get("fields", [])}
    suite.check(
        "C2",
        "event_describe lists categories with no project, describes events with typed args, defaults, allowed values, "
        "LOGO warnings, deprecation and an example, and searches current events",
        not listing["failed"]
        and listing.get("eventCount", 0) > 100
        and any(category["name"] == "Dialogue & Menus" for category in listing.get("categories", []))
        and direction.get("direction", {}).get("type") == "value"
        and by_event["EVENT_ACTOR_SET_DIRECTION"]["example"]["args"]["direction"]
        == {"type": "direction", "value": "up"}
        and menu.get("layout", {}).get("options") == ["dialogue", "menu"]
        and any("LOGO" in warning.get("sceneTypes", []) for warning in by_event["EVENT_MENU"].get("warnings", []))
        and by_event["EVENT_IF_VALUE"].get("deprecated") is True
        and by_event["EVENT_IF_VALUE"].get("replacement") == "EVENT_IF"
        and "value" in described.get("fieldTypes", {})
        and sound.get("matches", [{}])[0].get("event") == "EVENT_SOUND_PLAY_EFFECT"
        and all(not match.get("deprecated") for match in current.get("matches", []))
        and current.get("deprecatedHidden", 0) >= 1,
        listing=listing,
        described=json.dumps(described)[:1500],
        sound=sound,
        current=current,
    )


def insert(client, target: dict, events: list[dict]) -> list[dict]:
    return [call(client, "script_edit", {"action": "insert", "target": target, "event": event}) for event in events]


def check_recipes(suite, client, start, sprite) -> dict:
    """Every cookbook recipe in its place: the pickup in a collision-group actor, the hazard in the scene's hit script,
    the gated exit in a trigger with a scene switch in its branch, the rest in the scene's start script."""
    book = recipes()
    scene = {"sceneId": start["id"]}
    coin = call(
        client,
        "actor_create",
        {
            "sceneId": start["id"],
            "name": "Coin",
            "x": 4,
            "y": 4,
            "spriteSheetId": sprite,
            "properties": {"collisionGroup": "1"},
        },
    )["actor"]
    gate = call(client, "trigger_create", {"sceneId": start["id"], "name": "Gate", "x": 8, "y": 2})["trigger"]
    placed = {
        "Pickup": [{**scene, "actorId": coin["id"]}, {**scene, "actorId": coin["id"], "scriptKey": "startScript"}],
        "Hazard": [{**scene, "scriptKey": "playerHit2Script"}],
        "Gated exit with a counter": [{**scene, "triggerId": gate["id"]}],
    }
    results = []
    for heading, lists in book.items():
        targets = placed.get(heading, [scene] * len(lists))
        for target, events in zip(targets, lists, strict=True):
            results += insert(client, target, events)
    gate_if = next(
        result["event"]["id"]
        for result in results
        if result.get("event", {}).get("command") == "EVENT_IF" and "/triggers/" in result.get("resourcePath", "")
    )
    transition = call(
        client,
        "script_transition",
        {
            "target": {**scene, "triggerId": gate["id"], "branchPath": [{"eventId": gate_if, "branch": "true"}]},
            "destinationSceneId": start["id"],
            "x": 2,
            "y": 2,
            "direction": "down",
        },
    )
    built = call(client, "rom_build")
    warned = [item for item in built.get("diagnostics", []) if item.get("code") in WARNINGS]
    suite.check(
        "C3",
        "Every event-cookbook recipe inserts in its place and the project builds, with none of the authoring warnings",
        sum(len(lists) for lists in book.values()) >= 10
        and not any(result["failed"] for result in results)
        and not transition["failed"]
        and built.get("success") is True
        and not warned,
        recipes={heading: len(lists) for heading, lists in book.items()},
        failed=[result for result in results if result["failed"]][:3],
        transition=transition if transition["failed"] else None,
        warned=warned,
        diagnostics=built.get("diagnostics"),
        log=built.get("logPath"),
    )
    return built


def check_warnings(suite, client, start, sprite, clean):
    logo = call(client, "scene_create", {"name": "Ending", "type": "LOGO", "backgroundId": start["backgroundId"]})[
        "scene"
    ]
    insert(client, {"sceneId": logo["id"]}, [{"command": "EVENT_TEXT", "args": {"text": "SCORE $0$"}}])
    shop = call(
        client, "scene_create", {"name": "Shop", "backgroundId": start["backgroundId"], "width": 20, "height": 18}
    )["scene"]
    keeper = call(
        client, "actor_create", {"sceneId": shop["id"], "name": "Keeper", "x": 15, "y": 16, "spriteSheetId": sprite}
    )["actor"]
    menu = {
        "command": "EVENT_MENU",
        "args": {"variable": "2", "items": 3, "option1": "BUY", "option2": "SELL", "option3": "BYE", "layout": "menu"},
    }
    insert(
        client,
        {"sceneId": shop["id"]},
        [menu, {"command": "EVENT_IF_TRUE", "args": {"variable": "4"}, "children": {"true": [], "false": []}}],
    )
    hidden = [{"command": "EVENT_HIDE_SPRITES", "args": {}}, menu, {"command": "EVENT_SHOW_SPRITES", "args": {}}]
    insert(client, {"sceneId": shop["id"], "actorId": keeper["id"]}, hidden)
    built = call(client, "rom_build")
    found = [item for item in built.get("diagnostics", []) if item.get("code") in WARNINGS]
    codes = [item["code"] for item in found]
    over_menu = [item for item in found if item["code"] == "ACTORS_OVER_MENU"]
    deprecated = [item for item in found if item["code"] == "DEPRECATED_EVENT"]
    suite.check(
        "C4",
        "rom_build warns about text in a LOGO scene, a $0$ token, actors under a right-hand menu without hidden "
        "sprites and a deprecated event, still builds, and warns about none of them on the clean build",
        built.get("success") is True
        and set(codes) == WARNINGS
        and len(over_menu) == 1
        and "scene Shop" in over_menu[0]["message"]
        and "Keeper" in over_menu[0]["message"]
        and len(deprecated) == 1
        and deprecated[0].get("event") == "EVENT_IF_TRUE"
        and "EVENT_IF" in deprecated[0].get("suggestedAction", "")
        and clean.get("success") is True,
        found=found,
        diagnostics=built.get("diagnostics"),
    )
