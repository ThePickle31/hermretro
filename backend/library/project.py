"""Project files, build artifacts and playable-copy freshness. Standard library only."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import threading
from pathlib import Path

from . import game_card

# Folders under a project that hold build output, recordings or tooling, never game source.
NOT_SOURCE = frozenset({"build", "captures", "save-states", "artifacts", "node_modules", "__pycache__", "docs"})
# How many source files sources_newer_than looks at before it stops and calls the ROM current. Its own bound, not the
# snapshot cap (backend/history/snapshots.py MAX_FILES, which skips the copy): the two only happen to share a number.
MAX_SOURCE_FILES = 20000
# File times of a build and the web export made right after it can differ by a little.
FRESH_SLACK_SECONDS = 2.0
# The record the engine writes into each web export it makes (engine/modretro-chromatic/dist/web-build.js).
WEB_MANIFEST = ".codex-web-build.json"
# The game's one ROM, without its extension (``canonical_rom``).
ROM_STEM = "build/game"


_hash_cache: dict[tuple, str] = {}
_hash_lock = threading.Lock()


def game_id(root: str | os.PathLike) -> str:
    """Stable id of a project: the first 12 hex digits of SHA-1 over its canonical root."""
    return hashlib.sha1(os.path.realpath(str(root)).encode()).hexdigest()[:12]


def valid_id(value) -> bool:
    return isinstance(value, str) and len(value) == 12 and all(c in "0123456789abcdef" for c in value)


def identified_game(identifier: str, entry: dict) -> dict:
    """Use the registry key even when a stored record names a different id."""
    return {**entry, "id": identifier}


def _file_stamp(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def file_sha256(path: Path) -> str:
    key = (str(path), *_file_stamp(path.stat()))
    with _hash_lock:
        known = _hash_cache.get(key)
    if known:
        return known
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        before = _file_stamp(os.fstat(handle.fileno()))
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
        after = _file_stamp(os.fstat(handle.fileno()))
    value = digest.hexdigest()
    if before == after:
        with _hash_lock:
            if len(_hash_cache) > 256:
                _hash_cache.clear()
            _hash_cache[(str(path), *before)] = value
    return value


def timestamp(value, default=0.0):
    try:
        return float(value) if type(value) in (int, float) and math.isfinite(value) else default
    except OverflowError:
        return default


def project_file(root: Path) -> Path | None:
    try:
        return next(iter(sorted(root.glob("*.gbsproj"))), None)
    except OSError:
        return None


def project_kind(root: Path) -> str:
    return "gbstudio" if project_file(root) else "gbdk"


def _json(path: Path, *, required: bool = False) -> dict:
    try:
        if _file_info(path) is None:
            if required:
                raise FileNotFoundError(f"{path.name} is missing.")
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object.")
        return value
    except (ValueError, RecursionError) as error:
        if required:
            raise OSError(f"Could not read {path.name}: {error}") from error
    except OSError:
        if required:
            raise
    return {}


def project_title(root: Path, fallback: str | None = None) -> str:
    project = project_file(root)
    if project:
        name = _json(project).get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()[:200]
    exported = _json(web_dir(root) / "gbstudio.json").get("project")
    name = exported.get("name") if isinstance(exported, dict) else None
    if isinstance(name, str) and name.strip():
        return name.strip()[:200]
    return fallback if isinstance(fallback, str) and fallback else root.name


def web_dir(root: Path) -> Path:
    return root / "build" / "web"


def has_web_export(root: Path) -> bool:
    web = web_dir(root)
    return _file_info(web / "index.html") is not None and _file_info(web / "js" / "binjgb.wasm") is not None


def _file_info(path: Path) -> os.stat_result | None:
    try:
        info = path.stat()
    except (FileNotFoundError, NotADirectoryError, UnicodeEncodeError):
        return None
    return info if stat.S_ISREG(info.st_mode) else None


def project_exists(root: Path) -> bool:
    """Confirm absence with stat, leaving permission and other I/O failures for the caller."""
    try:
        return stat.S_ISDIR(root.stat().st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False


def web_rom(root: Path, *, required: bool = False) -> Path | None:
    """The ROM inside the web export, from its ``gbstudio.json`` (path-checked)."""
    web = web_dir(root)
    try:
        rel = _json(web / "gbstudio.json", required=required).get("rom")
        if (
            isinstance(rel, str)
            and "\x00" not in rel
            and not rel.startswith("/")
            and ".." not in rel.split("/")
            and rel.lower().endswith((".gb", ".gbc"))
        ):
            path = web / rel
            if _file_info(path) is not None and path.resolve().is_relative_to(web.resolve()):
                return path
    except RuntimeError as error:  # a symlink loop on Python 3.11 and 3.12
        if required:
            raise OSError("Could not resolve the web build's ROM.") from error
    except OSError:
        if required:
            raise
    if required:
        raise OSError("The web build names no readable ROM inside it.")
    return None


def canonical_rom(root: Path) -> str:
    """The game's one ROM, relative to its project: every build of the project writes it (the broker sets
    ``chromatic_rom_build``'s ``outputPath``). ``build/game.gb`` for a monochrome project (``colorMode`` ``mono``
    in ``project/settings.gbsres``), else ``build/game.gbc``."""
    mode = _json(Path(root) / "project" / "settings.gbsres").get("colorMode")
    return ROM_STEM + (".gb" if mode == "mono" else ".gbc")


def _game_rom(root: Path) -> tuple[Path, float] | None:
    """The game's ROM (``canonical_rom``) and its file time; None when it has not been built."""
    path = root / canonical_rom(root)
    try:
        info = _file_info(path)
    except OSError:
        return None
    return (path, info.st_mtime) if info is not None else None


def _rom_info(path: Path | None) -> tuple[dict | None, float | None]:
    if path is None or (info := _file_info(path)) is None:
        return None, None
    try:
        sha256 = file_sha256(path)
    except (FileNotFoundError, NotADirectoryError):
        return None, None
    return {"path": str(path), "sha256": sha256, "size": info.st_size, "builtAt": int(info.st_mtime)}, info.st_mtime


def _recorded_rom(last: dict) -> tuple[dict | None, float | None]:
    recorded = last.get("rom")
    if last.get("ok") is True and isinstance(recorded, str) and "\x00" not in recorded:
        path = Path(recorded)
        if path.is_absolute():
            try:
                return _rom_info(path)
            except OSError:
                pass
    return None, None


def _native_rom_info(root: Path) -> tuple[dict | None, float | None]:
    found = _game_rom(root)
    try:
        return _rom_info(found[0]) if found else (None, None)
    except OSError:
        return None, None


def build_artifacts(root: Path, last: dict, *, require_web_rom: bool = False) -> tuple[dict, float | None]:
    """The game's ROM and the web export's. The ROM is the canonical one; a game last built before every build
    wrote it falls back to the ROM its last recorded build made, then to the web export's."""
    exported = has_web_export(root)
    required = exported and require_web_rom
    try:
        web_rom_info, web_time = _rom_info(web_rom(root, required=required))
    except OSError:
        if required:
            raise
        web_rom_info, web_time = None, None
    if required and web_rom_info is None:
        raise OSError("The web build's ROM is unavailable.")
    rom, built = _native_rom_info(root)
    if rom is None:
        rom, built = _recorded_rom(last)
    if rom is None:
        rom, built = web_rom_info, web_time
    web = {"sha256": web_rom_info["sha256"], "builtAt": web_rom_info["builtAt"]} if exported and web_rom_info else None
    return {"rom": rom, "webExport": exported, "web": web}, built


def web_export_time(root: Path) -> float | None:
    """When the playable web copy was written: its ROM's file time (else its ``index.html``)."""
    if not has_web_export(root):
        return None
    target = web_rom(root) or (web_dir(root) / "index.html")
    try:
        return target.stat().st_mtime
    except OSError:
        return None


def engine_made_export(root: Path) -> bool:
    """Whether ``build/web`` is the engine's own export, unchanged: its ``.codex-web-build.json`` lists the
    ROM and ``index.html`` it wrote, with their hashes, and both files still match. A copy assembled or edited
    by hand has no such record, or one whose hashes no longer match."""
    web = web_dir(root)
    manifest = _json(web / WEB_MANIFEST)
    files = manifest.get("files")
    rom = web_rom(root)
    if not isinstance(files, list) or rom is None or manifest.get("indexPath") != "index.html":
        return False
    if manifest.get("romPath") != rom.relative_to(web).as_posix():
        return False
    hashes = {
        item["path"]: item.get("sha256")
        for item in files
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    for relative in ("index.html", manifest["romPath"]):
        try:
            # The bytes as they are now, never a cached digest: a swapped file can keep its size and time.
            current = hashlib.sha256((web / relative).read_bytes()).hexdigest()
        except OSError:
            return False
        if current != hashes.get(relative):
            return False
    return True


def _plays_rom(root: Path, rom: Path) -> bool:
    """Whether the web export's ROM is byte for byte ``rom``: the engine writes the ROM the last build made into
    every export of the same sources (``engine/CHANGES.md``)."""
    played = web_rom(root)
    try:
        return played is not None and file_sha256(played) == file_sha256(rom)
    except OSError:
        return False


# What a GB Studio web export is made from (the engine's own source fingerprint covers the same).
EXPORT_SOURCES = ("project", "assets", "plugins")


def source_digest(root: Path) -> str | None:
    """A digest of what the playable copy is made from: the ``.gbsproj`` and every file under ``project/``,
    ``assets/`` and ``plugins/``, by path and content. A deleted or renamed file changes it too; the card, the
    plans and the README do not. None for a project that is not GB Studio's, or past ``MAX_SOURCE_FILES``."""
    descriptor = project_file(root)
    if descriptor is None:
        return None
    digest = hashlib.sha256(b"hermretro\0export-sources\0v1\0")
    seen = 0
    files = [descriptor]
    for folder in EXPORT_SOURCES:
        for directory, folders, names in os.walk(root / folder):
            folders.sort()
            files += [Path(directory, name) for name in sorted(names)]
    for path in files:
        seen += 1
        if seen > MAX_SOURCE_FILES:
            return None
        try:
            if path.is_symlink() or not path.is_file():
                continue
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + file_sha256(path).encode() + b"\0")
        except OSError:
            continue
    return digest.hexdigest()


# What to do about a stale playable copy, by why it is stale.
_REBUILD = (
    "Run chromatic_rom_build for this project (with the 'Keep the playable copy current' setting on it also "
    "makes the playable copy; with it off, call chromatic_web_preview after it), then call "
    "chromatic_present_game again."
)
_REMAKE = (
    "Call chromatic_web_preview to make the playable copy from the current build, then call chromatic_present_game "
    "again. If chromatic_web_preview fails, tell the user what it said instead of building again."
)


def export_freshness(
    root: Path, last_build: dict | None = None, last_web_export: dict | None = None
) -> tuple[bool, str | None, str | None]:
    """Whether the web copy shows the latest build: ``(fresh, why, next step)``. Fresh means it exists, the engine
    made it (``engine_made_export``), it is not older than the last ROM build, and no game source changed after it.
    When the library recorded the build, its time counts (the native ROM file otherwise), and the copy's time is
    the later of its files and the last successful web export the broker recorded (the engine reuses an unchanged
    export without rewriting it). A failed build after the copy also counts as stale: the user would be shown an
    older game than the one being worked on."""
    last = last_build if isinstance(last_build, dict) else None
    recorded = timestamp(last.get("t")) if last else 0.0
    game_rom = _game_rom(root)
    rom_time = game_rom[1] if game_rom else None
    # When hermretro's own successful build is the newest ROM, only its playable copy is missing: building the
    # same thing again would loop, so the copy is made from it. A newer ROM nobody recorded needs a real build.
    remake = bool(last and last.get("ok")) and recorded + FRESH_SLACK_SECONDS >= (rom_time or 0.0)
    recover = _REMAKE if remake else _REBUILD
    exported = web_export_time(root)
    if exported is None:
        return False, "This game has no playable web copy yet.", recover
    if not engine_made_export(root):
        return (
            False,
            "The playable copy in build/web was not made by hermretro's build, or was changed after it, so it may "
            "not be this game as its sources stand.",
            "Never make, copy or edit files in build/ yourself. " + recover,
        )
    if game_rom is not None and not _plays_rom(root, game_rom[0]):
        return (
            False,
            f"The playable copy does not play this game's ROM ({canonical_rom(root)}), so it is another build.",
            _REBUILD,
        )
    if isinstance(last_web_export, dict):
        exported = max(exported, timestamp(last_web_export.get("t")))
    built = None if last else rom_time  # a recorded build's time counts, else the newest ROM file's
    if last and last.get("ok") is False and recorded > exported + FRESH_SLACK_SECONDS:
        return (
            False,
            "The last chromatic_rom_build of this game failed, so the playable copy is an older build.",
            "Fix what the build reported first. " + _REBUILD,
        )
    latest = max([moment for moment in (built, recorded if last and last.get("ok") else None) if moment] or [0.0])
    if latest > exported + FRESH_SLACK_SECONDS:
        return False, "The playable web copy is older than the last ROM build.", recover
    recorded_sources = last_web_export.get("sources") if isinstance(last_web_export, dict) else None
    if isinstance(recorded_sources, str):
        changed = source_digest(root) != recorded_sources
    else:  # an export recorded before the library kept its sources' digest
        changed = sources_newer_than(root, exported)
    if changed:
        return False, "Game files changed after the playable copy was made, so it is not the current game.", _REBUILD
    return True, None, None


def sources_newer_than(root: Path, moment: float) -> bool:
    """Whether any game source file under the project changed after ``moment`` (a ROM's mtime)."""
    seen = 0
    top = os.fspath(root)
    for directory, folders, files in os.walk(root):
        folders[:] = [f for f in folders if not f.startswith(".") and f not in NOT_SOURCE]
        for name in files:
            # The game card (game.json, cover.png) describes the game; it is not game source.
            if name.startswith(".") or (directory == top and name in game_card.CARD_FILES):
                continue
            seen += 1
            if seen > MAX_SOURCE_FILES:
                return False
            try:
                if os.stat(os.path.join(directory, name)).st_mtime > moment + 1.0:
                    return True
            except OSError:
                continue
    return False
