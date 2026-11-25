"""What a game fetched from a link must be before it reaches the library. Standard library only.

``take_payload(checkout, game)`` moves exactly what the game's mode publishes out of the checked-out folder and nothing
else: for a game alone (``game``) its game files (``project.GAME_FILES``) and the ROM its ``game.json`` names; with its
source (``game+source``, the folder has one ``.gbsproj``) the ``.gbsproj`` and the source folders too. Everything else
(``build/web``, other build output, notes, a ``.hermretro/`` of someone else's) stays behind and is deleted with the
checkout, so no fetched browser code is ever served: the playable copy is made again here. A game alone that carries
source folders without a project is refused.

``check(game)`` then answers ``{ok, mode, card, rom, problems, warnings, needsPluginConsent}`` about that folder: a
hermretro game whose ROM a Chromatic cartridge can hold. Each finding is ``{code, path, message}``. Every file read
here is a regular file read with a size limit; links were refused before checkout (``install_git.tree_problems``).
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from . import cartridge, game_card, layout
from .game_cover import check_cover
from .project import GAME_FILES, canonical_rom

MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_FILES = 5000


def take_payload(checkout: Path, game: Path) -> tuple[str | None, list[dict]]:
    """Move the game's published files from ``checkout`` into the new folder ``game``. ``(mode, problems)``; with a
    problem nothing is moved."""
    checkout, game = Path(checkout), Path(game)
    card, problems = read_card(checkout)
    if problems:
        return None, problems
    names = _entries(checkout)
    projects = [name for name in names if name.endswith(".gbsproj")]
    sources = [name for name in names if name in layout.SOURCE_FOLDERS]
    if len(projects) > 1:
        return None, [_finding("PROJECTS", "", "The game has more than one .gbsproj; it must have one.")]
    if projects and not _regular(checkout / projects[0]):
        return None, [_finding("BAD_PROJECT", projects[0], f"{projects[0]} must be a file.")]
    if not projects and sources:
        return None, [_finding("SOURCE_WITHOUT_PROJECT", sources[0], "The game has source folders but no .gbsproj.")]
    mode = "game+source" if projects else "game"
    rom = card.get("rom")
    if rom not in layout.GAME_ROMS or not _regular(checkout / rom) or (checkout / "build").is_symlink():
        return None, [_finding("NO_ROM", str(rom or "game.json"), "game.json does not name a ROM the game has.")]
    taken = [name for name in GAME_FILES if _regular(checkout / name)] + [rom]
    if projects:
        taken += [projects[0], *(name for name in sources if (checkout / name).is_dir())]
    game.mkdir()
    (game / "build").mkdir()
    for name in taken:
        os.rename(checkout / name, game / name)
    return mode, []


def check(game: Path) -> dict:
    """Whether the folder ``take_payload`` made is a game this hermretro installs (module docstring)."""
    game = Path(game)
    problems, warnings = [], []
    _walk(game, problems)
    card, card_problems = read_card(game)
    problems += card_problems
    mode = "game+source" if any(name.endswith(".gbsproj") for name in _entries(game)) else "game"
    rom_info = None
    if not card_problems:
        rom = card.get("rom")
        if mode == "game+source" and rom != canonical_rom(game):
            problems.append(_finding("ROM_NAME", str(rom), f"The project builds {canonical_rom(game)}, not {rom}."))
        if mode == "game" and not _sha256_text(card.get("romSha256")):
            problems.append(_finding("NO_ROM_SHA", game_card.CARD_FILE, "game.json has no romSha256 for its ROM."))
        rom_info = _check_rom(game, rom, card, problems) if rom in layout.GAME_ROMS else None
        cover = game / game_card.COVER_FILE
        if not _regular(cover):
            problems.append(_finding("NO_COVER", game_card.COVER_FILE, "The game has no cover."))
        elif not (result := check_cover(cover))["ok"]:
            problems.append(_finding("COVER", game_card.COVER_FILE, result["problem"]))
    if mode == "game+source" and not (game / "project").is_dir() and "scenes" not in _project_json(game):
        problems.append(_finding("NO_SOURCE", "project", "The game's project/ folder is missing."))
    plugins = game / "plugins"
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
    """The folder's ``game.json``, strictly: a regular file of at most 64 KB holding a JSON object with a game id, a
    title and, when it says, a format this hermretro reads. Returns ``(card or {}, problems)``."""
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
        with path.open("rb") as handle:
            card = json.loads(handle.read(game_card.MAX_CARD_BYTES + 1).decode("utf-8"))
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
    if "romSha256" in card and not _sha256_text(card["romSha256"]):
        problems.append(_finding("CARD", game_card.CARD_FILE, "game.json's romSha256 is not a SHA-256."))
    return card, problems


def _check_rom(game: Path, rom: str, card: dict, problems: list) -> dict | None:
    path = game / rom
    if not _regular(path):
        problems.append(_finding("NO_ROM", rom, f"The game's ROM {rom} is missing."))
        return None
    info = cartridge.inspect(path)
    found = info["problems"] + cartridge.check_name(info, rom)
    problems += [_finding(problem["code"], rom, problem["message"]) for problem in found]
    digest = None
    if info["sizeBytes"] is not None and info["sizeBytes"] <= cartridge.MAX_ROM_BYTES:
        with path.open("rb") as handle:
            digest = hashlib.sha256(handle.read(cartridge.MAX_ROM_BYTES + 1)).hexdigest()
    expected = card.get("romSha256")
    if expected is not None and expected != digest:
        problems.append(_finding("ROM_CHANGED", rom, "The ROM is not the one its author published (romSha256)."))
    return {"path": rom, "sizeBytes": info["sizeBytes"], "sha256": digest, "title": info.get("title")}


def _walk(folder: Path, problems: list) -> None:
    """Refuse links, special files, oversized files and too much of everything, anywhere in the folder (the fetched
    tree was checked before checkout; this holds what was written)."""
    total = count = 0
    for directory, folders, names in os.walk(folder):
        here = Path(directory)
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
            elif not stat.S_ISDIR(info.st_mode):
                problems.append(_finding("SPECIAL_FILE", relative, f"{relative} is not a plain file."))
        folders[:] = [name for name in folders if not (here / name).is_symlink()]
    if total > MAX_TOTAL_BYTES:
        problems.append(_finding("TOO_BIG", "", "The game is larger than 50 MB."))
    if count > MAX_FILES:
        problems.append(_finding("TOO_MANY", "", f"The game has more than {MAX_FILES} files."))


def _regular(path: Path) -> bool:
    try:
        return stat.S_ISREG(Path(path).lstat().st_mode)
    except OSError:
        return False


def _sha256_text(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _entries(folder: Path) -> list[str]:
    try:
        return os.listdir(folder)
    except OSError:
        return []


def _project_json(folder: Path) -> dict:
    descriptor = next((Path(folder) / name for name in _entries(folder) if name.endswith(".gbsproj")), None)
    if descriptor is None or not _regular(descriptor) or descriptor.stat().st_size > 16 * 1024 * 1024:
        return {}
    try:
        data = json.loads(descriptor.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return {}
    return data if isinstance(data, dict) else {}


def _finding(code: str, path: str, message: str) -> dict:
    return {"code": code, "path": path, "message": message}
