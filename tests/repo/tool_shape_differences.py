"""The fields of the pinned engine tools that really differ from others of their name, by path, each with why.

tests/repo/test_tool_shapes.py reads these. A path is the tool, then each field: ``[]`` for array items and
``anyOf[i]`` for a field's forms.
"""

# Path: why the field means something of its own, so it is compared with no other field of its name.
OWN = {
    "web_preview.action": "the browser preview's own verbs",
    "device_capture.action": "the capture device's own verbs",
    "emulator_checkpoint.action": "save or restore a checkpoint",
    "emulator_recording.action": "the recording store's own verbs",
    "tilemap_atlas_create.primitives[].cells": "an atlas primitive's grid of tiles, not tilemap_edit's cell edits",
    "rom_build.colorMode": "the hardware a ROM targets (dmg, gbc, gbc-only), not a project's or art's color mode",
    "setup.command": "setup's own commands; device's are different",
    "project_inventory.cursor": "its cursor carries the inventory's filters, so it is longer",
    "event_describe.cursor": "the event catalog's cursor is a position, digits only",
    "project_inventory.detail": "the inventory's own levels: summary, standard and full",
    "graphics_analyze_scene.detail": "a scene analysis in summary or per tile",
    "world_dependencies.direction": "links followed incoming or outgoing, not a facing",
    "emulator_replay.expect.frames": "whether a replayed check must match the recording frame for frame, not a frame count",
    "device_capture.durationMs": "a recording's length, at least 1 s; web_preview's is a button press",
    "palette_paint.edits": "palette slot rectangles, not collision edits",
    "music_compose.sections[].wave.anyOf[1].instrument": "the wave channel's own instruments",
    "graphics_analyze.kind": "what is analyzed (tilesets too, no music or sound), not what is imported",
    "tilemap_inspect.offset": "a page start within a tilemap, not a memory offset",
    "scene_apply.operations": "scene_apply's operations, not tilemap_edit's",
    "asset_import.sprite.anyOf[1].profile": "the native-metadata form's only profile",
    "music_compose.instruments.pulse1": "the channel's default instrument, not a section's notes",
    "music_compose.instruments.pulse2": "the channel's default instrument, not a section's notes",
    "music_compose.instruments.wave": "the channel's default instrument, not a section's notes",
    "event_describe.query": "a search of the event catalog, not of the project",
    "web_preview.installationBinding.requestId": "an install binding's UUID, not a hardware request",
    "setup.sessionId": "setup's own session, not an emulator session",
    "scene_create.symbol": "a scene's compiler symbol; scene_apply's operations name variable symbols",
    "variable_set.symbol": "var_ and a C name, checked in the schema; scene_apply's operations check it when they run",
    "palette_assign.target": "names background or sprite palettes, not a script",
    "scene_apply.operations[].type": "scene_apply's operation kinds",
    "world_dependencies.node.type": "the kinds of node in the project graph",
    "engine_field_update.updates[].value": "an engine field's value, text or a number; elsewhere a collision byte",
    "emulator_clip.maxFrames": "a clip's length, at most 600 frames; elsewhere a recording's cap",
}

# Why: the fields of one name that share a meaning of their own; they are compared only with each other.
GROUPS = {
    "the whole-project revision as its SHA-256; the others take any revision string": [
        "settings_update.expectedRevision",
        "tilemap_atlas_create.expectedRevision",
        "tilemap_create.expectedRevision",
        "tilemap_edit.expectedRevision",
        "tilemap_compile.expectedRevision",
    ],
    "an atlas's own names for its tiles and primitives": [
        "tilemap_atlas_create.tiles[].id",
        "tilemap_atlas_create.primitives[].id",
    ],
    "a branch as branch-0001, checked in the schema; emulator_recording and emulator_clip take any identifier": [
        "emulator_replay.branchId",
        "emulator_review.branchId",
    ],
    "dialogue's wrap profiles": ["dialogue_analyze.profile", "dialogue_preview.profile"],
    "a sprite preview's zoom: sprites are small, so up to 8; emulator frames up to 4": [
        "sprite_preview.scale",
        "sprite_contact_sheet.scale",
    ],
    "tilemap_create's base forms": ["tilemap_create.base.anyOf[0].type", "tilemap_create.base.anyOf[1].type"],
    "tilemap_edit's operation kinds": [f"tilemap_edit.operations[].anyOf[{index}].type" for index in range(6)],
    "a scene's place in the editor's world, which may be below 0": [
        "scene_create.x",
        "scene_create.y",
        "scene_update.x",
        "scene_update.y",
    ],
    "a tile of a tilemap or its atlas, from 0 to 254": [
        *(
            f"{path}.{axis}"
            for axis in "xy"
            for path in (
                "tilemap_atlas_create.tiles[]",
                "tilemap_atlas_create.primitives[].anchor",
                "tilemap_create.protectedRegions[]",
                "tilemap_inspect",
                "tilemap_edit.operations[].anyOf[1]",
                "tilemap_edit.operations[].anyOf[2]",
                "tilemap_edit.operations[].anyOf[3]",
                "tilemap_edit.operations[].anyOf[4].cells[]",
                "tilemap_edit.operations[].anyOf[5].cells[]",
            )
        ),
    ],
    "a variable's ID as a canonical decimal string; scene_apply's operations check it when they run": [
        "variable_inspect.variableId",
        "variable_set.variableId",
        "variable_delete.variableId",
    ],
}

# Path: why the field accepts less than the others of its name and meaning (each of them accepts all it does).
NARROWER = {
    "script_transition.target": "names no event: a transition is inserted, not an edit of one",
    "asset_import.assets[].sprite": "a batch item imports with a profile, never from native metadata",
    "music_compose.sections[].name": "a section label, at most 32 characters",
    "emulator_inspect.limit": "OAM has 40 objects",
    "emulator_recording.limit": "an export's page of actions, at most 128",
    "tilemap_inspect.limit": "a page of a tilemap's cells, at most 128",
    "dialogue_update.text": "stores at most 10,000 characters a text; dialogue_analyze and dialogue_preview read 20,000",
    "tilemap_atlas_create.primitives[].width": "a primitive is at most 32 tiles wide",
    "tilemap_atlas_create.primitives[].height": "a primitive is at most 32 tiles high",
}

# Path: why the field accepts more than the others of its name and meaning (it accepts all each of them does).
# scene_apply's operations share one field of each name across every operation type; each operation checks its own
# values when it runs, and schemas of their own per operation are a change of their own.
WIDER = {
    "scene_apply.operations[].action": "variable operations also upsert",
    "scene_apply.operations[].edits": "may be empty; collision.edit refuses no edits when it runs",
    "scene_apply.operations[].x": "one x for every operation, to 65535; actors and triggers are kept inside the scene",
    "scene_apply.operations[].y": "one y for every operation, to 65535; actors and triggers are kept inside the scene",
    "scene_apply.operations[].width": "one width for every operation, to 4096; triggers are kept inside the scene",
    "scene_apply.operations[].height": "one height for every operation, to 4096; triggers are kept inside the scene",
    "emulator_debug.collisions.width": "a read of at most 256 tiles, one row of them too; it must fit inside the scene",
    "emulator_debug.collisions.height": "a read of at most 256 tiles, one column of them too; it must fit inside the scene",
}
