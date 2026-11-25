"""Small tool fixes on the real engine, on B after its replays (later checks restart B's emulator): script_inspect
named flat, a step that only looks pointed to observe, frames and contact sheets in the Chromatic's colors, a
stopped recording continued by replay, and the event named inside a script target."""

import base64

from backend.library.game_cover import decode_png
from tests.acceptance.fixture import OWNER_B, structured


def refused(response) -> bool:
    return response["result"].get("isError") is True


def error(response) -> str:
    return str(structured(response).get("error"))


def image(response) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """Width, height and RGBA pixels of a response's last image."""
    block = [b for b in response["result"].get("content", []) if b.get("type") == "image"][-1]
    return decode_png(base64.b64decode(block["data"]))


def pixels(response) -> list[tuple[int, int, int, int]]:
    return image(response)[2]


def tile_pixels(sheet_response, tile: dict) -> list[tuple[int, int, int, int]]:
    """A contact-sheet tile's pixels at native size (one per enlarged square)."""
    width, _height, sheet = image(sheet_response)
    scale = tile["width"] // tile["sourceWidth"]
    return [
        sheet[(tile["y"] + row * scale) * width + tile["x"] + column * scale]
        for row in range(tile["sourceHeight"])
        for column in range(tile["sourceWidth"])
    ]


def chromatic(pixel: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """The hermretro player's color correction (the Gambatte curve), as the engine applies it."""
    red, green, blue = (channel >> 3 for channel in pixel[:3])
    return (red * 13 + green * 2 + blue) >> 1, (green * 3 + blue) << 1, (red * 3 + green * 2 + blue * 11) >> 1, pixel[3]


def check_tool_friction(suite, client_b, rom_b):
    check_script_inspect(suite, client_b)
    check_look_only_step(suite, client_b)
    check_color_correction(suite, client_b, rom_b)
    check_corrected_contact_sheets(suite, client_b)
    check_stopped_recording(suite, client_b, rom_b)
    check_event_in_target(suite, client_b)


def check_script_inspect(suite, client_b):
    scene = structured(client_b.call(OWNER_B, "project_inspect", {}))["settings"]["startSceneId"]
    flat = structured(client_b.call(OWNER_B, "script_inspect", {"sceneId": scene}))
    nested = structured(client_b.call(OWNER_B, "script_inspect", {"target": {"sceneId": scene}}))
    both = client_b.call(OWNER_B, "script_inspect", {"sceneId": scene, "target": {"sceneId": scene}})
    neither = client_b.call(OWNER_B, "script_inspect", {})
    suite.check(
        "M10",
        "script_inspect reads a script named by a flat sceneId as it does by target, and refuses both or neither",
        flat.get("sceneId") == scene
        and bool(flat.get("revision"))
        and {key: flat.get(key) for key in ("events", "revision", "scriptKey")}
        == {key: nested.get(key) for key in ("events", "revision", "scriptKey")}
        and refused(both)
        and refused(neither)
        and "sceneId" in error(neither),
        flat_revision=flat.get("revision") or flat.get("error"),
        nested_revision=nested.get("revision") or nested.get("error"),
        both=error(both),
        neither=error(neither),
    )


def check_look_only_step(suite, client_b):
    before = structured(client_b.call(OWNER_B, "emulator_status")).get("frame")
    looks = [
        client_b.call(OWNER_B, "emulator_step", args)
        for args in (
            {"buttons": [], "frames": 30, "sampleCount": 0},
            {"buttons": [], "frames": 0},
            {},
            {"inputs": []},
            {"inputs": [{"buttons": [], "frames": 0}, {"buttons": ["a"], "frames": 0}]},
        )
    ]
    after = structured(client_b.call(OWNER_B, "emulator_status")).get("frame")
    suite.check(
        "M11",
        "A step with sampleCount 0, frames 0, no input or a look-only inputs list is refused before it plays, "
        "pointing to emulator_observe",
        all(refused(look) and "emulator_observe" in error(look) for look in looks) and before == after is not None,
        errors=[error(look) for look in looks],
        frame_before=before,
        frame_after=after,
    )


def check_color_correction(suite, client_b, rom_b):
    raw = client_b.call(OWNER_B, "emulator_observe", {"detail": "full"})
    corrected = client_b.call(OWNER_B, "emulator_observe", {"colorCorrection": "chromatic"})
    stepped = client_b.call(OWNER_B, "emulator_step", {"buttons": [], "frames": 1, "colorCorrection": "chromatic"})
    stepped_raw = client_b.call(OWNER_B, "emulator_observe", {})
    replayed = client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b, "colorCorrection": "chromatic"})
    replayed_raw = client_b.call(OWNER_B, "emulator_observe", {})
    pairs = {"observe": (raw, corrected), "step": (stepped_raw, stepped), "replay": (replayed_raw, replayed)}
    suite.check(
        "M12",
        "Step, observe and replay frames on color hardware come back in the Chromatic's colors, every pixel through "
        "the player's curve, with the native frames' hashes",
        structured(raw).get("cgb") is True
        and all(
            structured(shown).get("imageDelivery", {}).get("colorCorrection") == "chromatic"
            and pixels(shown) == [chromatic(pixel) for pixel in pixels(native)]
            and pixels(shown) != pixels(native)
            for native, shown in pairs.values()
        )
        and structured(corrected)["samples"][0]["sha256"] == structured(raw)["samples"][0]["sha256"]
        and structured(stepped)["samples"][-1]["sha256"] == structured(stepped_raw)["samples"][0]["sha256"],
        cgb=structured(raw).get("cgb"),
        delivery={name: structured(shown).get("imageDelivery") for name, (_, shown) in pairs.items()},
        errors={name: structured(shown).get("error") for name, (_, shown) in pairs.items() if refused(shown)},
    )


def check_corrected_contact_sheets(suite, client_b):
    sheet_args = {"imageLayout": "contact-sheet", "colorCorrection": "chromatic"}
    observed = client_b.call(OWNER_B, "emulator_observe", sheet_args)
    observed_raw = client_b.call(OWNER_B, "emulator_observe", {})
    stepped = client_b.call(OWNER_B, "emulator_step", {"buttons": [], "frames": 2, "scale": 3, **sheet_args})
    stepped_raw = client_b.call(OWNER_B, "emulator_observe", {})
    pairs = {"observe": (observed_raw, observed), "step": (stepped_raw, stepped)}

    def corrected(native, sheet) -> bool:
        tiles = structured(sheet).get("contactSheet", {}).get("tiles") or [{}]
        return (
            not refused(sheet)
            and structured(sheet)["imageDelivery"].get("colorCorrection") == "chromatic"
            and tiles[-1].get("sha256") == structured(sheet)["samples"][-1]["sha256"]
            and tiles[-1]["sha256"] == structured(native)["samples"][0]["sha256"]
            and tile_pixels(sheet, tiles[-1]) == [chromatic(pixel) for pixel in pixels(native)]
        )

    suite.check(
        "M14",
        "Step and observe contact sheets on color hardware draw the Chromatic's colors and keep the native hashes",
        all(corrected(native, sheet) for native, sheet in pairs.values()),
        errors={name: error(sheet) for name, (_, sheet) in pairs.items() if refused(sheet)},
        delivery={name: structured(sheet).get("imageDelivery") for name, (_, sheet) in pairs.items()},
    )


def check_stopped_recording(suite, client_b, rom_b):
    stopped = structured(client_b.call(OWNER_B, "emulator_recording", {"action": "stop"}))
    after = client_b.call(OWNER_B, "emulator_step", {"buttons": [], "frames": 1})
    suite.check(
        "M13",
        "After a recording stops, a step is refused as finalized, with how to go on: emulator_run again or "
        "emulator_replay with the stopped recording's recordingPath and branchId",
        stopped.get("status") == "stopped"
        and refused(after)
        and all(word in error(after) for word in ("finalized", "emulator_run", "emulator_replay", "recordingPath")),
        stopped=stopped.get("status") or stopped.get("error"),
        step=error(after),
    )
    source = {"recordingPath": stopped.get("recordingPath"), "branchId": stopped.get("branchId")}
    replayed = structured(
        client_b.call(OWNER_B, "emulator_replay", {"romPath": rom_b, "includeImages": False, **source})
    )
    replay = replayed.get("replay", {})
    played = replay.get("source", {})
    suite.check(
        "M15",
        "Replaying a stopped recording by the recordingPath and branchId stop returned plays it to its end",
        None not in source.values()
        and {"recordingPath": played.get("recordingPath"), "branchId": played.get("branchId")} == source
        and replay.get("status") == "matched"
        and replay.get("replayedActions") == played.get("actionCount"),
        source=source,
        replay=replay or replayed.get("error"),
    )


def check_event_in_target(suite, client_b):
    """script_edit, scene_apply and script_inspect take the event inside target as they take it beside target, and a
    scene_apply batch whose last operation names two different events is refused with nothing applied. The events it
    adds are deleted again, so B's start script is as it was."""

    def edit(arguments):
        return client_b.call(OWNER_B, "script_edit", arguments)

    def apply(operations, **arguments):
        return client_b.call(
            OWNER_B, "scene_apply", {"sceneId": target["sceneId"], "operations": operations, **arguments}
        )

    def revision():
        return structured(client_b.call(OWNER_B, "project_inspect", {})).get("revision")

    target = {"sceneId": structured(client_b.call(OWNER_B, "project_inspect", {}))["settings"]["startSceneId"]}
    comment = {"command": "EVENT_COMMENT", "args": {"text": "first"}}
    inserted = structured(edit({"action": "insert", "target": target, "event": comment}))
    event = {**target, "eventId": (inserted.get("event") or {}).get("id")}
    edited = edit({"action": "update", "target": event, "patch": {"args": {"text": "second"}}})
    operation = {"type": "script.edit", "action": "update", "target": event, "patch": {"args": {"text": "third"}}}
    applied = apply([operation])
    inspected = structured(client_b.call(OWNER_B, "script_inspect", {"target": event}))
    conflicting = edit({"action": "delete", "target": event, "eventId": "another-event"})
    condition = {"command": "EVENT_IF_TRUE", "args": {"variable": "0"}, "children": {"true": [], "false": []}}
    branch = (structured(edit({"action": "insert", "target": target, "event": condition})).get("event") or {}).get("id")
    batch = [
        {"type": "actor.create", "id": "acceptance-k2-actor", "name": "K2 actor", "x": 1, "y": 1},
        {
            "type": "script.edit",
            "action": "insert",
            "target": {**target, "branchPath": [{"eventId": branch, "branch": "true"}]},
            "event": comment,
        },
        {
            "type": "script.edit",
            "action": "insert",
            "target": {**target, "actorId": "acceptance-k2-actor"},
            "event": comment,
        },
        {**operation, "input": {"target": {**target, "eventId": branch}}},
    ]
    staged = apply(batch[:-1], dryRun=True)
    before = revision()
    mixed = apply(batch)
    after = revision()
    deleted = [
        edit({"action": "delete", "target": {**target, "eventId": eventId}}) for eventId in (event["eventId"], branch)
    ]
    suite.check(
        "K2",
        "An event named as target.eventId is updated by script_edit and by a scene_apply operation, read alone by "
        "script_inspect and deleted by script_edit; a different eventId beside it is refused, and a batch that "
        "creates an actor and edits a nested branch and that actor's script is refused with nothing applied when "
        "its last operation names another event in its input",
        event["eventId"] is not None
        and not refused(edited)
        and not refused(applied)
        and [(e.get("id"), (e.get("args") or {}).get("text")) for e in inspected.get("events") or []]
        == [(event["eventId"], "third")]
        and refused(conflicting)
        and "target.eventId" in error(conflicting)
        and branch is not None
        and not refused(staged)
        and refused(mixed)
        and "Operation 3" in error(mixed)
        and "eventId" in error(mixed)
        and before is not None
        and after == before
        and not any(refused(result) for result in deleted),
        inserted=inserted.get("event") or inserted.get("error"),
        edited=error(edited) if refused(edited) else "ok",
        applied=error(applied) if refused(applied) else "ok",
        inspected=inspected.get("events") or inspected.get("error"),
        conflicting=error(conflicting),
        staged=error(staged) if refused(staged) else "ok",
        mixed=error(mixed) if refused(mixed) else "applied",
        revisions=[before, after],
        deleted=[error(result) if refused(result) else "ok" for result in deleted],
    )
