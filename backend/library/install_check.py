"""What a game folder fetched from a link must be before it reaches the library: a hermretro game in its layout, whose
ROM a Chromatic cartridge can hold, with nothing in it that could reach outside it. Standard library only; reads the
folder and writes nothing.

``check(folder)`` answers ``{ok, mode, card, rom, problems, warnings, needsPluginConsent}``. ``mode`` is ``game+source``
when the folder has its ``.gbsproj``, else ``game``. Each finding is ``{code, path, message}``.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from . import cartridge, game_card, layout
from .game_cover import check_cover
from .project import GAME_FILES, canonical_rom, project_file

MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES = 5000
# Folders a fetched folder may hold that are never looked at: git's own (removed before the game is installed).
SKIPPED = frozenset({".git"})


def check(folder: Path) -> dict:
    folder = Path(folder)
    problems, warnings = [], []
    _walk(folder, problems)
    card, card_problems = read_card(folder)
    problems += card_problems
    mode = "game+source" if project_file(folder) is not None else "game"
    rom_info = None
    rom = card.get("rom") if card else None
    if card and rom not in layout.GAME_ROMS:
        problems.append(
            _finding("NO_ROM", "game.json", "game.json does not name the game's ROM (build/game.gbc or .gb).")
        )
    elif card:
        if mode == "game+source" and rom != canonical_rom(folder):
            problems.append(_finding("ROM_NAME", rom, f"The project builds {canonical_rom(folder)}, not {rom}."))
        rom_info = _check_rom(folder, rom, card, problems)
    if card:
        cover = folder / game_card.COVER_FILE
        if not cover.is_file():
            problems.append(_finding("NO_COVER", game_card.COVER_FILE, "The game has no cover."))
        elif not (result := check_cover(cover))["ok"]:
            problems.append(_finding("COVER", game_card.COVER_FILE, result["problem"]))
    if mode == "game+source" and not (folder / "project").is_dir() and "scenes" not in _project_json(folder):
        problems.append(_finding("NO_SOURCE", "project", "The game's project/ folder is missing."))
    for name in sorted(_entries(folder)):
        if name not in SKIPPED and name not in layout.LOCAL_FOLDERS and layout.kind_of(folder, name) == "local":
            warnings.append(
                _finding("UNKNOWN_ENTRY", name, f"{name} is not part of a game; it is kept but never used.")
            )
    plugins = folder / "plugins"
    consent = mode == "game+source" and plugins.is_dir() and any(path.is_file() for path in plugins.rglob("*"))
    return {
        "ok": not problems,
        "mode": mode,
        "card": card,
        "rom": rom_info,
        "problems": problems,
        "warnings": warnings,
        "needsPluginConsent": consent,
    }


def read_card(folder: Path) -> tuple[dict, list[dict]]:
    """The folder's ``game.json``, strictly: a JSON object of at most 64 KB with an id, a title and, when it says, a
    format this hermretro reads. Returns ``(card or {}, problems)``."""
    path = Path(folder) / game_card.CARD_FILE
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {}, [_finding("NO_CARD", game_card.CARD_FILE, "This is not a hermretro game: it has no game.json.")]
    except OSError as error:
        return {}, [_finding("CARD_UNREADABLE", game_card.CARD_FILE, f"game.json cannot be read: {error}.")]
    if not stat.S_ISREG(info.st_mode) or info.st_size > game_card.MAX_CARD_BYTES:
        return {}, [_finding("CARD_UNREADABLE", game_card.CARD_FILE, "game.json must be a file of at most 64 KB.")]
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as error:
        return {}, [_finding("CARD_UNREADABLE", game_card.CARD_FILE, f"game.json is not valid JSON: {error}.")]
    if not isinstance(card, dict):
        return {}, [_finding("CARD_UNREADABLE", game_card.CARD_FILE, "game.json must be a JSON object.")]
    problems = []
    form = card.get("format", 1)
    if type(form) is not int or form < 1:
        problems.append(_finding("FORMAT", game_card.CARD_FILE, "game.json has an unknown format."))
    elif form > layout.FORMAT_VERSION:
        problems.append(
            _finding("NEWER_FORMAT", game_card.CARD_FILE, "This game needs a newer hermretro; update hermretro first.")
        )
    if not (isinstance(card.get("id"), str) and layout.ID_PATTERN.match(card["id"])):
        problems.append(
            _finding("NO_ID", game_card.CARD_FILE, "game.json has no game id; it was not made by hermretro.")
        )
    if not (isinstance(card.get("title"), str) and card["title"].strip()):
        problems.append(_finding("CARD", game_card.CARD_FILE, "game.json has no title."))
    version = card.get("gameVersion")
    if version is not None and not (isinstance(version, str) and layout.VERSION_PATTERN.match(version)):
        problems.append(_finding("CARD", game_card.CARD_FILE, "game.json's gameVersion is not a version (1.2.3)."))
    return card, problems


def _check_rom(folder: Path, rom: str, card: dict, problems: list) -> dict | None:
    path = folder / rom
    if path.is_symlink() or not path.is_file():
        problems.append(_finding("NO_ROM", rom, f"The game's ROM {rom} is missing."))
        return None
    info = cartridge.inspect(path)
    found = info["problems"] + cartridge.check_name(info, rom)
    problems += [_finding(problem["code"], rom, problem["message"]) for problem in found]
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if info["sizeBytes"] else None
    expected = card.get("romSha256")
    if expected is not None and expected != digest:
        problems.append(_finding("ROM_CHANGED", rom, "The ROM is not the one its author published (romSha256)."))
    return {"path": rom, "sizeBytes": info["sizeBytes"], "sha256": digest, "title": info.get("title")}


def _walk(folder: Path, problems: list) -> None:
    """Refuse links, special files, oversized files and too much of everything, anywhere in the folder."""
    total = count = 0
    for directory, folders, names in os.walk(folder):
        here = Path(directory)
        if here == folder:
            folders[:] = [name for name in folders if name not in SKIPPED]
        for name in [*folders, *names]:
            path = here / name
            relative = path.relative_to(folder).as_posix()
            try:
                info = path.lstat()
            except OSError as error:
                problems.append(_finding("UNREADABLE", relative, f"{relative} cannot be read: {error}."))
                continue
            if stat.S_ISLNK(info.st_mode):
                problems.append(_finding("LINK", relative, f"{relative} is a link; a game holds only plain files."))
            elif stat.S_ISREG(info.st_mode):
                count += 1
                total += info.st_size
                if info.st_size > MAX_FILE_BYTES:
                    problems.append(_finding("TOO_BIG", relative, f"{relative} is larger than 20 MB."))
            elif not stat.S_ISDIR(info.st_mode):
                problems.append(_finding("SPECIAL_FILE", relative, f"{relative} is not a plain file."))
        folders[:] = [name for name in folders if not (here / name).is_symlink()]
    if total > MAX_TOTAL_BYTES:
        problems.append(_finding("TOO_BIG", "", "The game is larger than 50 MB."))
    if count > MAX_FILES:
        problems.append(_finding("TOO_BIG", "", f"The game has more than {MAX_FILES} files."))


def _entries(folder: Path) -> list[str]:
    try:
        return [name for name in os.listdir(folder) if name not in GAME_FILES]
    except OSError:
        return []


def _project_json(folder: Path) -> dict:
    descriptor = project_file(folder)
    try:
        data = json.loads(descriptor.read_text(encoding="utf-8")) if descriptor else {}
    except (OSError, ValueError, RecursionError):
        return {}
    return data if isinstance(data, dict) else {}


def _finding(code: str, path: str, message: str) -> dict:
    return {"code": code, "path": path, "message": message}
