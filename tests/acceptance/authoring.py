"""Authoring through the real engine: project-unique symbols, scene transactions (and their operations files) and
script events."""

import json
from pathlib import Path

from tests.acceptance.fixture import OWNER_S, structured


def call(client, tool: str, arguments: dict | None = None) -> dict:
    response = client.call(OWNER_S, tool, arguments or {})
    result = response.get("result") or {}
    return {**structured(response), "failed": bool(result.get("isError"))}


def check_symbols_and_events(suite, client):
    root = suite.work / "projS"
    call(
        client,
        "project_create_blank",
        {
            "name": "S01 Symbols",
            "destinationPath": str(root),
            "gameType": "TOPDOWN",
            "colorMode": "color",
            "select": True,
        },
    )
    inventory = call(client, "project_inventory")
    start = inventory["scenes"][0]
    sprite = next(asset["id"] for asset in inventory["assets"] if asset["type"] == "sprite")
    made = call(client, "scene_create", {"name": "Cellar", "backgroundId": start["backgroundId"]})
    cellar = made["scene"]
    # Real sprites and a different line each, so the build compiles both interaction scripts.
    created = [
        call(
            client,
            "actor_create",
            {"sceneId": scene["id"], "name": "Door", "x": 2, "y": 2, "spriteSheetId": sprite, "dialogue": line},
        )
        for scene, line in ((start, "FRONT DOOR"), (cellar, "CELLAR DOOR"))
    ]
    doors = [result["actor"] for result in created]
    exits = [
        call(client, "trigger_create", {"sceneId": scene["id"], "name": "Exit", "x": 4, "y": 4})["trigger"]
        for scene in (start, cellar)
    ]
    batch = call(
        client,
        "scene_apply",
        {"sceneId": start["id"], "operations": [{"type": "actor.create", "name": "Door", "x": 6, "y": 2}]},
    )
    third = call(
        client, "actor_inspect", {"sceneId": start["id"], "actorId": batch["operationResults"][0]["resourceId"]}
    )["actor"]
    renamed = call(client, "actor_update", {"sceneId": cellar["id"], "actorId": doors[1]["id"], "name": "Cellar Door"})
    symbols = [doors[0]["symbol"], doors[1]["symbol"], third["symbol"], exits[0]["symbol"], exits[1]["symbol"]]
    suite.check(
        "S1",
        "Same-named actors and triggers in two scenes get project-unique symbols, and a rename gives a new one",
        symbols == ["actor_door", "actor_door_2", "actor_door_3", "trigger_exit", "trigger_exit_2"]
        and renamed["actor"]["symbol"] == "actor_cellar_door",
        symbols=symbols,
        renamed=renamed.get("actor", {}).get("symbol"),
    )
    check_reserved_keys(suite, client, start, cellar, doors, third)
    check_compiled_names(suite, client, root, cellar, third)
    check_events(suite, client, start, cellar, doors, created)
    check_stale_duplicate(suite, client, root, cellar, doors, created)
    check_older_events(suite, client, root / made["resourcePath"], start, cellar, third)
    check_operations_file(suite, client, root, cellar, sprite)


def check_operations_file(suite, client, root, cellar, sprite):
    operations = [{"type": "actor.create", "name": "Lamp", "x": 9, "y": 3, "spriteSheetId": sprite}]
    (root / "lamp-ops.json").write_text(json.dumps({"operations": operations}))
    outside = suite.work / "outside-ops.json"
    outside.write_text(json.dumps(operations))
    applied = call(client, "scene_apply", {"sceneId": cellar["id"], "operationsPath": "lamp-ops.json"})
    lamp = call(
        client, "actor_inspect", {"sceneId": cellar["id"], "actorId": applied["operationResults"][0]["resourceId"]}
    ).get("actor", {})
    refused = client.call(OWNER_S, "scene_apply", {"sceneId": cellar["id"], "operationsPath": str(outside)})
    suite.check(
        "S10",
        "scene_apply reads its operations from a JSON file in the project and refuses one outside it",
        not applied["failed"]
        and lamp.get("name") == "Lamp"
        and (refused.get("denied") or {}).get("code") == "OPERATIONS_FILE"
        and refused.get("dispatched") is False,
        applied=applied.get("error") or applied.get("changedPaths"),
        lamp=lamp.get("name"),
        refused=refused,
    )


def check_reserved_keys(suite, client, start, cellar, doors, third):
    revision = call(client, "scene_inspect", {"sceneId": cellar["id"]})["revision"]
    set_symbol = call(
        client,
        "scene_apply",
        {
            "sceneId": cellar["id"],
            "expectedRevision": revision,
            "operations": [{"type": "actor.update", "actorId": doors[1]["id"], "symbol": "actor_mine"}],
        },
    )
    unchanged = call(
        client,
        "scene_apply",
        {"sceneId": cellar["id"], "operations": [{"type": "actor.update", "actorId": doors[1]["id"], "x": 2}]},
    )
    suite.check(
        "S2",
        "Setting a symbol is refused, and a scene_apply that changes nothing reports no changed files",
        set_symbol["failed"]
        and set_symbol.get("code") == "INVALID_PROPERTY"
        and not unchanged["failed"]
        and unchanged.get("changedPaths") == []
        and unchanged.get("revision") == unchanged.get("previousRevision"),
        set_symbol=set_symbol,
        unchanged_paths=unchanged.get("changedPaths"),
    )

    created_symbol = call(
        client,
        "actor_create",
        {"sceneId": start["id"], "name": "Sign", "x": 8, "y": 8, "properties": {"symbol": "actor_door"}},
    )
    conflicting = call(
        client,
        "scene_apply",
        {
            "sceneId": start["id"],
            "operations": [{"type": "actor.update", "actorId": third["id"], "id": doors[0]["id"]}],
        },
    )
    alias = call(
        client,
        "scene_apply",
        {"sceneId": start["id"], "operations": [{"type": "actor.update", "id": third["id"], "x": 7}]},
    )
    suite.check(
        "S6",
        "actor_create refuses a symbol property, and scene_apply refuses an id that names another resource",
        created_symbol["failed"]
        and created_symbol.get("code") == "INVALID_PROPERTY"
        and conflicting["failed"]
        and conflicting.get("code") == "INVALID_INPUT"
        and not alias["failed"],
        created_symbol=created_symbol.get("code"),
        conflicting=conflicting.get("error"),
        alias=alias.get("error"),
    )


def check_compiled_names(suite, client, root: Path, cellar, third):
    # actor_door_3 compiles actor_door_3_interact, so an actor named "Door 3 Interact" may not take that symbol.
    clash = call(client, "actor_create", {"sceneId": cellar["id"], "name": "Door 3 Interact", "x": 9, "y": 9})
    script_file = root / "project" / "scripts" / "door_hook.gbsres"
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(
        json.dumps(
            {
                "_resourceType": "script",
                "id": "5c0a9b9e-6f43-4d52-9d0e-0d2f4b6f2a11",
                "name": "Door Hook",
                "symbol": "actor_door_3_interact_2_update",
                "description": "",
                "variables": {},
                "actors": {},
                "script": [],
            },
            indent=2,
        )
    )
    diagnostics = call(client, "project_inventory", {"resourceTypes": ["diagnostic"]}).get("diagnostics", [])
    script_file.unlink()
    duplicates = [item for item in diagnostics if item.get("code") == "DUPLICATE_SYMBOL"]
    suite.check(
        "S7",
        "Symbols avoid the script names other symbols compile to, and a custom script taking one is a duplicate",
        not clash["failed"]
        and clash["actor"]["symbol"] == "actor_door_3_interact_2"
        and len(duplicates) == 1
        and "actor_door_3_interact_2_update" in duplicates[0]["message"]
        and clash["actor"]["id"] in duplicates[0]["message"],
        clash=clash.get("actor", {}).get("symbol") or clash.get("error"),
        duplicates=duplicates,
    )
    call(client, "actor_delete", {"sceneId": cellar["id"], "actorId": clash["actor"]["id"]})


def check_events(suite, client, start, cellar, doors, created):
    facing = call(
        client,
        "script_edit",
        {
            "action": "insert",
            "target": {"sceneId": start["id"]},
            "event": {
                "command": "EVENT_ACTOR_SET_DIRECTION",
                "args": {"actorId": doors[0]["id"], "direction": {"type": "direction", "value": "left"}},
            },
        },
    )
    replaced = call(
        client,
        "scene_apply",
        {
            "sceneId": start["id"],
            "operations": [
                {"type": "actor.delete", "actorId": doors[0]["id"]},
                {
                    "type": "actor.create",
                    "id": doors[0]["id"],
                    "name": "Door",
                    "x": 3,
                    "y": 3,
                    "spriteSheetId": doors[0]["spriteSheetId"],
                    "properties": {"script": doors[0]["script"]},
                },
            ],
        },
    )
    after = call(client, "actor_inspect", {"sceneId": start["id"], "actorId": doors[0]["id"]})
    suite.check(
        "S3",
        "Deleting and recreating one id in a scene_apply replaces the actor in its file, while a script refers to it",
        not facing["failed"]
        and not replaced["failed"]
        and replaced.get("changedPaths") == [created[0]["resourcePath"]]
        and after.get("resourcePath") == created[0]["resourcePath"]
        and (after.get("actor", {}).get("x"), after.get("actor", {}).get("symbol")) == (3, "actor_door"),
        replaced=replaced if replaced["failed"] else replaced.get("changedPaths"),
    )

    owner = {"sceneId": cellar["id"], "actorId": doors[1]["id"]}
    branch = {
        "command": "EVENT_IF_TRUE",
        "args": {"variable": "0"},
        "children": {"true": [{"command": "EVENT_TEXT", "args": {"text": "Locked."}}], "false": []},
    }
    nested = [
        call(client, "script_edit", {"action": "insert", "index": 0, "target": owner, "event": branch})
        for _ in range(2)
    ]

    def set_direction(args: dict) -> dict:
        event = {"command": "EVENT_ACTOR_SET_DIRECTION", "args": {"actorId": "$self$", **args}}
        return call(client, "script_edit", {"action": "insert", "index": 0, "target": owner, "event": event})

    untyped = set_direction({"direction": "up"})
    events = call(client, "script_inspect", {"target": owner})["events"]
    ids = [event.get("id") for event in events if event["command"] == "EVENT_IF_TRUE"]
    ids += [
        child.get("id")
        for event in events
        if event["command"] == "EVENT_IF_TRUE"
        for child in event["children"]["true"]
    ]
    suite.check(
        "S4",
        "Events without ids, nested ones too, get unique ids, and an untyped actor direction is refused on write",
        all(not result["failed"] for result in nested)
        and len(ids) == 4
        and all(ids)
        and len(set(ids)) == 4
        and untyped["failed"]
        and untyped.get("code") == "INVALID_EVENT",
        ids=ids,
        untyped=untyped.get("error"),
    )

    refused = [set_direction({}), set_direction({"direction": {"type": "direction", "value": "north"}})]
    accepted = [
        set_direction({"direction": {"type": "variable", "value": "0"}}),
        set_direction({"direction": "up", "__comment": True}),
    ]
    suite.check(
        "S8",
        "An actor direction event needs a direction of up, down, left or right, a variable is accepted, and a "
        "commented-out event is not checked",
        all(result["failed"] and result.get("code") == "INVALID_EVENT" for result in refused)
        and not any(result["failed"] for result in accepted),
        refused=[result.get("error") for result in refused],
        accepted=[result.get("error") for result in accepted],
    )


def check_stale_duplicate(suite, client, root: Path, cellar, doors, created):
    # A project made before the fix: two actors named Door sharing a symbol, written straight to the file.
    actor_file = root / created[1]["resourcePath"]
    stale = json.loads(actor_file.read_text())
    actor_file.write_text(json.dumps({**stale, "name": "Door", "symbol": "actor_door"}, indent=2))
    inspected = call(client, "project_inspect")
    message = next(
        (item["message"] for item in inspected.get("diagnostics", []) if item.get("code") == "DUPLICATE_SYMBOL"), ""
    )
    refused = call(client, "rom_build")
    renamed = call(client, "actor_update", {"sceneId": cellar["id"], "actorId": doors[1]["id"], "name": "Door!"})
    built = call(client, "rom_build")
    rom = Path(built["outputPath"]).read_bytes() if built.get("outputPath") else b""
    suite.check(
        "S5",
        "A shared symbol in an older project is listed with both owners' ids and blocks rom_build until a rename "
        "that keeps the name's symbol gives it a new one, and both doors' scripts are built",
        inspected.get("health", {}).get("byCode", {}).get("DUPLICATE_SYMBOL") == 1
        and all(door["id"] in message for door in doors)
        and refused["failed"]
        and refused.get("code") == "DUPLICATE_SYMBOL"
        and renamed.get("actor", {}).get("symbol") not in (None, "actor_door")
        and not built["failed"]
        and built.get("success") is not False
        and b"FRONT DOOR" in rom
        and b"CELLAR DOOR" in rom,
        message=message,
        refused=refused.get("code"),
        renamed=renamed.get("actor", {}).get("symbol") or renamed.get("error"),
        built=built.get("error") or built.get("success"),
    )


def check_older_events(suite, client, scene_file: Path, start, cellar, third):
    # An older scene: an id-less scene switch with plain coordinates, which an unrelated edit must keep accepting.
    scene = json.loads(scene_file.read_text())
    switch = {"command": "EVENT_SWITCH_SCENE", "args": {"sceneId": start["id"], "x": 3, "y": 3, "direction": "down"}}
    scene_file.write_text(json.dumps({**scene, "script": [switch, *scene.get("script", [])]}, indent=2))
    unrelated = call(client, "scene_update", {"sceneId": cellar["id"], "x": 40})

    # A dialogue event whose command changed survives the event it was created after.
    owner = {"sceneId": start["id"], "actorId": third["id"]}
    wait = {"command": "EVENT_WAIT", "args": {"time": 0.5}}
    first = call(client, "script_edit", {"action": "insert", "target": owner, "event": wait})["event"]
    spoken = call(client, "dialogue_update", {**owner, "text": "Hello"})
    spoken_id = (spoken.get("event") or {}).get("id")
    call(client, "script_edit", {"action": "update", "target": owner, "eventId": spoken_id, "patch": wait})
    call(client, "script_edit", {"action": "delete", "target": owner, "eventId": first["id"]})
    again = call(client, "dialogue_update", {**owner, "text": "Hello again"})
    suite.check(
        "S9",
        "An unchanged older id-less event stays accepted, and dialogue_update gives a new event an unused id",
        not unrelated["failed"] and not spoken["failed"] and not again["failed"],
        unrelated=unrelated.get("error"),
        spoken=spoken.get("error") or spoken_id,
        again=again.get("error"),
    )
