"""The emulator's device skins: one folder each, ``player/skins/<id>/``, holding ``skin.webp`` (or ``skin.png``) and,
optionally, ``skin.json``.

The JSON names the skin and its colours: ``{"name": "Midnight", "edition": "Hermes Edition", "background":
"#15171c", "ink": "#e6edf3", "order": 1}``, every field optional. ``background`` is the page behind the handheld
and the swatch, ``ink`` the text on it, ``order`` its place in the lists (then the id); the first skin is the
default. The player's colour rail lists them before the engine's own finishes, and the Build page's player menu
from the ``player`` RPC. Standard library only.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..system import paths

logger = logging.getLogger(__name__)

SKINS_DIR = paths.PLUGIN_ROOT / "player" / "skins"
IMAGE_TYPES = (".webp", ".png")
SKIN_ID = re.compile(r"[a-z0-9-]{1,40}")
COLOUR = re.compile(r"#[0-9a-fA-F]{6}")
DEFAULTS = {"edition": "", "background": "#15171c", "ink": "#e6edf3", "order": 100}
# The engine's own finishes (its view.js ``DEVICE_COLORS``) and the id prefix its stylesheet treats specially.
ENGINE_VIEW = paths.ENGINE_ROOT / "dist" / "web-annotations" / "view.js"
ENGINE_PREFIX = "transparent-"
_engine_cache: dict[tuple, frozenset] = {}


def engine_ids() -> frozenset:
    """The ids of the engine's own finishes: a skin may not take one."""
    try:
        info = ENGINE_VIEW.stat()
    except OSError:
        return frozenset()
    key = (info.st_size, info.st_mtime_ns)
    if key not in _engine_cache:
        text = ENGINE_VIEW.read_text(encoding="utf-8")
        block = text[text.find("DEVICE_COLORS = [") : text.find("];", text.find("DEVICE_COLORS = ["))]
        _engine_cache.clear()
        _engine_cache[key] = frozenset(re.findall(r'\{ id: "([a-z0-9-]+)"', block))
    return _engine_cache[key]


def _text(value) -> str | None:
    """A JSON string field as text the player can serve, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return value.strip()


def _read(folder: Path) -> dict | None:
    """One skin from its folder, or None (logged) when it cannot be used."""
    skin_id = folder.name
    problem = (
        "a skin's folder is lower-case letters, digits and dashes (at most 40)"
        if not SKIN_ID.fullmatch(skin_id)
        else "the engine has a finish with that id"
        if skin_id in engine_ids() or skin_id.startswith(ENGINE_PREFIX)
        else "a skin is a folder, not a link"
        if folder.is_symlink()
        else None
    )
    if problem:
        logger.warning("hermretro: skin %s skipped: %s", skin_id, problem)
        return None
    files = {kind: folder / f"skin{kind}" for kind in (*IMAGE_TYPES, ".json")}
    if any(path.is_symlink() for path in files.values()):
        logger.warning("hermretro: skin %s skipped: its files must be files, not links", skin_id)
        return None
    image = next((files[kind] for kind in IMAGE_TYPES if files[kind].is_file()), None)
    if image is None:
        logger.warning("hermretro: skin %s skipped: its folder has no skin.webp or skin.png", skin_id)
        return None
    data = {}
    if files[".json"].is_file():
        try:
            data = json.loads((folder / "skin.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            logger.warning("hermretro: skin %s skipped: its skin.json does not read: %s", skin_id, error)
            return None
    data = data if isinstance(data, dict) else {}
    skin = {"id": skin_id, "name": skin_id.replace("-", " ").title(), **DEFAULTS, "image": image}
    for key in ("name", "edition"):
        if (text := _text(data.get(key))) is not None:
            skin[key] = text
    for key in ("background", "ink"):
        if isinstance(data.get(key), str) and COLOUR.fullmatch(data[key]):
            skin[key] = data[key]
    if isinstance(data.get("order"), int) and not isinstance(data["order"], bool):
        skin["order"] = data["order"]
    return skin


def skins() -> list[dict]:
    """Every usable skin, in order: ``{id, name, edition, background, ink, order, image}``."""
    if not SKINS_DIR.is_dir():
        return []
    found = [skin for folder in sorted(SKINS_DIR.iterdir()) if folder.is_dir() and (skin := _read(folder))]
    return sorted(found, key=lambda skin: (skin["order"], skin["id"]))


def default_skin() -> str:
    """The first skin's id (the one a player starts in), or the engine's first finish when there is none."""
    listed = skins()
    return listed[0]["id"] if listed else ""


def image_for(skin_id: str) -> Path | None:
    """The image of skin ``skin_id``, or None."""
    return next((skin["image"] for skin in skins() if skin["id"] == skin_id), None)


def page_skins() -> list[dict]:
    """The skins as the page's player menu shows them: ``{id, name, swatch}``."""
    return [{"id": skin["id"], "name": skin["name"], "swatch": skin["background"]} for skin in skins()]


def signature() -> tuple:
    """What changes when a skin is added, removed or edited (for caches built from them)."""
    return tuple((str(path), path.lstat().st_mtime_ns) for path in sorted(SKINS_DIR.glob("*/skin.*")))


def rail_entries() -> tuple[str, str]:
    """The engine's ``DEVICE_COLORS`` lines for the skins, and the CSS that puts them first in its colour rail."""

    def entry(skin: dict) -> str:
        label = f"{skin['edition']} · {skin['name']}" if skin["edition"] else skin["name"]
        quoted = [
            json.dumps(value, ensure_ascii=False) for value in (skin["id"], label, skin["background"], skin["ink"])
        ]
        return "    {{ id: {}, name: {}, background: {}, ink: {} }},\n".format(*quoted)

    listed = skins()
    lines = "".join(entry(skin) for skin in listed)
    css = "".join(
        f'.codex-game-view .cgv-color[data-device-color="{skin["id"]}"] {{ order: -4; }}\n' for skin in listed
    )
    return lines, css
