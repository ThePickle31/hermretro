"""The ROM a game plays in the player's shell instead of its own web export. Standard library only.

The shell is the GB Studio browser player bundled with hermretro (``player/web``, the demo cartridge's): only the ROM
changes. A game installed from a link always plays there, never from a web export, with its source or without: a web
export is GB Studio's ``index.html`` with the project's settings in it, and GB Studio's custom HTML header setting
lets a project put its author's script there, so a copy built here from imported source could still run that author's
JavaScript in the player. A game made here plays its web export.

A game without its source (installed so, or the edited copy an update kept of one, ``keep_rom``) is its checked ROM
and nothing else: it plays, and is flashed, only while that file is still the bytes its record names
(``rom_only_record``). Every ROM the shell plays is read once (``verified``: a regular file in the game's folder,
reached through no link, at most a cartridge's size) and those very bytes are hashed and served.
"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from . import freshness, layout, release
from .cartridge import MAX_ROM_BYTES
from .project import ROM_STEM

# The record the edited copy of a game installed without its source keeps (an update's keep_both): the ROM it was
# installed with and where it came from, so it still plays that ROM once it is a game of its own.
KEPT_ROM_FILE = "kept-rom.json"
# An installed game with its source is shown again after a build: it has no web copy to make.
ROM_BUILD = "Run chromatic_rom_build for this project, then call chromatic_present_game again."
GAME_ROMS = (ROM_STEM + ".gbc", ROM_STEM + ".gb")


def is_installed(root: Path) -> bool:
    """Whether the game was installed from a link (``release.installed``), with its source or without."""
    return release.installed(root) is not None


def rom_only_record(root: Path) -> dict | None:
    """For a game without its source (installed so, or kept from one), its checked ROM: ``{path, sha256, source,
    commit}`` (``path`` relative to the game). None for any other game."""
    record = release.installed(root)
    if record is not None:
        rom = record.get("rom") if record["mode"] == "game" else None
        found = {**rom, "source": record["source"].get("canonical"), "commit": record.get("commit")} if rom else None
    else:
        found = layout.state(root, KEPT_ROM_FILE) or None
    if not isinstance(found, dict) or found.get("path") not in GAME_ROMS or not isinstance(found.get("sha256"), str):
        return None
    return found


def plays_in_shell(root: Path) -> bool:
    """Whether the player plays this game's ROM in the shell: a game installed from a link, or kept from one."""
    return is_installed(root) or rom_only_record(root) is not None


def keep_rom(root: Path, record: dict) -> None:
    """Keep ``rom_only_record`` for the edited copy of a game installed without its source, now a game of its own."""
    layout.write_state(root, KEPT_ROM_FILE, record)


def read_rom(root: Path, relative: str) -> bytes | None:
    """The bytes of the game's ROM ``relative`` (``build/game.gb[c]``), read once: a regular file inside the game's own
    folder, reached through no link, at most ``MAX_ROM_BYTES``. None otherwise."""
    if relative not in GAME_ROMS:
        return None
    base = Path(os.path.realpath(root))
    path = base / relative
    if os.path.realpath(path) != str(path):  # a link anywhere on the way
        return None
    try:
        handle = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        return None
    try:
        info = os.fstat(handle)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ROM_BYTES:
            return None
        with os.fdopen(handle, "rb", closefd=False) as stream:
            data = stream.read(MAX_ROM_BYTES + 1)
        return data if len(data) <= MAX_ROM_BYTES else None
    finally:
        os.close(handle)


def verified(root: Path) -> dict | None:
    """The ROM the shell plays, read once: ``{relative, bytes, sha256, builtAt}``. A game without its source: its
    checked ROM while it is those bytes; otherwise the game's own ``build/game.gb[c]`` (the newer when both are there).
    None when there is none."""
    checked = rom_only_record(root)
    if checked is not None:
        candidates = [checked["path"]]
    else:
        present = [name for name in GAME_ROMS if (Path(root) / name).is_file()]
        candidates = sorted(present, key=lambda name: (Path(root) / name).stat().st_mtime, reverse=True)[:1]
    for relative in candidates:
        data = read_rom(root, relative)
        if data is None:
            continue
        sha256 = hashlib.sha256(data).hexdigest()
        if checked is not None and sha256 != checked["sha256"]:
            return None
        return {"relative": relative, "bytes": data, "sha256": sha256, "builtAt": _mtime(Path(root) / relative)}
    return None


def shell_rom(root: Path) -> Path | None:
    """Where ``verified``'s ROM is (its bytes may change after; read them with ``verified``)."""
    found = verified(root)
    return Path(root) / found["relative"] if found else None


def no_shell_rom(root: Path) -> str:
    """Why the shell has no ROM to play for this game, for the player."""
    if rom_only_record(root) is not None:
        return "The ROM this game was installed with is missing or changed. Update the game to get it back."
    return "This game has no ROM yet. Ask Hermes in its chat to build the game, then press Play again."


def playable_freshness(
    root: Path, last_build: dict | None = None, last_web_export: dict | None = None, sources: str | None = None
) -> tuple[bool, str | None, str | None]:
    """``freshness.export_freshness`` for any game: one the shell plays is current when it has its ROM and, with its
    source, no source changed after that ROM (it has no web copy to keep current)."""
    if not plays_in_shell(root):
        return freshness.export_freshness(root, last_build, last_web_export, sources)
    found = verified(root)
    if found is None:
        return False, no_shell_rom(root), None
    if rom_only_record(root) is None and freshness.sources_newer_than(root, found["builtAt"]):
        return False, "The game's sources changed after its ROM was built.", ROM_BUILD
    return True, None, None


def playable_intact(root: Path) -> bool:
    """Whether the game has a playable copy of some build (``freshness.intact_export``; its ROM, for the shell)."""
    return verified(root) is not None if plays_in_shell(root) else freshness.intact_export(root)


def shell_artifacts(root: Path, artifacts: dict) -> dict:
    """The games RPC's ``rom``, ``webExport`` and ``web`` for a game the shell plays: the ROM it plays, as the page's
    player reads a web export's (``web.sha256`` is what it plays). A game without its source has no other ROM: when
    its checked ROM changed it has none. Unchanged for a game that plays its web export."""
    if not plays_in_shell(root):
        return artifacts
    found = verified(root)
    rom = (
        {
            "path": str(Path(root) / found["relative"]),
            "sha256": found["sha256"],
            "size": len(found["bytes"]),
            "builtAt": int(found["builtAt"]),
        }
        if found
        else None
    )
    web = {"sha256": rom["sha256"], "builtAt": rom["builtAt"]} if rom else None
    if rom_only_record(root) is not None:
        artifacts = {**artifacts, "rom": rom}
    return {**artifacts, "webExport": web is not None, "web": web, "shell": True}


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
