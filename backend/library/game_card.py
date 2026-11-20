"""The game card: every game's ``game.json`` (title, tagline, description, about, genres, tags,
controls) and its ``cover.png`` (160x144 pixel art), at the root of the project folder.

The card is what the Games page shows for a game, and what ``chromatic_present_game`` requires before
it shows a game to the user. The project's own sources stay the game's truth; the card describes it.
Both files sit next to the ``.gbsproj`` and are not game sources (``games.sources_newer_than`` skips
them), so writing them never marks a built game as changed.

Unknown keys in ``game.json`` are kept, so later versions can add fields without losing anything.
Reads PNGs with the standard library only (the plugin process has no image library).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
import tempfile
import time
import zlib
from pathlib import Path

CARD_FILE = "game.json"
COVER_FILE = "cover.png"
CARD_FILES = frozenset({CARD_FILE, COVER_FILE})
VERSION = 1

COVER_WIDTH, COVER_HEIGHT = 160, 144
MAX_COVER_COLOURS = 32
MIN_COVER_COLOURS = 3
MAX_COVER_BYTES = 512 * 1024
MAX_CARD_BYTES = 64 * 1024

GENRES = (
    "Action",
    "Adventure",
    "Arcade",
    "Exploration",
    "Platformer",
    "Puzzle",
    "Racing",
    "Role-playing",
    "Rhythm",
    "Shooter",
    "Simulation",
    "Sports",
    "Strategy",
    "Story",
    "Other",
)
LIMITS = {
    "title": (1, 60),
    "tagline": (8, 90),
    "description": (40, 400),
    "about": (0, 4000),
}
MAX_GENRES = 3
MAX_TAGS = 12
MAX_TAG_CHARS = 24
MAX_CONTROLS = 12
MAX_BUTTON_CHARS = 20
MAX_CONTROL_CHARS = 60
TEXT_FIELDS = ("title", "tagline", "description", "about")
REQUIRED = ("title", "tagline", "description", "genres", "cover")
PLACEHOLDER = re.compile(r"\b(todo|tbd|tbc|lorem ipsum|placeholder|fill (this|me) in|coming soon)\b", re.I)


def card_path(root: Path) -> Path:
    return Path(root) / CARD_FILE


def cover_path(root: Path) -> Path:
    return Path(root) / COVER_FILE


# -- reading and writing ---------------------------------------------------------------


def load(root: Path) -> dict:
    """The card as stored, or an empty dict when there is none (or it cannot be read)."""
    path = card_path(root)
    try:
        if path.stat().st_size > MAX_CARD_BYTES:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(root: Path, data: dict) -> None:
    path = card_path(root)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=".game-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def scaffold(root: Path, title: str) -> dict:
    """Write a starter card (the title, everything else empty) unless the game has one."""
    root = Path(root)
    existing = load(root)
    if existing or card_path(root).exists():
        return existing
    data = {
        "version": VERSION,
        "title": (title or root.name).strip()[: LIMITS["title"][1]],
        "tagline": "",
        "description": "",
        "about": "",
        "genres": [],
        "tags": [],
        "controls": {},
        "cover": None,
        "createdAt": int(time.time()),
    }
    _write(root, data)
    return data


# -- the cover ----------------------------------------------------------------------------


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
    try:
        raw = zlib.decompress(b"".join(chunks))
    except zlib.error as error:
        raise PngError(f"the PNG data is damaged ({error})") from error
    bits = depth * channels
    stride = (width * bits + 7) // 8
    step = max(1, bits // 8)
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
        size = path.stat().st_size
    except OSError:
        return {"ok": False, "problem": f"{path} does not exist."}
    if size > MAX_COVER_BYTES:
        return {
            "ok": False,
            "problem": f"The cover file is {size // 1024} KB; a 160x144 pixel-art PNG is far "
            "smaller. Save it as a plain PNG.",
        }
    try:
        data = path.read_bytes()
        width, height, pixels = decode_png(data)
    except PngError as error:
        return {"ok": False, "problem": f"The cover cannot be read: {error}."}
    except OSError as error:
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


def copied_asset(root: Path, sha256: str) -> str | None:
    """The game image (under ``assets/``) the cover is an unchanged copy of, if any: a cover is drawn for
    the card (characters, title), not an existing background reused."""
    assets = Path(root) / "assets"
    if not assets.is_dir():
        return None
    for count, path in enumerate(assets.rglob("*.png")):
        if count > 2000:
            break
        try:
            if path.stat().st_size <= MAX_COVER_BYTES and hashlib.sha256(path.read_bytes()).hexdigest() == sha256:
                return path.relative_to(root).as_posix()
        except OSError:
            continue
    return None


def _copy_problem(name: str) -> str:
    return (
        f"The cover is an unchanged copy of {name}. Draw cover art for it: the main character and the "
        "game's title on a scene from the game."
    )


# -- checking a card -----------------------------------------------------------------------


def _text_problem(field: str, value) -> str | None:
    if not isinstance(value, str):
        return f"{field} must be text."
    low, high = LIMITS[field]
    text = value.strip()
    if len(text) < low:
        return f"{field} is empty." if not text else f"{field} is too short (at least {low} characters)."
    if len(text) > high:
        return f"{field} is too long (at most {high} characters, it has {len(text)})."
    if text and PLACEHOLDER.search(text):
        return f"{field} still has placeholder text; write the real thing."
    return None


def _list_problem(field: str, value) -> str | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return f"{field} must be a list of text."
    if field == "genres":
        unknown = [item for item in value if item not in GENRES]
        if unknown:
            return f"Unknown genre {', '.join(unknown)}; choose from: {', '.join(GENRES)}."
        if len(value) > MAX_GENRES:
            return f"At most {MAX_GENRES} genres."
    else:
        if len(value) > MAX_TAGS:
            return f"At most {MAX_TAGS} tags."
        if any(not item.strip() or len(item.strip()) > MAX_TAG_CHARS for item in value):
            return f"Each tag is 1 to {MAX_TAG_CHARS} characters."
    return None


def _controls_problem(value) -> str | None:
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        return "controls must map a button to what it does, e.g. {\"A\": \"jump\"}."
    if len(value) > MAX_CONTROLS:
        return f"At most {MAX_CONTROLS} controls."
    if any(
        not k.strip() or not v.strip() or len(k) > MAX_BUTTON_CHARS or len(v) > MAX_CONTROL_CHARS
        for k, v in value.items()
    ):
        return (
            f"Each control is a button name (up to {MAX_BUTTON_CHARS} characters) and what it does "
            f"(up to {MAX_CONTROL_CHARS} characters)."
        )
    return None


def status(root: Path, data: dict | None = None, *, strict: bool = False) -> dict:
    """What the card still needs: ``{complete, missing: [field], problems: [text], cover}``. ``strict``
    (presenting) also refuses a cover copied unchanged from the game's assets."""
    root = Path(root)
    data = load(root) if data is None else data
    missing, problems = [], []
    for field in ("title", "tagline", "description"):
        problem = _text_problem(field, data.get(field, ""))
        if problem:
            missing.append(field)
            if data.get(field):
                problems.append(problem)
    genres = data.get("genres")
    if not genres or _list_problem("genres", genres):
        missing.append("genres")
        if genres:
            problems.append(_list_problem("genres", genres))
    cover = check_cover(cover_path(root)) if cover_path(root).is_file() else None
    if cover and cover["ok"] and strict:
        copied = copied_asset(root, cover["sha256"])
        if copied:
            cover = {**cover, "ok": False, "problem": _copy_problem(copied)}
    if not cover or not cover["ok"]:
        missing.append("cover")
        if cover:
            problems.append(cover["problem"])
    return {"complete": not missing, "missing": missing, "problems": problems, "cover": cover}


def next_step(missing: list[str]) -> str:
    """What the agent should do about the missing fields, in one instruction."""
    if not missing:
        return "The game card is complete."
    words = [("cover (the PNG path)" if field == "cover" else field) for field in missing]
    draw = (
        f"Draw a {COVER_WIDTH}x{COVER_HEIGHT} pixel-art cover yourself in the game's own palette (its main "
        "character and title on a scene from the game; see hermretro:pixel-art, never Image Generation), "
        "then call"
        if "cover" in missing
        else "Call"
    )
    return f"{draw} chromatic_game_info with " + ", ".join(words) + "."


# -- updating ---------------------------------------------------------------------------


def update(
    root: Path,
    fields: dict,
    *,
    cover_source: str | None = None,
    build_sha: str | None = None,
    default_title: str | None = None,
) -> dict:
    """Check and store the given fields (all or nothing). ``{ok, problems?, card, status, was_complete}``:
    ``was_complete`` is the strict completeness before this change, so ``result["status"]["complete"] and not
    result["was_complete"]`` is the moment the card became complete."""
    root = Path(root)
    problems = []
    for field in TEXT_FIELDS:
        if field in fields:
            value = fields[field]
            problem = _text_problem(field, value) if not (field == "about" and value == "") else None
            if problem:
                problems.append(problem)
    for field in ("genres", "tags"):
        if field in fields:
            problem = _list_problem(field, fields[field])
            if problem:
                problems.append(problem)
    if "controls" in fields:
        problem = _controls_problem(fields["controls"])
        if problem:
            problems.append(problem)
    cover, source = None, None
    if cover_source is not None:
        source = Path(str(cover_source).removeprefix("file://")).expanduser()
        if not source.is_absolute():
            source = root / source
        cover = check_cover(source)
        if not cover["ok"]:
            problems.append(cover["problem"])
        else:
            copied = copied_asset(root, cover["sha256"])
            if copied:
                problems.append(_copy_problem(copied))
    if problems:
        return {"ok": False, "problems": problems}
    try:  # a damaged old card or cover must never block the update that repairs it
        was_complete = status(root, load(root) or {}, strict=True)["complete"]
    except Exception:
        was_complete = False
    data = load(root) or {"version": VERSION, "createdAt": int(time.time())}
    data.setdefault("title", (default_title or root.name)[: LIMITS["title"][1]])
    for field in TEXT_FIELDS:
        if field in fields:
            data[field] = fields[field].strip()
    if "genres" in fields:
        data["genres"] = list(dict.fromkeys(fields["genres"]))
    if "tags" in fields:
        data["tags"] = list(dict.fromkeys(tag.strip() for tag in fields["tags"]))
    if "controls" in fields:
        data["controls"] = {k.strip(): v.strip() for k, v in fields["controls"].items()}
    if cover is not None and source is not None:
        target = cover_path(root)
        if source.resolve() != target.resolve():
            handle, temporary = tempfile.mkstemp(prefix=".cover-", suffix=".png", dir=str(root))
            try:
                with os.fdopen(handle, "wb") as stream:
                    stream.write(source.read_bytes())
                os.replace(temporary, target)
            except BaseException:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
        data["cover"] = COVER_FILE
        data["coverSha256"] = cover["sha256"]
        data["coverForBuild"] = build_sha
    if not isinstance(data.get("version"), int) or data["version"] < VERSION:
        data["version"] = VERSION
    data["updatedAt"] = int(time.time())
    _write(root, data)
    return {"ok": True, "card": data, "status": status(root, data, strict=True), "was_complete": was_complete}


# -- for the desktop ---------------------------------------------------------------------

_cover_cache: dict[str, tuple[tuple[float, int], str | None]] = {}


def cover_data_url(root: Path) -> str | None:
    """The cover as a data URL when it is a valid one (cached by file time and size)."""
    path = cover_path(root)
    try:
        info = path.stat()
    except OSError:
        return None
    stamp = (info.st_mtime, info.st_size)
    cached = _cover_cache.get(str(path))
    if cached and cached[0] == stamp:
        return cached[1]
    value = None
    if check_cover(path)["ok"]:
        value = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    if len(_cover_cache) > 500:
        _cover_cache.clear()
    _cover_cache[str(path)] = (stamp, value)
    return value


def public(root: Path) -> dict | None:
    """The card for the Games page, or None when the game has none."""
    data = load(root)
    if not data:
        return None
    state = status(root, data)

    def text(key: str) -> str:
        value = data.get(key)
        return value.strip() if isinstance(value, str) else ""

    return {
        "title": text("title") or None,
        "tagline": text("tagline") or None,
        "description": text("description") or None,
        "about": text("about") or None,
        "genres": [g for g in data.get("genres") or [] if isinstance(g, str)][:MAX_GENRES],
        "tags": [t for t in data.get("tags") or [] if isinstance(t, str)][:MAX_TAGS],
        "controls": {k: v for k, v in (data.get("controls") or {}).items() if isinstance(k, str) and isinstance(v, str)}
        if isinstance(data.get("controls"), dict)
        else {},
        "complete": state["complete"],
        "missing": state["missing"],
        "hasCover": bool(state["cover"] and state["cover"]["ok"]),
        "coverForBuild": data.get("coverForBuild") if isinstance(data.get("coverForBuild"), str) else None,
    }
