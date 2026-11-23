"""Kept versions of game images: what an image looked like when a reply showed it. The image checks
(kind, size, whether a path is inside a library game), the hooks that keep each version, and the list of
kept versions."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import tempfile
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from stat import S_ISDIR

from ..hermes import host
from ..library import valid_id

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


def _frames_dir() -> Path:
    """The frames Hermes saved from tool results (content-addressed, shared by every game's chat)."""
    return (host._data_dir() / "frames").resolve()


def _folder_id(folder: Path) -> tuple[int, int] | None:
    try:
        stat = folder.stat()
        return (stat.st_dev, stat.st_ino) if S_ISDIR(stat.st_mode) else None
    except (OSError, ValueError):
        return None


def _same_folder(one: Path, other: Path) -> bool:
    """Whether two paths name the same existing folder (by identity, so a differently cased spelling on a
    case-insensitive disk is the same folder)."""
    try:
        return os.path.samefile(one, other)
    except (OSError, TypeError, ValueError):
        return False


def _is_frames(root: Path) -> bool:
    return _same_folder(root, _frames_dir())


class AssetOwners:
    """A registry snapshot indexed by directory identity, including on case-insensitive disks."""

    def __init__(self):
        self.games = {}
        self.game_folders = set()
        self.frames_folder = _folder_id(_frames_dir())
        for game, entry in host._registry().load()["games"].items():
            if not isinstance(entry, dict) or not isinstance(entry.get("projectRoot"), str):
                continue
            try:
                root = Path(entry["projectRoot"]).resolve(strict=True)
            except (OSError, RuntimeError, ValueError):
                continue
            identity = _folder_id(root)
            if identity is not None:
                if valid_id(game):
                    self.games[game] = root
                self.game_folders.add(identity)
        self.root_folders = self.game_folders | ({self.frames_folder} if self.frames_folder is not None else set())

    def holders(self, real: Path):
        """Yield the owning ancestors deepest first, spelled as in the resolved image path."""
        for folder in real.parents:
            if _folder_id(folder) in self.root_folders:
                yield folder

    def image_root(self, real: Path) -> Path | None:
        return next(self.holders(real), None)

    def list_root(self, game, raw_root) -> Path | None:
        root = self.games.get(str(game or ""))
        if root is None and raw_root:
            try:
                root = Path(str(raw_root)).expanduser().resolve(strict=True)
            except (OSError, RuntimeError, ValueError):
                return None
        if root is not None:
            identity = _folder_id(root)
            if identity != self.frames_folder and identity in self.game_folders:
                return root
        return None


def _image_root(real: Path) -> Path | None:
    """The folder an image is shown from, spelled as in ``real``: the saved frames, or the library game that most
    closely holds it (the deepest, so an image of a game inside another game's folder belongs to the inner game);
    None for neither."""
    return AssetOwners().image_root(real)


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


@contextmanager
def _version_lock(real: Path):
    """Serialize all keep, adoption and restore operations for one asset across Hermes processes."""
    locks = host._data_dir() / "asset-version-locks"
    locks.mkdir(parents=True, exist_ok=True)
    # Alternate case spellings on macOS can point to the same live file, even after os.replace changes its inode.
    name = _digest(unicodedata.normalize("NFC", str(real).casefold()))
    with (locks / name).open("ab") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def _versions_dir(real: Path, root: Path) -> Path:
    """Where the kept versions of ``real`` live as an image shown from ``root`` (``_image_root``): filed under the
    game that owns it, so a folder that later becomes a game of its own starts with none of the outer game's."""
    base = host._data_dir() / "asset-versions"
    folder = base / _digest(f"{root}\0{real}")
    if not folder.exists():
        _adopt_path_versions(base / _digest(str(real)), folder, real, root)
    return folder


def _adopt_path_versions(old: Path, folder: Path, real: Path, root: Path) -> None:
    """Versions kept by earlier releases were filed by path alone. They move to ``root`` only when it alone (a game or
    the saved frames) holds the image: with a game inside another's folder, the old ones could be either's."""
    try:
        holders = list(AssetOwners().holders(real)) if old.is_dir() else []
        if len(holders) == 1 and _same_folder(holders[0], root):
            old.rename(folder)
    except OSError:
        logger.debug("hermretro could not move an image's kept versions", exc_info=True)


def _kept_versions(folder: Path) -> list[Path]:
    try:
        return sorted(
            (item for item in folder.iterdir() if item.stem.isdigit() and item.suffix in ASSET_SUFFIXES),
            key=lambda item: int(item.stem),
        )
    except FileNotFoundError:
        return []


def _write_image(path: Path, data: bytes, suffix: str) -> None:
    """Atomically write a kept copy or replace the live image, cleaning up on failure."""
    handle, partial = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=suffix)
    try:
        with os.fdopen(handle, "wb") as writer:
            writer.write(data)
        os.replace(partial, path)
    finally:
        Path(partial).unlink(missing_ok=True)


def _save_version(real: Path, folder: Path, *, required=False) -> tuple[Path | None, bool]:
    """Save the live bytes under the asset lock. Return their kept path and whether it is new."""
    with real.open("rb") as source:
        stat = os.fstat(source.fileno())
        target = folder / f"{stat.st_mtime_ns}{real.suffix.lower()}"
        if target.is_file() and not required:
            return target, False
        if stat.st_size <= ASSET_MAX_BYTES:
            data = source.read(ASSET_MAX_BYTES + 1)
            if len(data) <= ASSET_MAX_BYTES:
                return _save_image_bytes(folder, target, data)
    if required:
        raise OSError(f"The current image is larger than {size_text(ASSET_MAX_BYTES)} and could not be backed up.")
    return None, False


def _save_image_bytes(folder: Path, target: Path, data: bytes) -> tuple[Path, bool]:
    if target.is_file():
        if target.read_bytes() != data:
            raise OSError("A different image already has the current image's modification time.")
        return target, False
    kept = _kept_versions(folder)
    if kept and int(kept[-1].stem) < int(target.stem) and kept[-1].read_bytes() == data:
        return kept[-1], False
    folder.mkdir(parents=True, exist_ok=True)
    _write_image(target, data, ".part")
    return target, True


def _prune_versions(folder: Path, protect=()) -> None:
    kept = _kept_versions(folder)
    excess = max(0, len(kept) - ASSET_KEEP_VERSIONS)
    for old in [item for item in kept if item not in protect][:excess]:
        old.unlink(missing_ok=True)


def _try_keep_version(real: Path, folder: Path, *, protect=()) -> None:
    try:
        _saved, added = _save_version(real, folder)
        if added:
            _prune_versions(folder, protect)
    except OSError:
        logger.debug("hermretro could not keep an image version", exc_info=True)


def _keep_version(real: Path, root: Path) -> None:
    """Best-effort history capture for a hook or build report."""
    try:
        with _version_lock(real):
            _try_keep_version(real, _versions_dir(real, root))
    except OSError:
        logger.debug("hermretro could not lock image history", exc_info=True)


def _restore_version(real: Path, root: Path, wanted: str) -> list[dict] | None:
    with _version_lock(real):
        folder = _versions_dir(real, root)
        selected = folder / f"{wanted}{real.suffix.lower()}"
        try:
            data = selected.read_bytes()
        except FileNotFoundError:
            return None
        backup, _added = _save_version(real, folder, required=True)
        protect = (selected, backup)
        _prune_versions(folder, protect)
        _write_image(real, data, ".restore")
        _try_keep_version(real, folder, protect=protect)
        return _versions(real, folder)


def _version_at(real: Path, folder: Path, at_ms) -> Path | None:
    """The kept version of ``real`` that was current at ``at_ms`` (a reply's time), when the file has
    been rewritten since; None when the file on disk is still that version (or nothing older was kept)."""
    try:
        at_ns = int(float(at_ms) * 1_000_000)
    except (OverflowError, TypeError, ValueError):
        return None
    if at_ns <= 0 or real.stat().st_mtime_ns <= at_ns:
        return None
    return next((item for item in reversed(_kept_versions(folder)) if int(item.stem) <= at_ns), None)


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


def _versions(real: Path, folder: Path) -> list[dict]:
    """Every kept version, oldest first, with the current one marked."""
    kept = _kept_versions(folder)
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
        with _version_lock(real):
            return sum(1 for version in _versions(real, _versions_dir(real, root)) if not version["current"])
    except OSError:
        return 0
