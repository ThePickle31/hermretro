"""Script events GB Studio does not have, on the event stages' game: refused by the script-writing tools with the
nearest real events, kept in a project with plugin events, and a build that leaves one out failing."""

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
