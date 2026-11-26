"""Repeatable builds, on a worker of its own, from a copy of B's project (the smallest) in another folder, with other
inodes, as a game installed from its repository on another machine: its web compile and its build both give B's ROM, an
asset without a .gbsres does not change it from one build to the next, and the save signature follows the save layout:
an event's own `_v` arg, project engine code and a plugin's event script change it. Every build here is one a check
needs (the suite's time on a CI runner is close to its limit)."""

import hashlib
import json
import shutil
from pathlib import Path

from tests.acceptance.checkpoints import signature_bytes
from tests.acceptance.fixture import structured
from tests.support import encode_png

# A worker opens one project's folder only: the copy gets an owner (and a worker) of its own.
OWNER_R = {"profile": "s01-profile", "conversation_id": "conv-R"}


WHITE = (255, 255, 255, 255)

# A plugin's script event: GB Studio loads every plugins/**/events/event*.js, used or not.
PLUGIN_EVENT = (
    'const id = "HR_EVENT_REPEATABLE";\nconst fields = [];\nconst compile = () => {{}};\n'
    'module.exports = {{ id, name: "{name}", fields, compile }};\n'
)


def sha256(path) -> str | None:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if path and Path(path).is_file() else None


def select(client, root: Path) -> dict:
    """Open the project on its owner's worker; the answer when it is not opened."""
    selected = client.call(OWNER_R, "project_select", {"projectPath": str(root / "project.gbsproj")})
    status = structured(client.call(OWNER_R, "session_status"))
    opened = Path(status.get("projectRoot") or "/").resolve() == root.resolve()
    return {} if opened else {"error": selected}


def build(client, root: Path) -> dict:
    """A ROM build of the project at root, refused when its ROM lands anywhere else."""
    refused = select(client, root)
    built = refused or structured(client.call(OWNER_R, "rom_build", {}))
    rom = built.get("outputPath")
    if rom and not Path(rom).resolve().is_relative_to(root.resolve()):
        built = {"error": f"built {rom}, not in {root}"}
        rom = None
    return {"sha256": sha256(rom), "signature": signature_bytes(rom), **built}


def web_rom(client, root: Path) -> str | None:
    if select(client, root):
        return None
    built = structured(client.call(OWNER_R, "web_build", {"force": True}))
    rom = built.get("romPath")
    return sha256(rom) if rom and Path(rom).resolve().is_relative_to(root.resolve()) else None


def check_repeatable(suite, client, rom_b: str):
    """``rom_b``: B's ROM as B's last build made it, from the project as it is now."""
    copy = suite.work / "repeatable" / "elsewhere" / "deep" / "copy"
    shutil.copytree(
        suite.project_b, copy, ignore=shutil.ignore_patterns("build", "artifacts", "captures", "save-states")
    )
    original = sha256(rom_b)
    web = web_rom(client, copy)  # first, so there is no native ROM of the copy's own to adopt
    copied = build(client, copy)
    suite.check(
        "R1",
        "A byte-identical copy of a project in another folder, with other inodes, builds the original's ROM",
        bool(original) and copied.get("success") is True and copied["sha256"] == original,
        original=original,
        copy=copied["sha256"] or copied.get("error"),
    )
    suite.check(
        "R2",
        "The copy's web compile, with no native ROM to adopt, plays that same ROM",
        bool(original) and web == original,
        web=web,
        native=original,
    )
    # The copy's first build compiled everything; this one takes the compiled engine files from GB Studio's cache.
    rebuilt = build(client, copy)
    first_ms, again_ms = copied.get("durationMs"), rebuilt.get("durationMs")
    suite.check(
        "R9",
        "Building the copy again reuses GB Studio's cache of its first build, at least three times faster, and gives "
        "that same ROM",
        bool(original)
        and rebuilt.get("success") is True
        and rebuilt["sha256"] == original
        and isinstance(first_ms, int)
        and isinstance(again_ms, int)
        and again_ms * 3 < first_ms,
        original=original,
        rebuilt=rebuilt["sha256"] or rebuilt.get("error"),
        first_ms=first_ms,
        again_ms=again_ms,
    )

    unlisted_image = copy / "assets" / "backgrounds" / "unlisted.png"
    unlisted_image.parent.mkdir(parents=True, exist_ok=True)
    # No .gbsres beside it: GB Studio gives it a new random id on every load.
    unlisted_image.write_bytes(encode_png(160, 144, lambda x, y: (0, 0, 0, 255) if (x // 8 + y // 8) % 2 else WHITE))
    unlisted = [build(client, copy) for _ in range(2)]
    suite.check(
        "R3",
        "A project with an asset that has no .gbsres builds to the same ROM twice",
        all(entry.get("success") is True for entry in unlisted) and unlisted[0]["sha256"] == unlisted[1]["sha256"],
        sha256=[entry["sha256"] or entry.get("error") for entry in unlisted],
    )

    # Each build below adds one change to the one before it.
    scene = next((copy / "project" / "scenes").glob("*/scene.gbsres"))
    data = json.loads(scene.read_text())
    wait = {
        "command": "EVENT_WAIT",
        "args": {"time": {"type": "number", "value": 0.5}, "units": "time"},
        "id": "9c1a3d52-4b7e-4f0a-9e21-5d8c6b4a7f13",
    }
    scene.write_text(json.dumps({**data, "script": [*data.get("script", []), wait]}, indent=2))
    plugin_event = copy / "plugins" / "repeatable" / "events" / "eventRepeatable.js"
    plugin_event.parent.mkdir(parents=True)
    plugin_event.write_text(PLUGIN_EVENT.format(name="Repeatable"))
    base = build(client, copy)
    wait["args"]["_v"] = 1
    scene.write_text(json.dumps({**data, "script": [*data.get("script", []), wait]}, indent=2))
    with_arg = build(client, copy)
    override = copy / "assets" / "engine" / "include" / "repeatable_check.h"
    override.parent.mkdir(parents=True)
    override.write_text("/* engine code the project brings */\n")
    with_engine = build(client, copy)
    plugin_event.write_text(PLUGIN_EVENT.format(name="Repeatable again"))
    plugin_changed = build(client, copy)
    builds = (base, with_arg, with_engine, plugin_changed)
    signatures = [entry["signature"] for entry in builds]
    suite.check(
        "R4",
        "The save signature changes with an event's own _v arg, with engine code the project brings and with a plugin's "
        "event script",
        all(entry.get("success") is True for entry in builds) and all(signatures) and len(set(signatures)) == 4,
        signatures=signatures,
        errors=[entry.get("error") for entry in builds if entry.get("error")],
    )
