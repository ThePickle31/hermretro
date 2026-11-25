"""Project files, the game's ROM and build artifacts. Standard library only (freshness.py says whether the playable
copy is current)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import threading
from pathlib import Path


# Folders under a project that hold build output, recordings, tooling or the agent's own files (docs/ its plans,
# scratch/ its helper scripts), never game source.
NOT_SOURCE = frozenset(
    {"build", "captures", "save-states", "artifacts", "node_modules", "__pycache__", "docs", "scratch"}
)
# The files at the top of a game folder that describe the game rather than make it (backend/library/layout.py):
# what every publish holds besides the ROM.
GAME_FILES = ("game.json", "cover.png", "README.md", "CHANGELOG.md", "LICENSE", ".gitignore")
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
    ``chromatic_rom_build``'s ``outputPath``). ``build/game.gb`` for a monochrome project (``colorMode`` ``mono``),
    else ``build/game.gbc``."""
    return ROM_STEM + (".gb" if project_settings(root).get("colorMode") == "mono" else ".gbc")


def project_settings(root: Path) -> dict:
    """The project's GB Studio settings: ``project/settings.gbsres``, else the ``settings`` an older single-file
    ``.gbsproj`` holds ({} when neither can be read)."""
    settings = _json(Path(root) / "project" / "settings.gbsres")
    if settings:
        return settings
    descriptor = project_file(Path(root))
    legacy = _json(descriptor).get("settings") if descriptor else None
    return legacy if isinstance(legacy, dict) else {}


def _build_roms(root: Path) -> list[tuple[Path, float]]:
    """The ROMs directly in ``build/``, newest first."""
    try:
        files = list((Path(root) / "build").iterdir())
    except OSError:
        return []
    roms = []
    for path in files:
        if path.suffix.lower() not in (".gb", ".gbc"):
            continue
        try:
            info = _file_info(path)
        except OSError:
            continue
        if info is not None:
            roms.append((path, info.st_mtime))
    return sorted(roms, key=lambda item: item[1], reverse=True)


def _game_rom(root: Path) -> tuple[Path, float] | None:
    """The game's ROM and its file time: ``build/game.gbc`` or ``build/game.gb`` (the newer, when a colour mode
    change left both; ``canonical_rom`` names the one the next build writes). None when it has not been built."""
    own = {ROM_STEM.rsplit("/", 1)[1] + suffix for suffix in (".gb", ".gbc")}
    return next(((path, moment) for path, moment in _build_roms(root) if path.name in own), None)


def _legacy_rom(root: Path) -> tuple[Path, float] | None:
    """The newest ROM in ``build/`` of a game last built before every build wrote the game's ROM."""
    roms = _build_roms(root)
    return roms[0] if roms else None


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


def _native_rom_info(root: Path, find=_game_rom) -> tuple[dict | None, float | None]:
    found = find(root)
    try:
        return _rom_info(found[0]) if found else (None, None)
    except OSError:
        return None, None


def build_artifacts(root: Path, last: dict, *, require_web_rom: bool = False) -> tuple[dict, float | None]:
    """The game's ROM and the web export's. The ROM is the game's own (``_game_rom``); a game last built before
    every build wrote it falls back to the ROM its last recorded build made, its newest ROM in ``build/``, then the
    web export's."""
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
        rom, built = _native_rom_info(root, _legacy_rom)
    if rom is None:
        rom, built = web_rom_info, web_time
    web = {"sha256": web_rom_info["sha256"], "builtAt": web_rom_info["builtAt"]} if exported and web_rom_info else None
    return {"rom": rom, "webExport": exported, "web": web}, built
