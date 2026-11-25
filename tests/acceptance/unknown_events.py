"""Script events GB Studio does not have or cannot compile, on the event stages' game: refused by the script-writing
tools with the nearest real events or the replacement, kept in a project with plugin events, and a build that leaves
one out or fails on one saying which event and what to do."""

import json
import shutil
from pathlib import Path

from tests.acceptance.fixture import OWNER_E, structured


def call(client, tool: str, arguments: dict | None = None) -> dict:
    response = client.call(OWNER_E, tool, arguments or {})
    result = response.get("result") or {}
    return {**structured(response), "failed": bool(result.get("isError"))}


def check(suite, client, root: Path, start):
    """A command that is no GB Studio event (an agent wrote EVENT_INPUT_AWAIT) is refused by every script-writing
    tool with the nearest real events, also as a scene update's actor and when an edit names an old one; a project
    with plugin events keeps any command; and a project that already holds one fails its build instead of building
    without it, keeping its last ROM."""
    invented = {"command": "EVENT_INPUT_AWAIT", "args": {"input": ["a"]}}
    scene = {"sceneId": start["id"]}
    refused = [
        call(client, "script_edit", {"action": "insert", "target": scene, "event": invented}),
        call(
            client,
            "scene_apply",
            {
                "sceneId": start["id"],
                "operations": [{"type": "script.edit", "action": "insert", "target": scene, "event": invented}],
            },
        ),
        call(
            client,
            "actor_create",
            {"sceneId": start["id"], "name": "Waiter", "x": 6, "y": 6, "properties": {"script": [invented]}},
        ),
        call(
            client,
            "scene_update",
            {
                "sceneId": start["id"],
                "properties": {"actors": [{"id": "e01-nested", "name": "Nested", "script": [invented]}]},
            },
        ),
    ]
    plugin = root / "plugins" / "e01-tools" / "events"
    plugin.mkdir(parents=True)
    (plugin / "eventE01Ping.js").write_text(
        'const id = "EVENT_E01_PING";\nmodule.exports = { id, name: "Ping", fields: [], compile: () => {} };\n'
    )
    kept = [
        call(client, "script_edit", {"action": "insert", "target": scene, "event": event})
        for event in ({"command": "EVENT_E01_PING"}, invented)
    ]
    removed = [
        call(
            client,
            "script_edit",
            {"action": "delete", "target": scene, "eventId": result.get("event", {}).get("id", "")},
        )
        for result in kept
    ]
    shutil.rmtree(plugin.parent)

    # A project written before the check: the invented event straight in the scene file.
    scene_file = root / kept[0].get("resourcePath", "")
    original = scene_file.read_text()
    stored = json.loads(original)
    stored["script"] = [*stored.get("script", []), {"id": "e01-invented", **invented}]
    scene_file.write_text(json.dumps(stored, indent=2))
    later = call(
        client,
        "script_edit",
        {
            "action": "insert",
            "target": scene,
            "event": {"command": "EVENT_WAIT", "args": {"time": {"type": "number", "value": 0.5}, "units": "time"}},
        },
    )
    edited = call(
        client,
        "script_edit",
        {"action": "update", "target": scene, "eventId": "e01-invented", "patch": {"args": {"input": ["b"]}}},
    )
    roms = {path.name: path.read_bytes() for path in (root / "build").glob("*.gb*") if path.is_file()}
    built = call(client, "rom_build")
    scene_file.write_text(original)
    unknown = [item for item in built.get("diagnostics", []) if item.get("code") == "UNKNOWN_EVENT_COMMAND"]
    rom = Path(built.get("outputPath", "")).name
    suite.check(
        "C6",
        "script_edit, scene_apply, actor properties and a scene update's actors refuse an event GB Studio does not have "
        "and name the nearest ones, a project with plugin events keeps any command, an edit beside an old unknown "
        "event works but one of it is refused, and a build that drops one fails and keeps the last ROM",
        all(result["failed"] and result.get("code") == "INVALID_EVENT" for result in [*refused, edited])
        and all("EVENT_AWAIT_INPUT" in str(result.get("error")) for result in refused)
        and not any(result["failed"] for result in [*kept, *removed, later])
        and built.get("success") is False
        and built.get("rom") is None
        and rom in roms
        and (root / "build" / rom).read_bytes() == roms[rom]
        and not list((root / "build").glob(".rom-build-*"))
        and len(unknown) == 1
        and unknown[0].get("severity") == "error"
        and unknown[0].get("event") == "EVENT_INPUT_AWAIT"
        and "EVENT_AWAIT_INPUT" in unknown[0].get("suggestedAction", ""),
        refused=[result.get("error") for result in refused],
        kept=[result.get("error") for result in kept],
        later=later.get("error"),
        edited=edited.get("error"),
        roms=list(roms),
        output=rom,
        unknown=unknown,
        diagnostics=built.get("diagnostics"),
        log=built.get("logPath"),
    )


def check_unavailable(suite, client, root: Path, start, sprite: str):
    """EVENT_WEAPON_ATTACK, which GB Studio lists but cannot compile (its weaponAttack helper is gone), is refused by
    every script-writing tool with EVENT_LAUNCH_PROJECTILE and the conversion, also when an edit updates, moves or
    resupplies an old one, and event_describe lists it only when asked. A build that stops on an event's compile fails
    with one SCRIPT_EVENT_COMPILE_FAILED for the innermost event, keeping the last ROM: the replacement for the attack
    and for a deprecated event that failed for another reason, the cause for a plugin's. Message-shaped output from a
    build that succeeds is no failure, and a project with plugin events keeps any command on write."""
    attack = {
        "command": "EVENT_WEAPON_ATTACK",
        "args": {
            "spriteSheetId": sprite,
            "actorId": "$self$",
            "offset": 10,
            "collisionGroup": "3",
            "collisionMask": ["1"],
        },
    }
    scene = {"sceneId": start["id"]}
    refused = [
        call(client, "script_edit", {"action": "insert", "target": scene, "event": attack}),
        call(
            client,
            "scene_apply",
            {
                "sceneId": start["id"],
                "operations": [{"type": "script.edit", "action": "insert", "target": scene, "event": attack}],
            },
        ),
        call(
            client,
            "actor_create",
            {"sceneId": start["id"], "name": "Swinger", "x": 6, "y": 6, "properties": {"script": [attack]}},
        ),
        call(
            client,
            "scene_update",
            {
                "sceneId": start["id"],
                "properties": {"actors": [{"id": "e01-attacker", "name": "Attacker", "script": [attack]}]},
            },
        ),
    ]
    hidden = call(client, "event_describe", {"query": "attack"})
    listed = call(client, "event_describe", {"query": "attack", "includeDeprecated": True})
    described = call(client, "event_describe", {"events": ["EVENT_WEAPON_ATTACK"]})

    # A project written before the check: the attack straight in the scene file, in an EVENT_IF's disabled else.
    wait = {"command": "EVENT_WAIT", "args": {"time": {"type": "number", "value": 0.5}, "units": "time"}}
    later = call(client, "script_edit", {"action": "insert", "target": scene, "event": wait})
    scene_file = root / later.get("resourcePath", "")
    original = scene_file.read_text()
    old = {"id": "e01-attack", **attack}

    def with_script(*events: dict) -> None:
        stored = json.loads(original)
        stored["script"] = [*stored.get("script", []), *events]
        scene_file.write_text(json.dumps(stored, indent=2))

    def branch(true: list, false: list) -> dict:
        condition = {"type": "number", "value": 1}
        return {
            "id": "e01-if",
            "command": "EVENT_IF",
            "args": {"condition": condition, "__disableElse": True},
            "children": {"true": true, "false": false},
        }

    with_script(branch([], [old]))
    in_else = {**scene, "branchPath": [{"eventId": "e01-if", "branch": "false"}]}
    rewritten = [
        call(
            client,
            "script_edit",
            {"action": "update", "target": in_else, "eventId": "e01-attack", "patch": {"args": {"offset": 12}}},
        ),
        call(client, "script_edit", {"action": "move", "target": in_else, "eventId": "e01-attack", "index": 0}),
        call(
            client,
            "script_edit",
            {
                "action": "update",
                "target": scene,
                "eventId": "e01-if",
                "patch": {"children": {"true": [old], "false": []}},
            },
        ),
    ]
    roms = {path.name: path.read_bytes() for path in (root / "build").glob("*.gb*") if path.is_file()}
    with_script(branch([old], []))
    built = call(client, "rom_build")
    expression = {"id": "e01-expression", "command": "EVENT_IF_EXPRESSION", "args": {"expression": "1 + + ) ("}}
    with_script({**expression, "children": {"true": [], "false": []}})
    malformed = call(client, "rom_build")
    scene_file.write_text(original)
    rom = Path(built.get("outputPath", "")).name
    kept_rom = rom in roms and (root / "build" / rom).read_bytes() == roms[rom]

    plugin = root / "plugins" / "e01-tools" / "events"
    plugin.mkdir(parents=True)
    (plugin / "eventE01Boom.js").write_text(
        'const id = "EVENT_E01_BOOM";\n'
        'module.exports = { id, name: "Boom", fields: [], compile: () => { throw new Error("e01 boom\\nsecond line"); } };\n'
    )
    (plugin / "eventE01Quiet.js").write_text(
        'const id = "EVENT_E01_QUIET";\nmodule.exports = { id, name: "Quiet", fields: [], compile: () => {\n'
        '  console.log(\'Compiling "EVENT_E01_QUIET" failed with error "not really". {"scene":"Start"}\');\n} };\n'
    )
    kept = [
        call(client, "script_edit", {"action": "insert", "target": scene, "event": event})
        for event in ({"command": "EVENT_E01_QUIET"}, attack)
    ]
    call(
        client, "script_edit", {"action": "delete", "target": scene, "eventId": kept[1].get("event", {}).get("id", "")}
    )
    quiet = call(client, "rom_build")
    call(client, "script_edit", {"action": "insert", "target": scene, "event": {"command": "EVENT_E01_BOOM"}})
    boom = call(client, "rom_build")
    shutil.rmtree(plugin.parent)
    scene_file.write_text(original)

    def failures(result: dict) -> list[dict]:
        return [item for item in result.get("diagnostics", []) if item.get("code") == "SCRIPT_EVENT_COMPILE_FAILED"]

    def others(result: dict, event: str) -> list[dict]:
        """A generic compiler error, or the deprecation warning the failure stands for."""
        return [
            item
            for item in result.get("diagnostics", [])
            if item.get("code") == "COMPILER_ERROR"
            or (item.get("code") == "DEPRECATED_EVENT" and item.get("event") == event)
        ]

    attacked, broken, boomed = failures(built), failures(malformed), failures(boom)
    by_event = {entry.get("event"): entry for entry in described.get("events", [])}
    suite.check(
        "C7",
        "Every script-writing tool refuses EVENT_WEAPON_ATTACK (GB Studio cannot compile it) with "
        "EVENT_LAUNCH_PROJECTILE and the conversion, also an edit that updates, moves or resupplies an old one, "
        "event_describe lists it only when asked, a build that stops on an event's compile says which with one "
        "SCRIPT_EVENT_COMPILE_FAILED for the innermost event and keeps the last ROM (the replacement for the attack "
        "and a malformed deprecated event, the cause for a plugin's), and message-shaped output of a build that "
        "succeeds is no failure",
        all(result["failed"] and result.get("code") == "INVALID_EVENT" for result in [*refused, *rewritten])
        and all(
            "EVENT_LAUNCH_PROJECTILE" in str(result.get("error")) and "initialOffset" in str(result.get("error"))
            for result in [*refused, *rewritten]
        )
        and not later["failed"]
        and not any(match.get("event") == "EVENT_WEAPON_ATTACK" for match in hidden.get("matches", []))
        and hidden.get("deprecatedHidden", 0) >= 1
        and any(
            match.get("event") == "EVENT_WEAPON_ATTACK" and match.get("unavailable") is True
            for match in listed.get("matches", [])
        )
        and "weaponAttack" in str(by_event.get("EVENT_WEAPON_ATTACK", {}).get("unavailable"))
        and built.get("success") is False
        and built.get("rom") is None
        and kept_rom
        and len(attacked) == 1
        and attacked[0].get("event") == "EVENT_WEAPON_ATTACK"
        and "EVENT_LAUNCH_PROJECTILE" in attacked[0].get("suggestedAction", "")
        and not others(built, "EVENT_WEAPON_ATTACK")
        and malformed.get("success") is False
        and len(broken) == 1
        and broken[0].get("event") == "EVENT_IF_EXPRESSION"
        and "Mismatched parenthesis" in broken[0].get("suggestedAction", "")
        and "Use EVENT_IF instead" in broken[0].get("suggestedAction", "")
        and not others(malformed, "EVENT_IF_EXPRESSION")
        and not any(result["failed"] for result in kept)
        and quiet.get("success") is True
        and not failures(quiet)
        and boom.get("success") is False
        and len(boomed) == 1
        and boomed[0].get("event") == "EVENT_E01_BOOM"
        and "second line" in boomed[0].get("suggestedAction", "")
        and not others(boom, "EVENT_E01_BOOM"),
        refused=[result.get("error") for result in refused],
        rewritten=[result.get("error") for result in rewritten],
        later=later.get("error"),
        kept=[result.get("error") for result in kept],
        hidden=hidden,
        listed=listed,
        roms=list(roms),
        output=rom,
        built=built.get("diagnostics"),
        malformed=malformed.get("diagnostics"),
        quiet=quiet.get("diagnostics"),
        boom=boom.get("diagnostics"),
    )
