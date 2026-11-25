"""The game card's cover: paths, standard-library PNG decoding, validation and the desktop data URL."""

from __future__ import annotations

import base64
import hashlib
import struct
import zlib
from functools import lru_cache
from pathlib import Path
from stat import S_ISREG

COVER_FILE = "cover.png"
COVER_WIDTH, COVER_HEIGHT = 160, 144
MAX_COVER_COLOURS = 32
MIN_COVER_COLOURS = 3
MAX_COVER_BYTES = 512 * 1024


def cover_path(root: Path) -> Path:
    return Path(root) / COVER_FILE


class PngError(ValueError):
    pass


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_png(data: bytes) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """Width, height and RGBA pixels of a non-interlaced 8-bit (or palette) PNG; any damage is a PngError."""
    try:
        return _decode_png(data)
    except PngError:
        raise
    except (struct.error, IndexError, ValueError, zlib.error) as error:
        raise PngError(f"the PNG data is damaged ({error})") from error


def _decode_png(data: bytes) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise PngError("not a PNG file")
    position, header, palette, transparency, chunks = 8, None, None, None, []
    while position + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[position : position + 8])
        body = data[position + 8 : position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body[:13])
        elif kind == b"PLTE":
            palette = [tuple(body[index : index + 3]) for index in range(0, len(body) - 2, 3)]
        elif kind == b"tRNS":
            transparency = body
        elif kind == b"IDAT":
            chunks.append(body)
        elif kind == b"IEND":
            break
    if header is None:
        raise PngError("the PNG has no header")
    width, height, depth, colour, _compression, _filter, interlace = header
    if interlace:
        raise PngError("the PNG is interlaced; save it without interlacing")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour)
    if channels is None:
        raise PngError(f"unsupported PNG colour type {colour}")
    if depth == 16:
        raise PngError("the PNG uses 16 bits per channel; save it with 8")
    if colour != 3 and depth != 8 and not (colour == 0 and depth in (1, 2, 4)):
        raise PngError(f"unsupported PNG bit depth {depth}")
    if colour == 3 and not palette:
        raise PngError("the palette PNG has no palette")
    palette = palette or []
    if width * height > 4_000_000:
        raise PngError("the image is too large")
    bits = depth * channels
    stride = (width * bits + 7) // 8
    step = max(1, bits // 8)
    try:  # never more than the rows the header promises: a small file must not inflate without end
        raw = zlib.decompressobj().decompress(b"".join(chunks), height * (stride + 1))
    except zlib.error as error:
        raise PngError(f"the PNG data is damaged ({error})") from error
    if len(raw) < height * (stride + 1):
        raise PngError("the PNG data is shorter than its size says")
    previous = bytearray(stride)
    pixels: list[tuple[int, int, int, int]] = []
    alpha_of = {}
    if colour == 3 and transparency:
        alpha_of = {index: value for index, value in enumerate(transparency)}
    key = None
    if colour == 0 and transparency and len(transparency) >= 2:
        key = struct.unpack(">H", transparency[:2])[0]
    elif colour == 2 and transparency and len(transparency) >= 6:
        key = struct.unpack(">HHH", transparency[:6])
    for row in range(height):
        start = row * (stride + 1)
        kind = raw[start]
        line = bytearray(raw[start + 1 : start + 1 + stride])
        for index in range(stride):
            left = line[index - step] if index >= step else 0
            up = previous[index]
            corner = previous[index - step] if index >= step else 0
            if kind == 1:
                line[index] = (line[index] + left) & 0xFF
            elif kind == 2:
                line[index] = (line[index] + up) & 0xFF
            elif kind == 3:
                line[index] = (line[index] + ((left + up) >> 1)) & 0xFF
            elif kind == 4:
                line[index] = (line[index] + _paeth(left, up, corner)) & 0xFF
            elif kind != 0:
                raise PngError("the PNG data is damaged (unknown row filter)")
        previous = line
        if depth < 8:
            per_byte, mask = 8 // depth, (1 << depth) - 1
            values = [(line[x // per_byte] >> (8 - depth * (x % per_byte + 1))) & mask for x in range(width)]
            for value in values:
                if colour == 3:
                    if value >= len(palette):
                        raise PngError("a pixel uses a colour the palette does not have")
                    r, g, b = palette[value]
                    pixels.append((r, g, b, alpha_of.get(value, 255)))
                else:
                    grey = value * 255 // mask
                    pixels.append((grey, grey, grey, 0 if key == value else 255))
            continue
        for x in range(width):
            chunk = line[x * channels : (x + 1) * channels]
            if colour == 3:
                if chunk[0] >= len(palette):
                    raise PngError("a pixel uses a colour the palette does not have")
                r, g, b = palette[chunk[0]]
                pixels.append((r, g, b, alpha_of.get(chunk[0], 255)))
            elif colour == 0:
                pixels.append((chunk[0], chunk[0], chunk[0], 0 if key == chunk[0] else 255))
            elif colour == 4:
                pixels.append((chunk[0], chunk[0], chunk[0], chunk[1]))
            elif colour == 2:
                rgb = (chunk[0], chunk[1], chunk[2])
                pixels.append((*rgb, 0 if key == rgb else 255))
            else:
                pixels.append((chunk[0], chunk[1], chunk[2], chunk[3]))
    return width, height, pixels


def check_cover(path: Path) -> dict:
    """Whether a PNG is a usable cover: exactly 160x144, fully opaque, pixel art (3 to 32 colours).
    ``{ok, problem?, width?, height?, colours?, sha256?}``."""
    path = Path(path)
    try:
        info = path.stat()
    except OSError:
        return {"ok": False, "problem": f"{path} does not exist."}
    if not S_ISREG(info.st_mode):
        return {"ok": False, "problem": f"{path} is not a regular file."}
    try:
        result, _ = _read_cover(path, info.st_size)
    except OSError as error:
        return {"ok": False, "problem": f"The cover cannot be read: {error}."}
    return result


def _size_problem(size: int) -> dict:
    return {
        "ok": False,
        "problem": f"The cover file is {size // 1024} KB; a 160x144 pixel-art PNG is far smaller. Save it as a plain PNG.",
    }


def _read_cover(path: Path, size: int) -> tuple[dict, bytes]:
    if size > MAX_COVER_BYTES:
        return _size_problem(size), b""
    with path.open("rb") as handle:
        data = handle.read(MAX_COVER_BYTES + 1)
    return _check_cover_bytes(data), data


def png_size(data: bytes) -> tuple[int, int] | None:
    """A PNG's width and height from its header, without decoding it; None when it has no such header."""
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[8:16] != b"\x00\x00\x00\x0dIHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _check_cover_bytes(data: bytes) -> dict:
    if len(data) > MAX_COVER_BYTES:
        return _size_problem(len(data))
    size = png_size(data)  # a damaged or foreign file is left to decode_png, which says what is wrong
    if size is not None and size != (COVER_WIDTH, COVER_HEIGHT):
        width, height = size
        return {
            "ok": False,
            "width": width,
            "height": height,
            "problem": f"The cover is {width}x{height}; it must be exactly {COVER_WIDTH}x{COVER_HEIGHT} (the "
            "Game Boy screen), drawn at that size, not scaled down.",
        }
    try:
        width, height, pixels = decode_png(data)
    except PngError as error:
        return {"ok": False, "problem": f"The cover cannot be read: {error}."}
    info = {"width": width, "height": height}
    if (width, height) != (COVER_WIDTH, COVER_HEIGHT):
        return {
            "ok": False,
            **info,
            "problem": f"The cover is {width}x{height}; it must be exactly {COVER_WIDTH}x{COVER_HEIGHT} (the "
            "Game Boy screen), drawn at that size, not scaled down.",
        }
    if any(pixel[3] != 255 for pixel in pixels):
        return {"ok": False, **info, "problem": "The cover has transparent pixels; every pixel must be opaque."}
    colours = len({pixel[:3] for pixel in pixels})
    info["colours"] = colours
    if colours > MAX_COVER_COLOURS:
        return {
            "ok": False,
            **info,
            "problem": f"The cover has {colours} colours; pixel art uses at most {MAX_COVER_COLOURS}. Draw it "
            "as pixel art in the game's own palettes (no smoothing, gradients or photos).",
        }
    if colours < MIN_COVER_COLOURS:
        return {"ok": False, **info, "problem": "The cover is nearly blank; draw the game's art on it."}
    return {"ok": True, **info, "sha256": hashlib.sha256(data).hexdigest()}


def copied_asset(root: Path, cover: Path) -> str | None:
    """The game image (under ``assets/``) the cover is a byte-identical copy of, if any: a cover is drawn for
    the card (characters, title), not an existing image reused. Only PNGs of the cover's size are read."""
    assets = Path(root) / "assets"
    if not assets.is_dir():
        return None
    try:
        data = Path(cover).read_bytes()
    except OSError:
        return None
    for path in assets.rglob("*"):
        if path.suffix.lower() != ".png":
            continue
        try:
            info = path.stat()
            if S_ISREG(info.st_mode) and info.st_size == len(data) and path.read_bytes() == data:
                return path.relative_to(root).as_posix()
        except OSError:
            continue
    return None


def _copy_problem(name: str) -> str:
    return (
        f"The cover is an unchanged copy of {name}. Draw cover art for it: the main character and the "
        "game's title on a scene from the game."
    )


def _cover(root: Path, strict: bool) -> dict | None:
    """``check_cover`` of the project's cover (None when there is no cover file); ``strict`` also refuses one
    copied unchanged from the game's assets."""
    if not strict:
        cover, _ = _display_cover(root)
        return dict(cover) if cover is not None else None
    path = cover_path(root)
    if not path.is_file():
        return None
    cover = check_cover(path)
    if cover["ok"]:
        copied = copied_asset(root, path)
        if copied:
            cover = {**cover, "ok": False, "problem": _copy_problem(copied)}
    return cover


def cover_problem(root: Path, strict: bool = True) -> str | None:
    """What is wrong with the project's cover by the rules ``status`` uses (``strict``, the default, is
    chromatic_present_game's: a cover copied unchanged from ``assets/`` is refused too), as the text ``status``
    lists in ``problems``; None for a usable cover. A project without ``cover.png`` gets a sentence saying so."""
    cover = _cover(Path(root), strict)
    if cover is None:
        return f"There is no {COVER_FILE} yet; draw one and set it with chromatic_game_info."
    return None if cover["ok"] else cover["problem"]


@lru_cache(maxsize=128)
def _cached_display_cover(path: Path, stamp: tuple) -> tuple[dict, str | None]:
    result, data = _read_cover(path, stamp[-1])
    url = "data:image/png;base64," + base64.b64encode(data).decode("ascii") if result["ok"] else None
    return result, url


def _display_cover(root: Path) -> tuple[dict | None, str | None]:
    path = cover_path(root)
    try:
        info = path.stat()
        if S_ISREG(info.st_mode):
            # Replacement and in-place edits invalidate both the card decision and its displayed image.
            stamp = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_size)
            return _cached_display_cover(path, stamp)
    except OSError:
        pass
    return None, None


def cover_data_url(root: Path) -> str | None:
    """The cover as a data URL when it is valid for the shelf."""
    return _display_cover(root)[1]
