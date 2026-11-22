"""The emulator's device skins: each is ``player/skins/<id>.webp`` (or ``.png``) with ``<id>.json`` beside it.

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


def _read(meta: Path) -> dict | None:
    """One skin from its JSON file, or None (logged) when it cannot be used."""
    skin_id = meta.stem
    if not SKIN_ID.fullmatch(skin_id):
        logger.warning("hermretro: skin %s skipped: an id is lower-case letters, digits and dashes", meta.name)
        return None
    image = next((meta.with_suffix(kind) for kind in IMAGE_TYPES if meta.with_suffix(kind).is_file()), None)
    if image is None:
        logger.warning("hermretro: skin %s skipped: no %s.webp or %s.png beside its JSON", skin_id, skin_id, skin_id)
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        logger.warning("hermretro: skin %s skipped: its JSON does not read: %s", skin_id, error)
        return None
    data = data if isinstance(data, dict) else {}
    skin = {"id": skin_id, "name": skin_id.replace("-", " ").title(), **DEFAULTS, "image": image}
    for key in ("name", "edition"):
        if isinstance(data.get(key), str) and data[key].strip():
            skin[key] = data[key].strip()
    for key in ("background", "ink"):
        if isinstance(data.get(key), str) and COLOUR.fullmatch(data[key]):
            skin[key] = data[key]
    if isinstance(data.get("order"), int) and not isinstance(data["order"], bool):
        skin["order"] = data["order"]
    return skin


def skins() -> list[dict]:
    """Every usable skin, in order: ``{id, name, edition, background, ink, order, image}``."""
    found = [skin for meta in sorted(SKINS_DIR.glob("*.json")) if (skin := _read(meta))]
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
    return tuple((path.name, path.stat().st_mtime_ns) for path in sorted(SKINS_DIR.glob("*")) if path.is_file())


def rail_entries(taken: set[str]) -> tuple[str, str]:
    """The engine's ``DEVICE_COLORS`` lines for the skins whose id the engine does not use itself, and the CSS that
    puts them first in its colour rail."""
    listed = []
    for skin in skins():
        if skin["id"] in taken:
            logger.warning("hermretro: skin %s skipped: the engine has a finish with that id", skin["id"])
        else:
            listed.append(skin)
    lines = "".join(
        "    { id: %s, name: %s, background: %s, ink: %s },\n"
        % tuple(
            json.dumps(value, ensure_ascii=False)
            for value in (
                skin["id"],
                f"{skin['edition']} · {skin['name']}" if skin["edition"] else skin["name"],
                skin["background"],
                skin["ink"],
            )
        )
        for skin in listed
    )
    css = "".join(
        f'.codex-game-view .cgv-color[data-device-color="{skin["id"]}"] {{ order: -4; }}\n' for skin in listed
    )
    return lines, css
