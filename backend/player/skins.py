"""The emulator's device skins: one folder each, ``player/skins/<id>/``, holding ``skin.webp`` (or ``skin.png``) and,
optionally, ``skin.json``.

The JSON names the skin and its colours: ``{"name": "Nous Black", "edition": "Hermes Edition", "background":
"#15171c", "ink": "#e6edf3", "order": 1}``, every field optional. ``background`` is the page behind the handheld
and the swatch, ``ink`` the text on it, ``order`` its place in the lists (then the id); the first skin is the
default. They are every finish the player has: its colour rail lists them in place of the engine's own list, and
the Build page's player menu from the ``player`` RPC. A skin may take one of the engine's ids (``cloud``,
``supply-co``): the engine's player keys a few things on them, such as the lower screen of a ``transparent-`` shell.
Standard library only.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from ..system import paths

logger = logging.getLogger(__name__)

SKINS_DIR = paths.SKINS_DIR
IMAGE_TYPES = (".webp", ".png")
SKIN_ID = re.compile(r"[a-z0-9-]{1,40}")
COLOUR = re.compile(r"#[0-9a-fA-F]{6}")
DEFAULTS = {"edition": "", "background": "#15171c", "ink": "#e6edf3", "order": 100}


def _text(value) -> str | None:
    """A JSON string field as text the player can serve, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    return value.strip()


def _personal_image(path: Path) -> bool:
    """Check a personal finish before using it in place of a bundled one."""
    if not path.is_file():
        return False
    try:
        with path.open("rb") as stream:
            size = os.fstat(stream.fileno()).st_size
            header = stream.read(24)
            if path.suffix == ".png":
                if size < 57 or header[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
                    return False
                stream.seek(-12, os.SEEK_END)
                return stream.read() == b"\x00\x00\x00\x00IEND\xaeB`\x82"
            if size < 26 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
                return False
            declared = int.from_bytes(header[4:8], "little") + 8
            first_chunk = int.from_bytes(header[16:20], "little")
            return declared == size and 0 < first_chunk <= size - 20 and header[12:16] in (b"VP8 ", b"VP8L", b"VP8X")
    except OSError:
        return False


def _read(folder: Path, *, personal: bool) -> dict | None:
    """One skin from its folder, or None (logged) when it cannot be used."""
    skin_id = folder.name
    problem = (
        "a skin's folder is lower-case letters, digits and dashes (at most 40)"
        if not SKIN_ID.fullmatch(skin_id)
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
    usable = _personal_image if personal else Path.is_file
    image = next((files[kind] for kind in IMAGE_TYPES if usable(files[kind])), None)
    if image is None:
        logger.warning("hermretro: skin %s skipped: its folder has no usable skin.webp or skin.png", skin_id)
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


def _roots() -> tuple[Path, Path]:
    return SKINS_DIR, paths.hermretro_home() / "skins"


def skins() -> list[dict]:
    """Every usable skin, in order: ``{id, name, edition, background, ink, order, image}``."""
    found = {}
    for root in _roots():
        try:
            for folder in root.iterdir():
                try:
                    if folder.is_dir() and (skin := _read(folder, personal=root != SKINS_DIR)):
                        found[skin["id"]] = skin
                except OSError as error:
                    logger.warning("hermretro: cannot read skin %s: %s", folder.name, error)
        except FileNotFoundError:
            continue
        except OSError as error:
            logger.warning("hermretro: cannot read skins in %s: %s", root, error)
    return sorted(found.values(), key=lambda skin: (skin["order"], skin["id"]))


def default_skin() -> str:
    """The first skin's id (the one a player starts in), or "" when there is none."""
    listed = skins()
    return listed[0]["id"] if listed else ""


def image_for(skin_id: str) -> Path | None:
    """The image of skin ``skin_id``, or None."""
    return next((skin["image"] for skin in skins() if skin["id"] == skin_id), None)


def page_skins() -> list[dict]:
    """The skins as the page's player menu shows them: ``{id, name, swatch}``."""
    return [{"id": skin["id"], "name": skin["name"], "swatch": skin["background"]} for skin in skins()]


def rail_entries() -> str:
    """The skins as the lines of the engine's ``DEVICE_COLORS`` list, in order."""

    def entry(skin: dict) -> str:
        label = f"{skin['edition']} · {skin['name']}" if skin["edition"] else skin["name"]
        quoted = [
            json.dumps(value, ensure_ascii=False) for value in (skin["id"], label, skin["background"], skin["ink"])
        ]
        return "    {{ id: {}, name: {}, background: {}, ink: {} }},\n".format(*quoted)

    return "".join(entry(skin) for skin in skins())
