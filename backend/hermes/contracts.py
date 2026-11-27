"""Turn the pinned engine tool contracts into Hermes tool schemas.

The pinned file is the single source. Names gain a `chromatic_` prefix because
the originals (`device`, `setup`, `play`, `flash`) are too generic for a shared
registry. Local `$ref`s are inlined and `$schema` is dropped, because provider
tool-schema validators differ in what they accept. A few tools then get hermretro's
own adjustments (`hermes_schema`): the project creators' destination is optional,
`rom_build`'s output path is explained, `script_inspect` gets its one-of, and
`scene_apply` accepts `operationsPath` instead of inline `operations`.
"""

from __future__ import annotations

import copy
import json
import os
import re
from functools import lru_cache

from ..system import paths

PREFIX = "chromatic_"
TOOLSET = "chromatic"


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
    return name[len(PREFIX) :] if name.startswith(PREFIX) else name


#: Tools that make a new project folder. In Hermes their destination is optional: without one the
#: backend puts the game in the hermretro games folder (``paths.games_dir``).
CREATORS = frozenset({"project_create", "project_create_blank"})


def default_destination(name: object) -> str:
    """``<games folder>/<Name without unsafe characters>`` for a new game called ``name``, numbered (``Name 2``,
    ``Name 3``, …) when that folder is taken: the engine only creates a project in a new folder."""
    text = name if isinstance(name, str) else ""
    slug = (re.sub(r"[^A-Za-z0-9 _.-]+", "", text).strip().strip(".") or "MyGame")[:80]
    folder = paths.games_dir() / slug
    number = 2
    while os.path.lexists(folder):
        folder = paths.games_dir() / f"{slug} {number}"
        number += 1
    return str(folder)


def hermes_schema(tool: dict) -> dict:
    description = tool.get("description", "")
    parameters = _resolve(tool["inputSchema"], tool["inputSchema"])
    if tool["name"] in CREATORS:
        games = str(paths.games_dir())
        description += (
            f" In hermretro, leave destinationPath out: the game is created in the Studio's "
            f"games folder ({games}/<name>). Give a destinationPath only when the user asks for "
            f"another folder."
        )
        parameters["required"] = [key for key in parameters.get("required", []) if key != "destinationPath"]
        destination = parameters.get("properties", {}).get("destinationPath")
        if isinstance(destination, dict):
            destination["description"] = (
                f"Optional. Default: {games}/<name>. Only for a folder the user "
                f"asked for: an absolute new path under an existing parent."
            )
    if tool["name"] == "rom_build":
        # The broker sets a project build's outputPath (backend/broker/broker.py game_rom_arguments).
        output = parameters.get("properties", {}).get("outputPath")
        if isinstance(output, dict):
            output["description"] = (
                "Leave it out for a project build: hermretro writes every build of a game to its one ROM, "
                "build/game.gbc (build/game.gb for a monochrome project), and refuses any other path. Only for "
                "standalone C (sourcePath)."
            )
    if tool["name"] == "script_inspect":
        # The engine lists a plain object (its MCP SDK drops a refinement from the listed schema) and refuses an
        # incomplete script only once it runs; Hermes's argument check refuses it before the call.
        flat = [key for key in parameters["properties"] if key not in ("target", "eventId")]
        parameters["oneOf"] = [
            {"required": ["sceneId"], "not": {"required": ["target"]}},
            {"required": ["target"], "not": {"anyOf": [{"required": [key]} for key in flat]}},
        ]
    if tool["name"] == "scene_apply":
        # hermretro's own argument: the broker reads the file into `operations` (backend/broker/operations_file.py).
        parameters.setdefault("properties", {})["operationsPath"] = {
            "type": "string",
            "description": (
                "Instead of operations: a JSON file holding them (a list, or an object with operations), inside the "
                "game's project (write it in its scratch/ folder) or Hermes's scratch folder (<Hermes home>/cache/"
                "scratch). A relative path such as scratch/ops.json is read from the project folder."
            ),
        }
        parameters["required"] = [key for key in parameters.get("required", []) if key != "operations"]
        parameters["oneOf"] = [{"required": ["operations"]}, {"required": ["operationsPath"]}]
    return {"name": hermes_name(tool["name"]), "description": description, "parameters": parameters}


@lru_cache(maxsize=1)
def hermes_schemas() -> tuple[dict, ...]:
    return tuple(hermes_schema(tool) for tool in pinned_tools())
