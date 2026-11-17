"""Turn the pinned original tool contracts into Hermes tool schemas.

The pinned file is the single source. Names gain a `chromatic_` prefix because
the originals (`device`, `setup`, `play`, `flash`) are too generic for a shared
registry. Local `$ref`s are inlined and `$schema` is dropped, because provider
tool-schema validators differ in what they accept; nothing else is changed.
"""
from __future__ import annotations

import copy
import json
import re
from functools import lru_cache

from ..system import paths

PREFIX = "chromatic_"
TOOLSET = "chromatic"

# Host wording only. The contract (arguments, behaviour) is untouched. Applied in order, so the
# web_preview sentence is rewritten before the generic one (which device_capture still uses): in Hermes
# the user plays the game in the hermretro emulator, shown with chromatic_present_game.
_DESCRIPTION_REWRITES = (
    ("Open the selected project's official player only in Codex's built-in browser.",
     "Open or refresh the selected project's official player (the engine's own preview). To show the game to "
     "the user in Hermes, call chromatic_present_game instead (it shows the game in the hermretro "
     "emulator); open this URL with desktop_preview only if the user says they cannot see that emulator."),
    ("only in Codex's built-in browser", "for the user to play. In Hermes Desktop, open the returned URL beside the "
                                         "chat with the desktop_preview tool (action \"open\"); without that tool, "
                                         "give the user the URL"),
    ("Codex", "Hermes"),
)


def _resolve(node, root, depth=0):
    if depth > 32:
        raise ValueError("Schema reference cycle")
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            if not ref.startswith("#/"):
                raise ValueError(f"Unsupported schema reference: {ref}")
            target = root
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                target = target[int(part)] if isinstance(target, list) else target[part]
            merged = copy.deepcopy(_resolve(target, root, depth + 1))
            for key, value in node.items():  # sibling keys (a local description) override the target's
                if key != "$ref":
                    merged[key] = _resolve(value, root, depth + 1)
            return merged
        return {key: _resolve(value, root, depth + 1) for key, value in node.items() if key != "$schema"}
    if isinstance(node, list):
        return [_resolve(item, root, depth + 1) for item in node]
    return node


@lru_cache(maxsize=1)
def pinned_tools() -> tuple[dict, ...]:
    return tuple(json.loads(paths.PINNED_TOOLS.read_text())["tools"])


def hermes_name(original: str) -> str:
    return PREFIX + original


def original_name(name: str) -> str:
    return name[len(PREFIX):] if name.startswith(PREFIX) else name


#: Tools that make a new project folder. In Hermes their destination is optional: without one the
#: backend puts the game in the hermretro games folder (``paths.games_dir``).
CREATORS = frozenset({"project_create", "project_create_blank"})


def default_destination(name: object) -> str:
    """``<games folder>/<Name without unsafe characters>`` for a new game called ``name``."""
    text = name if isinstance(name, str) else ""
    slug = re.sub(r"[^A-Za-z0-9 _.-]+", "", text).strip().strip(".") or "MyGame"
    return str(paths.games_dir() / slug[:80])


def hermes_schema(tool: dict) -> dict:
    description = tool.get("description", "")
    for before, after in _DESCRIPTION_REWRITES:
        description = description.replace(before, after)
    parameters = _resolve(tool["inputSchema"], tool["inputSchema"])
    if tool["name"] in CREATORS:
        games = str(paths.games_dir())
        description += (f" In hermretro, leave destinationPath out: the game is created in the Studio's "
                        f"games folder ({games}/<name>). Give a destinationPath only when the user asks for "
                        f"another folder.")
        parameters["required"] = [key for key in parameters.get("required", []) if key != "destinationPath"]
        destination = parameters.get("properties", {}).get("destinationPath")
        if isinstance(destination, dict):
            destination["description"] = (f"Optional. Default: {games}/<name>. Only for a folder the user "
                                          f"asked for: an absolute new path under an existing parent.")
    if tool["name"] == "project_select":
        # hermretro's own argument, removed by the broker before the engine sees it.
        parameters.setdefault("properties", {})["continueInThisChat"] = {
            "type": "boolean",
            "description": ("Only after the user confirmed it: work on a game that has its own hermretro Build "
                            "conversation from this chat anyway (its history will not include this work)."),
        }
    return {"name": hermes_name(tool["name"]), "description": description, "parameters": parameters}


@lru_cache(maxsize=1)
def hermes_schemas() -> tuple[dict, ...]:
    return tuple(hermes_schema(tool) for tool in pinned_tools())
