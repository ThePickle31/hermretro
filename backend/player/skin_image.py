"""Check a personal skin's image container before it replaces bundled artwork."""

from __future__ import annotations

import struct
from functools import lru_cache
from pathlib import Path
from stat import S_ISREG


def _png(stream, size: int) -> bool:
    if stream.read(16) != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
        return False
    dimensions = stream.read(8)
    if len(dimensions) != 8 or not all(struct.unpack(">II", dimensions)):
        return False
    stream.seek(33)  # signature, IHDR and its CRC
    pixels = False
    while stream.tell() + 12 <= size:
        length, kind = struct.unpack(">I4s", stream.read(8))
        end = stream.tell() + length + 4
        if end > size:
            return False
        if kind == b"IEND":
            return pixels and length == 0 and end == size and stream.read(4) == b"\xaeB`\x82"
        pixels |= kind == b"IDAT" and length > 0
        stream.seek(end)
    return False


def _webp_chunks(stream, limit: int, *, in_frame: bool = False) -> bool:
    pixels = False
    while stream.tell() + 8 <= limit:
        kind, length = struct.unpack("<4sI", stream.read(8))
        start = stream.tell()
        end = start + length + (length % 2)
        if end > limit:
            return False
        if kind == b"VP8 ":
            header = stream.read(min(length, 10))
            if len(header) != 10 or length <= 10 or header[3:6] != b"\x9d\x01\x2a":
                return False
            pixels = True
        elif kind == b"VP8L":
            if length <= 5 or stream.read(1) != b"\x2f":
                return False
            pixels = True
        elif kind == b"ANMF":
            if in_frame or length <= 16:
                return False
            stream.seek(start + 16)
            if not _webp_chunks(stream, start + length, in_frame=True):
                return False
            pixels = True
        stream.seek(end)
    return pixels and stream.tell() == limit


@lru_cache(maxsize=64)
def _usable(path: Path, inode: int, changed: int, size: int) -> bool:
    with path.open("rb") as stream:
        if path.suffix == ".png":
            return _png(stream, size)
        header = stream.read(12)
        return (
            len(header) == 12
            and header[:4] == b"RIFF"
            and header[8:] == b"WEBP"
            and int.from_bytes(header[4:8], "little") + 8 == size
            and _webp_chunks(stream, size)
        )


def usable(path: Path) -> bool:
    try:
        info = path.lstat()
        return S_ISREG(info.st_mode) and _usable(path, info.st_ino, info.st_ctime_ns, info.st_size)
    except (OSError, struct.error):
        return False
