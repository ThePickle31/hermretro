"""Checkpoints across rebuilds on B's worker: restored onto a build that differs only in GB Studio's save signature
(an editor-only change) only with symbols each build captured, never onto a changed one, and a branch restored from
another build is not replayed past that restore."""

import json
import re
import shutil
from pathlib import Path

from tests.acceptance.fixture import OWNER_B, move_scene_on_map, structured

# Each recording reserves its maxBytes against the project's 1 GiB of retained attempts; these need little.
SMALL = {"maxBytes": 4 * 1024 * 1024}

# A standalone GBDK program: no GB Studio build, so no symbols of its own.
GBDK_SOURCE = "#include <gb/gb.h>\n\nvoid main(void) {\n    DISPLAY_ON;\n    while (1) vsync();\n}\n"


def refused(response) -> bool:
    return response["result"].get("isError") is True


def save_signature(rom_path: str) -> int | None:
    """Where the build's linker symbols put GB Studio's 4-byte save signature."""
    symbols = Path(f"{rom_path}.debug/symbols.noi")
    found = (
        re.findall(r"^DEF _save_signature (0x[0-9A-Fa-f]+)$", symbols.read_text(), re.M) if symbols.is_file() else []
    )
    return int(found[0], 16) if len(found) == 1 else None


def signature_bytes(rom_path) -> str | None:
    """The build's 4-byte save signature, found from the symbols the build captured beside its ROM."""
    offset = save_signature(str(rom_path)) if rom_path else None
    return Path(rom_path).read_bytes()[offset : offset + 4].hex() if offset is not None else None


def stamp_only(before: bytes, after: bytes, signature: int | None) -> list[int] | None:
    """The bytes two ROMs differ in, when those are only GB Studio's build stamp; else None."""
    if signature is None or len(before) != len(after):
        return None
    differing = [i for i, (old, new) in enumerate(zip(before, after, strict=True)) if old != new]
    stamped = set(range(signature, signature + 4)) | {0x14E, 0x14F}
    return differing if differing and set(differing) <= stamped else None


def save_checkpoint(client_b, rom_path: str) -> dict:
    client_b.call(OWNER_B, "emulator_run", {"romPath": rom_path, "recording": SMALL})
    client_b.call(
        OWNER_B, "emulator_step", {"inputs": [{"buttons": ["right"], "frames": 6}, {"buttons": [], "frames": 1}]}
    )
    return structured(client_b.call(OWNER_B, "emulator_checkpoint", {"action": "save"}))


def restore(client_b, rom_path: str, checkpoint: dict) -> dict:
    client_b.call(OWNER_B, "emulator_run", {"romPath": rom_path, "recording": SMALL})
    return client_b.call(OWNER_B, "emulator_checkpoint", {"action": "restore", **checkpoint})


def check_signature_only_rebuild(suite, client_b, rom_b) -> dict:
    """A checkpoint saved on one build restores onto a build that differs from it only in its save signature."""
    # Build the project as it is now, then again after an editor-only change: a rebuild of the unchanged project gives
    # the same bytes, which the worker matches by their hash before it looks at any symbols.
    first = structured(client_b.call(OWNER_B, "rom_build", {}))
    saved = save_checkpoint(client_b, rom_b)
    before = Path(rom_b).read_bytes()
    move_scene_on_map(suite.project_b)
    rebuilt = structured(client_b.call(OWNER_B, "rom_build", {}))
    signature = save_signature(rom_b)
    differing = stamp_only(before, Path(rom_b).read_bytes(), signature)
    checkpoint = {"checkpointId": saved.get("checkpointId"), "recordingPath": saved.get("recordingPath")}
    restored_response = restore(client_b, rom_b, checkpoint)
    restored = structured(restored_response)
    onward = structured(client_b.call(OWNER_B, "emulator_step", {"inputs": [{"buttons": [], "frames": 2}]}))
    suite.check(
        "M18",
        "Two builds an editor-only change apart differ only in GB Studio's save signature and the global checksum, "
        "and a checkpoint saved on one restores onto the other",
        first.get("success") is not False
        and rebuilt.get("success") is not False
        and bool(saved.get("checkpointId"))
        and differing is not None
        and not refused(restored_response)
        and restored.get("frame") == saved.get("frame")
        and restored.get("romSha256") != saved.get("romSha256")
        and onward.get("frame") == saved.get("frame", 0) + 2,
        save_signature=hex(signature) if signature is not None else None,
        differing=[hex(i) for i in (differing or [])[:16]],
        saved_frame=saved.get("frame") or saved.get("error"),
        restored=restored.get("frame") or restored.get("error"),
        onward_frame=onward.get("frame"),
    )
    return {"checkpoint": checkpoint, "saved": saved, "rom": before, "restored": restored}


def check_restored_replay(suite, client_b, rom_b, cross: dict):
    """A branch restored from another build replays from a clean boot only up to that restore."""
    branch = cross["restored"].get("recording", {})
    restored_at = (
        json.loads(Path(cross["saved"]["path"]).read_text())["actionCount"] if "path" in cross["saved"] else None
    )
    selection = {"romPath": rom_b, "recordingPath": branch.get("recordingPath"), "branchId": branch.get("branchId")}
    declined = client_b.call(OWNER_B, "emulator_replay", selection)
    prefix = structured(client_b.call(OWNER_B, "emulator_replay", {**selection, "toActionIndex": restored_at}))
    suite.check(
        "M20",
        "A branch restored from a checkpoint of another build is declined past that restore and replays up to it",
        refused(declined)
        and "another build" in str(structured(declined).get("error"))
        and prefix.get("replay", {}).get("status") == "matched"
        and prefix.get("replay", {}).get("replayedActions") == restored_at,
        declined=structured(declined).get("error"),
        restored_at=restored_at,
        prefix=prefix.get("replay") or prefix.get("error"),
    )


def check_unverified_symbols(suite, client_b, rom_b, cross: dict):
    """A rebuild whose symbols this session did not capture with it takes no checkpoint of another build, even with
    an earlier build's symbols beside it; a GBDK ROM with copied symbols matches only itself."""
    stale = Path(f"{rom_b}.debug/symbols.noi")
    # The project as it is would build the bytes whose symbols the last build recorded.
    move_scene_on_map(suite.project_b)
    plain = structured(client_b.call(OWNER_B, "rom_build", {"captureDebugArtifacts": False}))
    differing = stamp_only(cross["rom"], Path(rom_b).read_bytes(), save_signature(rom_b))
    stale_refusal = restore(client_b, rom_b, cross["checkpoint"])
    suite.check(
        "M21",
        "A rebuild without symbols captured in this session refuses another build's checkpoint, stale symbols beside it",
        plain.get("success") is not False
        and stale.is_file()
        and differing is not None
        and refused(stale_refusal)
        and "no symbols" in str(structured(stale_refusal).get("error")),
        differing=[hex(i) for i in (differing or [])[:16]],
        error=structured(stale_refusal).get("error"),
    )

    source = suite.project_b / "gbdk" / "hello.c"
    source.parent.mkdir(exist_ok=True)
    source.write_text(GBDK_SOURCE)
    gbdk = structured(client_b.call(OWNER_B, "rom_build", {"sourcePath": "gbdk/hello.c"}))
    rom = gbdk.get("outputPath")
    copied = Path(f"{rom}.debug") if rom else None
    if copied is not None:
        shutil.copytree(stale.parent, copied, dirs_exist_ok=True)
    saved = save_checkpoint(client_b, rom) if rom else {}
    metadata = json.loads(Path(saved["path"]).read_text()) if "path" in saved else {}
    suite.check(
        "M22",
        "A standalone GBDK ROM with another build's symbols beside it runs and checkpoints under its exact identity only",
        gbdk.get("success") is True
        and gbdk.get("builder") == "gbdk"
        and bool(metadata)
        and metadata.get("romSha256") == saved.get("romSha256")
        and "romUnstampedSha256" not in metadata,
        build=gbdk.get("stderr") or gbdk.get("success"),
        checkpoint=sorted(metadata) or saved.get("error"),
    )


def check_archived_checkpoint(suite, client_b, rom_b, cross: dict):
    """A checkpoint kept in an archived recording restores onto a verified rebuild."""
    client_b.call(OWNER_B, "emulator_close", {})
    archived = structured(
        client_b.call(
            OWNER_B, "emulator_recording", {"action": "archive", "recordingPath": cross["checkpoint"]["recordingPath"]}
        )
    )
    rebuilt = structured(client_b.call(OWNER_B, "rom_build", {}))
    restored_response = restore(client_b, rom_b, cross["checkpoint"])
    restored = structured(restored_response)
    suite.check(
        "M23",
        "A checkpoint in an archived recording restores onto a rebuild that differs only in its save signature",
        archived.get("status") == "archived"
        and rebuilt.get("success") is not False
        and Path(rom_b).read_bytes() != cross["rom"]
        and not refused(restored_response)
        and restored.get("frame") == cross["saved"].get("frame"),
        archived=archived.get("status") or archived.get("error"),
        restored=restored.get("frame") or restored.get("error"),
    )


def check_changed_rebuild(suite, client_b, cross: dict):
    """After a real change the same checkpoint is refused: only the build stamp may differ."""
    refused_restore = client_b.call(OWNER_B, "emulator_checkpoint", {"action": "restore", **cross["checkpoint"]})
    suite.check(
        "M19",
        "A checkpoint is refused on a build of a changed project",
        refused(refused_restore) and "ROM identity is incompatible" in str(structured(refused_restore).get("error")),
        error=structured(refused_restore).get("error"),
    )
