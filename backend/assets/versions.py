"""Kept versions of game images: what an image looked like when a reply showed it. The image checks
(kind, size, whether a path is inside a library game), the hooks that keep each version, and the list of
kept versions."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from ..hermes import host

logger = host.logger  # one logger for the Hermes side of the backend,

# Shared helpers (the data folder, the profile, the library, the broker client) stay in backend.hermes.host and are
# looked up there at call time, so one patch of host.<name> reaches every module.

ASSET_SUFFIXES = {
    ".png": "image/png",
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
ASSET_MAX_BYTES = 6 * 1024 * 1024  # the largest image the asset viewer shows


def size_text(size: int) -> str:
    """A byte count as the docs write it: ``6 MB``, ``512 KB``, or bytes when it is neither."""
    for unit, name in ((1024 * 1024, "MB"), (1024, "KB")):
        if size >= unit and size % unit == 0:
            return f"{size // unit} {name}"
    return f"{size} bytes"


def _image_size(data: bytes) -> tuple[int, int]:
    """Width and height from a PNG, GIF or JPEG header; (0, 0) when unknown."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                break
            marker, length = data[index + 1], int.from_bytes(data[index + 2 : index + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return int.from_bytes(data[index + 7 : index + 9], "big"), int.from_bytes(
                    data[index + 5 : index + 7], "big"
                )
            index += 2 + length
    return 0, 0


def _asset_kind(relative: str | None) -> str:
    parts = (relative or "").split("/")
    if parts[:2] == ["assets", "sprites"]:
        return "sprite"
    if parts[:2] == ["assets", "backgrounds"]:
        return "background"
    if parts[:2] == ["assets", "ui"] or parts[:2] == ["assets", "fonts"]:
        return "ui"
    if "playtests" in parts or "frames" in parts:
        return "frame"
    if "captures" in parts:
        return "capture"
    return "image"


# The "up to 40 per file" of the Versions paragraph (under the asset RPC heading) in .agents/skills/hermretro-dev-page/references/build-page.md: the
# newest kept, the oldest dropped. AssetRetention in tests/backend/assets/test_asset_versions.py reads the number there.
ASSET_KEEP_VERSIONS = 40
# A line of a reply that delivers a file (``MEDIA:/path``), quotes or backticks allowed around the path.
_MEDIA_LINE = re.compile(
    r"^[ \t]*MEDIA:[ \t]*([`\"']?)(.+?\.(?:png|gif|jpe?g|webp))\1[ \t]*$", re.IGNORECASE | re.MULTILINE
)


def _game_roots() -> list[Path]:
    """Every library game's project folder, straight from the registry: a game whose details cannot be read right now
    still owns its files."""
    roots = []
    for entry in host._registry().load()["games"].values():
        if isinstance(entry, dict) and isinstance(entry.get("projectRoot"), str):
            try:
                roots.append(Path(entry["projectRoot"]).resolve())
            except (OSError, RuntimeError):
                continue
    return roots


def _asset_roots() -> list[Path]:
    return [_frames_dir(), *_game_roots()]


def _frames_dir() -> Path:
    """The frames Hermes saved from tool results (content-addressed, shared by every game's chat)."""
    return (host._data_dir() / "frames").resolve()


def _same_folder(one, other) -> bool:
    """Whether two paths name the same existing folder (by identity, so a differently cased spelling on a
    case-insensitive disk is the same folder)."""
    try:
        return os.path.samefile(one, other)
    except (OSError, TypeError, ValueError):
        return False


def _is_frames(root: Path) -> bool:
    return _same_folder(root, _frames_dir())


def _holders(real: Path) -> list[Path]:
    """The saved frames or library games whose folders hold an image, deepest first, spelled as in ``real``. Folders
    are matched by identity, not spelling."""
    roots = set()
    for base in _asset_roots():
        try:
            found = base.stat()
        except OSError:
            continue
        roots.add((found.st_dev, found.st_ino))
    holders = []
    for folder in real.parents:
        try:
            found = folder.stat()
        except OSError:
            continue
        if (found.st_dev, found.st_ino) in roots:
            holders.append(folder)
    return holders


def _image_root(real: Path) -> Path | None:
    """The folder an image is shown from, spelled as in ``real``: the saved frames, or the library game that most
    closely holds it (the deepest, so an image of a game inside another game's folder belongs to the inner game);
    None for neither."""
    holders = _holders(real)
    return holders[0] if holders else None


def _shown_in(root: Path, game_root) -> bool:
    """Whether an image shown from ``root`` belongs on the Build page of the game whose project folder is
    ``game_root``: a saved frame always does, a game's file only on that game's own page (never on another game's,
    and never where ``game_root`` is not a library game)."""
    if _is_frames(root):
        return True
    wanted = Path(str(game_root or "")).expanduser()
    return wanted.is_absolute() and _same_folder(wanted, root)


def _asset_file(raw, game_root=None, *, any_game=False) -> tuple[Path, Path] | None:
    """The real file and the root it is shown from, for an image of the game whose project folder is ``game_root``
    or a saved frame (``any_game``: an image of any library game); None for anything else."""
    raw = str(raw or "")
    if raw.startswith("file://"):
        raw = raw[len("file://") :]
    candidate = Path(raw).expanduser()
    # Cheap checks first: this runs after every tool call.
    if not raw or not candidate.is_absolute() or candidate.suffix.lower() not in ASSET_SUFFIXES:
        return None
    try:
        real = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if real.suffix.lower() not in ASSET_SUFFIXES or not real.is_file():
        return None
    root = _image_root(real)
    if root is None or not (any_game or _shown_in(root, game_root)):
        return None
    return real, root


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _versions_dir(real: Path, root: Path) -> Path:
    """Where the kept versions of ``real`` live as an image shown from ``root`` (``_image_root``): filed under the
    game that owns it, so a folder that later becomes a game of its own starts with none of the outer game's."""
    base = host._data_dir() / "asset-versions"
    folder = base / _digest(f"{root}\0{real}")
    if not folder.exists():
        _adopt_path_versions(base / _digest(str(real)), folder, real)
    return folder


def _adopt_path_versions(old: Path, folder: Path, real: Path) -> None:
    """Versions kept by earlier releases were filed by path alone. They move to their game only when exactly one
    game (or the saved frames) holds the image: with a game inside another's folder, the old ones could be either's."""
    try:
        if old.is_dir() and len(_holders(real)) == 1:
            old.rename(folder)
    except OSError:
        logger.debug("hermretro could not move an image's kept versions", exc_info=True)


def _keep_version(real: Path, root: Path) -> None:
    """Keep this version of a game image (named by its modification time), so a later rewrite of the
    same file (cover.png made again) does not change what an earlier reply showed."""
    try:
        stat = real.stat()
        if stat.st_size > ASSET_MAX_BYTES:
            return
        folder = _versions_dir(real, root)
        target = folder / f"{stat.st_mtime_ns}{real.suffix.lower()}"
        if target.exists():
            return
        folder.mkdir(parents=True, exist_ok=True)
        data = real.read_bytes()
        kept = sorted(folder.iterdir(), key=lambda item: item.name)
        if kept and kept[-1].read_bytes() == data:
            return
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(data)
        partial.replace(target)
        for old in kept[: max(0, len(kept) + 1 - ASSET_KEEP_VERSIONS)]:
            old.unlink(missing_ok=True)
    except OSError:
        logger.debug("hermretro could not keep an image version", exc_info=True)


def _version_at(real: Path, root: Path, at_ms) -> Path | None:
    """The kept version of ``real`` that was current at ``at_ms`` (a reply's time), when the file has
    been rewritten since; None when the file on disk is still that version (or nothing older was kept)."""
    try:
        at_ns = int(float(at_ms) * 1_000_000)
    except (TypeError, ValueError):
        return None
    if at_ns <= 0 or real.stat().st_mtime_ns <= at_ns:
        return None
    folder = _versions_dir(real, root)
    if not folder.is_dir():
        return None
    older = [
        item for item in folder.iterdir() if item.suffix != ".part" and item.stem.isdigit() and int(item.stem) <= at_ns
    ]
    return max(older, key=lambda item: int(item.stem)) if older else None


def _keep_paths(values) -> None:
    for value in values:
        if isinstance(value, str) and value:
            found = _asset_file(value, any_game=True)
            if found:
                _keep_version(*found)


def keep_delivered_images(assistant_response=None, **_kwargs):
    """``post_llm_call``: keep the images a reply delivered (``MEDIA:`` lines), as they are right now."""
    try:
        if isinstance(assistant_response, str) and "MEDIA:" in assistant_response:
            _keep_paths(match.group(2).strip() for match in _MEDIA_LINE.finditer(assistant_response))
    except Exception:
        logger.debug("hermretro keep_delivered_images failed", exc_info=True)


def keep_inspected_images(tool_name=None, args=None, **_kwargs):
    """``post_tool_call``: keep the images a step looked at or wrote, as they are right after it."""
    try:
        if isinstance(args, dict):
            _keep_paths(args.get(key) for key in ("image_url", "image", "assetPath", "outputPath", "path"))
    except Exception:
        logger.debug("hermretro keep_inspected_images failed", exc_info=True)


def _versions(real: Path, root: Path) -> list[dict]:
    """Every kept version of a file shown from ``root``, oldest first, with the current one marked."""
    folder = _versions_dir(real, root)
    kept = (
        sorted(
            (item for item in folder.iterdir() if item.stem.isdigit() and item.suffix != ".part"),
            key=lambda item: int(item.stem),
        )
        if folder.is_dir()
        else []
    )
    current = real.stat().st_mtime_ns
    data = real.read_bytes()
    versions = [
        {"id": item.stem, "at": int(item.stem) // 1_000_000, "file": str(item), "current": False} for item in kept
    ]
    match = next((entry for entry in reversed(versions) if int(entry["id"]) == current), None)
    if match is None and kept and kept[-1].read_bytes() == data:
        match = versions[-1]
    if match is None:
        versions.append({"id": str(current), "at": current // 1_000_000, "file": str(real), "current": True})
    else:
        match["current"] = True
    return versions


def older_versions(real: Path, root: Path) -> int:
    """How many kept versions of a game image (shown from ``root``) are older than the file as it is now (the current
    one is not counted); 0 when none are kept or the file cannot be read."""
    try:
        return sum(1 for version in _versions(real, root) if not version["current"])
    except OSError:
        return 0
