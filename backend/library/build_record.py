"""What a game's ``game.json`` says about its last build: ``romSha256``, the SHA-256 of the ROM it made (what a published
game carries and an install checks), and ``builtWith``, what made it. Standard library only.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..system import paths
from . import game_card, layout
from .project import _json, canonical_rom, file_sha256

# The GB Studio file the toolchain's setup patches so a build's save signature is repeatable (its receipt names it).
SAVE_SIGNATURE_SOURCE = "src/lib/compiler/compileData.ts"


@game_card.locked
def record_build(root: Path, rom_path: str, rom_sha256: str, cli_path: str | None = None) -> bool:
    """After a successful build of the game's ROM (the build's own ``outputPath`` and ROM SHA-256): ``game.json``
    records that ROM's SHA-256 (``romSha256``, what a published game carries and an install checks) and what built it
    (``builtWith``, ``cli_path`` the GB Studio CLI the build ran). Nothing is recorded for another file than the game's
    ROM, or when the file there is no longer what the build made. A game made before every game had its card gets it
    first. Returns whether it wrote."""
    root = Path(root)
    rom = root / canonical_rom(root)
    try:
        if not rom.is_file() or rom.is_symlink() or not os.path.samefile(rom_path, rom):
            return False
        if file_sha256(rom) != rom_sha256:
            return False
    except (OSError, TypeError, ValueError):
        return False
    if not game_card.load(root):
        layout.ensure(root)
    card = game_card.load(root)
    if not card:
        return False
    fields = {"romSha256": rom_sha256, "builtWith": built_with(cli_path)}
    if all(layout.same(card.get(key), value) for key, value in fields.items()):
        return False
    game_card.set_fields(root, fields)
    return True


def built_with(cli_path: str | None = None) -> dict:
    """What built a game: the engine's version, and when the GB Studio CLI the build ran (``cli_path``) is the one the
    toolchain's setup installed, that setup's GB Studio version and commit and whether its save signature is the
    repeatable one (a game rebuilt from its source matches its author's ROM only with that). ``verified`` says whether
    the CLI was that one; a CLI it cannot vouch for (the engine may take a project's own toolchain) names no version."""
    found = {}
    engine = _json(paths.ENGINE_ROOT / "package.json").get("version")
    if isinstance(engine, str):
        found["engine"] = engine
    receipt = _json(paths.setup_root() / "receipts" / "cli.json")
    destination = receipt.get("destination")
    found["verified"] = (
        receipt.get("status") == "ready"
        and isinstance(destination, str)
        and isinstance(cli_path, str)
        and _inside(cli_path, destination)
    )
    if not found["verified"]:
        return found
    provenance = receipt.get("provenance") if isinstance(receipt.get("provenance"), dict) else {}
    if isinstance(receipt.get("version"), str):
        found["gbStudio"] = receipt["version"]
    if isinstance(provenance.get("sourceCommit"), str):
        found["gbStudioCommit"] = provenance["sourceCommit"]
    patches = provenance.get("buildMetadataPatches")
    found["repeatable"] = isinstance(patches, list) and any(
        isinstance(patch, dict) and patch.get("path") == SAVE_SIGNATURE_SOURCE for patch in patches
    )
    return found


def _inside(path: str, folder: str) -> bool:
    try:
        base = os.path.realpath(folder)
        return os.path.commonpath([os.path.realpath(path), base]) == base
    except (OSError, ValueError):
        return False
