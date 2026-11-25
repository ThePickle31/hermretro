"""Script events through the real engine: the event catalog against the toolchain's GB Studio, event_describe, the
authoring skill's cookbook recipes building in their places, and rom_build's authoring warnings (on every path,
through custom scripts, on compiled text only)."""

import importlib.util
import json
import re
from pathlib import Path

from tests.acceptance.fixture import OWNER_E, structured

ROOT = Path(__file__).resolve().parents[2]
RECIPE_PAGES = [ROOT / "skills" / "authoring" / "references" / page for page in ("event-cookbook.md", "scene-types.md")]
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
    """The event lists of the cookbook and the scene types page by section heading, in order."""
    sections = [section for page in RECIPE_PAGES for section in re.split(r"^## ", page.read_text(), flags=re.M)[1:]]
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
    start_id = call(client, "project_inspect")["settings"]["startSceneId"]
    start = next(scene for scene in inventory["scenes"] if scene["id"] == start_id)
    sprite = next(asset["id"] for asset in inventory["assets"] if asset["type"] == "sprite")
    clean = check_recipes(suite, client, start, sprite)
    logo = check_warnings(suite, client, start, sprite, clean)
    check_warning_paths(suite, client, root, start, sprite, logo)


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
    actors = call(client, "event_describe", {"category": "Actor", "includeDeprecated": True})
    rest = call(
        client,
        "event_describe",
        {"category": "Actor", "includeDeprecated": True, "cursor": actors.get("nextCursor", "0")},
    )
    uncategorized = call(client, "event_describe", {"category": "Uncategorized"})
    big = ["EVENT_SWITCH", "EVENT_MENU", "EVENT_TEXT", "EVENT_LAUNCH_PROJECTILE", "EVENT_LAUNCH_PROJECTILE_SLOT"]
    full = call(client, "event_describe", {"events": big})
    compact = call(client, "event_describe", {"events": big, "detail": "compact"})
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
        and current.get("deprecatedHidden", 0) >= 1
        and len(actors.get("matches", [])) + len(rest.get("matches", [])) == actors.get("total", -1) > 40
        and "nextCursor" not in rest
        and "EVENT_PRINT" in [match["event"] for match in uncategorized.get("matches", [])]
        and len(json.dumps(compact)) < len(json.dumps(full)) / 2,
        listing=listing,
        described=json.dumps(described)[:1500],
        sound=sound,
        current=current,
        actors={"total": actors.get("total"), "first": len(actors.get("matches", [])), "rest": rest},
        uncategorized=uncategorized,
        sizes={"full": len(json.dumps(full)), "compact": len(json.dumps(compact))},
    )


def insert(client, target: dict, events: list[dict]) -> list[dict]:
    return [call(client, "script_edit", {"action": "insert", "target": target, "event": event}) for event in events]


def check_recipes(suite, client, start, sprite) -> dict:
    """Every cookbook recipe in its place: the pickup in a collision-group actor, the hazard in the scene's hit script,
    the enemy's shots in its hit and update scripts, the patrol in an actor's update script, the gated exit in a
    trigger with a scene switch in its branch, the rest in the scene's start script. Shots use the project's sprite."""
    book = recipes()
    scene = {"sceneId": start["id"]}

    def actor(name: str, x: int, y: int, group: str) -> str:
        properties = {"collisionGroup": group}
        created = call(
            client,
            "actor_create",
            {"sceneId": start["id"], "name": name, "x": x, "y": y, "spriteSheetId": sprite, "properties": properties},
        )
        return created["actor"]["id"]

    coin, enemy, beetle = actor("Coin", 4, 4, "1"), actor("Enemy", 12, 6, "2"), actor("Beetle", 2, 9, "2")
    gate = call(client, "trigger_create", {"sceneId": start["id"], "name": "Gate", "x": 8, "y": 2})["trigger"]
    placed = {
        "Pickup": [{**scene, "actorId": coin}, {**scene, "actorId": coin, "scriptKey": "startScript"}],
        "Hazard": [{**scene, "scriptKey": "playerHit2Script"}],
        "Shooting": [
            scene,
            {**scene, "actorId": enemy, "scriptKey": "hit1Script"},
            {**scene, "actorId": enemy, "scriptKey": "updateScript"},
        ],
        "Patrolling enemy": [{**scene, "actorId": beetle, "scriptKey": "updateScript"}],
        "Gated exit with a counter": [{**scene, "triggerId": gate["id"]}],
    }
    results = []
    for heading, lists in book.items():
        targets = placed.get(heading, [scene] * len(lists))
        for target, events in zip(targets, lists, strict=True):
            results += insert(client, target, json.loads(json.dumps(events).replace("<shot sprite id>", sprite)))
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
    return logo


def check_warning_paths(suite, client, root, start, sprite, logo):
    """Hidden sprites count only on every path to a menu; a menu without layout is the right-hand one; text the
    compiler never prints is not checked; and a custom script is checked where it is called, its deprecated events
    counted once."""
    lines = {
        "_resourceType": "script",
        "id": "e01-shared-lines",
        "name": "Shared Lines",
        "symbol": "script_e01_shared_lines",
        "description": "",
        "variables": {},
        "actors": {},
        "script": [
            {"id": "e01-shared-text", "command": "EVENT_TEXT", "args": {"text": "Shared."}},
            {
                "id": "e01-shared-if",
                "command": "EVENT_IF_TRUE",
                "args": {"variable": "4"},
                "children": {"true": [], "false": []},
            },
        ],
    }
    scripts = root / "project" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "shared_lines.gbsres").write_text(json.dumps(lines, indent=2))
    call_lines = {"command": "EVENT_CALL_CUSTOM_EVENT", "args": {"customEventId": lines["id"]}}
    paths = call(
        client, "scene_create", {"name": "Paths", "backgroundId": start["backgroundId"], "width": 20, "height": 18}
    )["scene"]
    guard = call(
        client, "actor_create", {"sceneId": paths["id"], "name": "Guard", "x": 15, "y": 16, "spriteSheetId": sprite}
    )["actor"]
    gate = call(client, "trigger_create", {"sceneId": paths["id"], "name": "Quiet", "x": 2, "y": 2})["trigger"]
    menu = {"command": "EVENT_MENU", "args": {"variable": "2", "items": 2, "option1": "YES", "option2": "NO"}}
    hide = {"command": "EVENT_HIDE_SPRITES", "args": {}}
    inserted = insert(
        client,
        {"sceneId": paths["id"]},
        [
            {
                "command": "EVENT_IF",
                "args": {"condition": {"type": "variable", "value": "4"}},
                "children": {"true": [hide], "false": [menu]},
            },
            call_lines,
            call_lines,
        ],
    )
    inserted += insert(
        client,
        {"sceneId": paths["id"], "actorId": guard["id"]},
        [{"command": "EVENT_THREAD_START", "args": {"variable": "3"}, "children": {"true": [hide]}}, menu],
    )
    inserted += insert(
        client,
        {"sceneId": paths["id"], "triggerId": gate["id"]},
        [
            {"command": "EVENT_COMMENT", "args": {"text": "Shows $0$ coins."}},
            {
                "command": "EVENT_IF",
                "args": {"condition": {"type": "variable", "value": "4"}, "__disableElse": True},
                "children": {"true": [], "false": [{"command": "EVENT_TEXT", "args": {"text": "Never $0$."}}]},
            },
            {**menu, "args": {**menu["args"], "layout": "dialogue", "option8": "Unused $0$"}},
        ],
    )
    inserted += insert(client, {"sceneId": logo["id"]}, [call_lines])
    built = call(client, "rom_build")
    found = [item for item in built.get("diagnostics", []) if item.get("code") in WARNINGS]
    messages = {item["code"]: [] for item in found}
    for item in found:
        messages[item["code"]].append(item["message"])
    over = messages.get("ACTORS_OVER_MENU", [])
    deprecated = [item for item in found if item["code"] == "DEPRECATED_EVENT" and item.get("event") == "EVENT_IF_TRUE"]
    suite.check(
        "C5",
        "rom_build warns about a menu reached on a path without hidden sprites (another branch or a thread hid them), "
        "follows a custom script into a LOGO scene and counts its deprecated event once, and leaves out comments, a "
        "disabled else branch and menu options past the menu's items",
        built.get("success") is True
        and not any(result["failed"] for result in inserted)
        and any(message.startswith("The menu in scene Paths opens over Guard") for message in over)
        and any("actor Guard in scene Paths" in message for message in over)
        and any(
            "custom script Shared Lines (called from scene Ending)" in message
            for message in messages.get("TEXT_IN_LOGO_SCENE", [])
        )
        and not any("Paths" in message for message in messages.get("TEXT_VARIABLE_TOKEN", []))
        and len(deprecated) == 1
        and "(2 in the project" in deprecated[0]["message"],
        found=found,
        failed=[result for result in inserted if result["failed"]][:3],
        diagnostics=built.get("diagnostics"),
        log=built.get("logPath"),
    )
