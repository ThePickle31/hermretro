"""PNG data URLs for title-screen thumbnails and player captures."""

from __future__ import annotations

import base64
from pathlib import Path

MAX_THUMB_BYTES = 64 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def decode_png(data_url, limit: int) -> bytes:
    """A ``data:image/png;base64,`` URL (or bare base64) to PNG bytes, bounded and checked."""
    if not isinstance(data_url, str) or not data_url:
        raise ValueError("png must be a data:image/png;base64 URL.")
    if data_url.startswith("data:") and not data_url[:32].lower().startswith("data:image/png;base64,"):
        raise ValueError("png must be a data:image/png;base64 URL.")
    payload = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    if len(payload) > (limit * 4) // 3 + 8:
        raise ValueError(f"The image is larger than {limit // 1024} KB.")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("png is not valid base64.") from error
    if len(raw) > limit:
        raise ValueError(f"The image is larger than {limit // 1024} KB.")
    if not raw.startswith(PNG_MAGIC):
        raise ValueError("png is not a PNG image.")
    return raw


def read_thumbnail(path: Path) -> str | None:
    try:
        if not path.is_file():
            return None
        with path.open("rb") as handle:
            raw = handle.read(MAX_THUMB_BYTES + 1)
    except OSError:
        return None
    if not raw.startswith(PNG_MAGIC) or len(raw) > MAX_THUMB_BYTES:
        return None
    return "data:image/png;base64," + base64.b64encode(raw).decode()
