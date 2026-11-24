"""The game card: every game's ``game.json`` (title, tagline, description, about, genres, tags,
controls) and its ``cover.png`` (160x144 pixel art), at the root of the project folder.

The card is what the Games page shows for a game, and what ``chromatic_present_game`` requires before
it shows a game to the user. The project's own sources stay the game's truth; the card describes it.
Both files sit next to the ``.gbsproj`` and are not game sources (``games.sources_newer_than`` skips
them), so writing them never marks a built game as changed.

Unknown keys in ``game.json`` are kept, so later versions can add fields without losing anything.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path

from .game_cover import COVER_FILE, COVER_HEIGHT, COVER_WIDTH, _copy_problem, _cover, check_cover
from .game_cover import copied_asset, cover_path
from .game_cover import MAX_COVER_COLOURS as MAX_COVER_COLOURS  # public to tools.py's schema text
from .game_cover import MAX_COVER_BYTES as MAX_COVER_BYTES  # public to tools.py's schema text
from .game_cover import MIN_COVER_COLOURS as MIN_COVER_COLOURS  # public to tools.py's schema text
from .game_cover import cover_data_url as cover_data_url  # public to the shelf
from .game_cover import cover_problem as cover_problem  # public: backend/library/README.md

CARD_FILE = "game.json"
CARD_FILES = frozenset({CARD_FILE, COVER_FILE})
VERSION = 1

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


# -- reading and writing ---------------------------------------------------------------


def load(root: Path) -> dict:
    """The card as stored, or an empty dict when there is none (or it cannot be read)."""
    path = card_path(root)
    try:
        if path.stat().st_size > MAX_CARD_BYTES:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
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


def set_fields(root: Path, fields: dict) -> dict:
    """Merge ``fields`` into the stored card and write it, unchecked: the game layout's own fields (``id``,
    ``gameVersion``, ``rom``; ``backend/library/layout.py``), which ``update`` never takes."""
    data = {**load(root), **fields}
    _write(root, data)
    return data


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
    cover = _cover(root, strict)
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


def public(root: Path) -> dict | None:
    """The card for the Games page, or None when the game has none."""
    data = load(root)
    if not data:
        return None
    state = status(root, data)

    def text(key: str) -> str:
        value = data.get(key)
        return value.strip() if isinstance(value, str) else ""

    def strings(key: str, limit: int) -> list[str]:
        values = data.get(key)
        return [value for value in values if isinstance(value, str)][:limit] if isinstance(values, list) else []

    return {
        "title": text("title") or None,
        "tagline": text("tagline") or None,
        "description": text("description") or None,
        "about": text("about") or None,
        "genres": strings("genres", MAX_GENRES),
        "tags": strings("tags", MAX_TAGS),
        "controls": {k: v for k, v in (data.get("controls") or {}).items() if isinstance(k, str) and isinstance(v, str)}
        if isinstance(data.get("controls"), dict)
        else {},
        "complete": state["complete"],
        "missing": state["missing"],
        "hasCover": bool(state["cover"] and state["cover"]["ok"]),
        "coverForBuild": data.get("coverForBuild") if isinstance(data.get("coverForBuild"), str) else None,
    }
