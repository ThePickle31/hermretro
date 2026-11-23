"""Capture files, metadata and stable media identifiers for the player and the library."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .. import library
from ..system import paths
from .frame import DEMO_ID, PlayerError, is_demo

CAPTURE_NAMESPACE = uuid.UUID("5d0c7f39-3b8e-4f4f-9a43-2f6c3c7d1a11")
MEDIA_EXTENSIONS = {".png": "image/png", ".webm": "video/webm", ".mp4": "video/mp4"}


def demo_captures_root() -> Path:
    """Where the demo's captures go (``<library>/captures/demo``): the demo has no project folder."""
    return paths.library_dir()


def capture_root(identifier, game_root) -> Path | None:
    """Where a game's captures live (the folder ``list_captures``/``save_capture`` take as ``root``): the library
    folder for the demo cartridge (its captures go in ``<library>/captures/demo``), else ``game_root(identifier)``,
    the project folder (``host._game_root`` on the Hermes side); None for an unknown game."""
    if is_demo(identifier):
        return demo_captures_root()
    return game_root(identifier) if library.valid_id(identifier) else None


def captures_dir(root: Path, identifier: str | None = None) -> Path:
    return root / "captures" / DEMO_ID if is_demo(identifier) else root / "captures"


def capture_id(identifier: str, filename: str) -> str:
    """Stable per file, so a capture keeps its URL across restarts without an index."""
    return str(uuid.uuid5(CAPTURE_NAMESPACE, f"{identifier}/{filename}"))


def _stamp(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H-%M-%S-") + f"{now.microsecond // 1000:03d}Z"


def _free_name(directory: Path, stem: str, extension: str) -> Path:
    candidate = directory / f"{stem}.{extension}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{counter}.{extension}"
        counter += 1
    return candidate


def save_capture(
    root: Path, identifier: str, kind: str, media: bytes, media_type: str, metadata, extra: dict | None = None
) -> dict:
    """Write ``<project>/captures/<iso>-<kind>.<ext>`` and its ``.json`` sidecar; return the receipt the
    player checks (``id``, ``kind``, ``bytes``, ``path``, ``metadataPath``, ``sha256``, ``createdAt``, urls)."""
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", kind or ""):
        raise PlayerError("Unknown capture kind.")
    if not media:
        raise PlayerError("Capture media is empty.")
    if kind == "screenshot" or media.startswith(library.PNG_MAGIC):
        if not media.startswith(library.PNG_MAGIC):
            raise PlayerError("A screenshot must be a PNG image.")
        extension = "png"
    elif "mp4" in (media_type or "").lower():
        extension = "mp4"
    else:
        extension = "webm"
    directory = captures_dir(root, identifier)
    directory.mkdir(parents=True, exist_ok=True)
    created = datetime.now(UTC)
    target = _free_name(directory, f"{_stamp(created)}-{kind}", extension)
    target.write_bytes(media)
    sha = hashlib.sha256(media).hexdigest()
    identifier_value = capture_id(identifier, target.name)
    created_at = created.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    sidecar = target.with_name(target.name + ".json")
    sidecar.write_text(
        json.dumps(
            {
                "id": identifier_value,
                "kind": kind,
                "media": target.name,
                "mimeType": MEDIA_EXTENSIONS["." + extension],
                "bytes": len(media),
                "sha256": sha,
                "createdAt": created_at,
                "game": identifier,
                **(extra or {}),
                "metadata": metadata,
            },
            indent=1,
        )
    )
    return {
        "id": identifier_value,
        "kind": kind,
        "bytes": len(media),
        "path": str(target),
        "metadataPath": str(sidecar),
        "sha256": sha,
        "createdAt": created_at,
        "url": f"./codex-captures/{identifier_value}/media",
        "metadataUrl": f"./codex-captures/{identifier_value}/metadata",
    }


def list_captures(root: Path, identifier: str) -> list[dict]:
    """Media files directly in ``<project>/captures/``, newest first."""
    directory = captures_dir(root, identifier)
    found = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    for path in entries:
        if path.suffix.lower() not in MEDIA_EXTENSIONS or path.name.startswith(".") or not path.is_file():
            continue
        sidecar = library.read_json(path.with_name(path.name + ".json"))  # noqa: SLF001 - the library's shared JSON reader
        kind = (
            sidecar.get("kind")
            if isinstance(sidecar.get("kind"), str)
            else ("screenshot" if path.suffix.lower() == ".png" else "video")
        )
        created = (
            sidecar.get("createdAt")
            if isinstance(sidecar.get("createdAt"), str)
            else datetime.fromtimestamp(path.stat().st_mtime, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        found.append(
            {
                "id": capture_id(identifier, path.name),
                "path": str(path),
                "kind": kind,
                "createdAt": created,
                "file": path.name,
            }
        )
    found.sort(key=lambda c: c["createdAt"], reverse=True)
    return found


def find_capture(root: Path, identifier: str, cid: str) -> Path | None:
    directory = captures_dir(root, identifier)
    try:
        for path in directory.iterdir():
            if path.suffix.lower() in MEDIA_EXTENSIONS and capture_id(identifier, path.name) == cid and path.is_file():
                return path
    except OSError:
        pass
    return None
