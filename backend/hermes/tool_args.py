"""Helpers any feature's plugin-owned tool shares: the failure answer and the project the tool acts on.

A tool module imports them as ``from ..hermes.tool_args import tool_error, tool_project`` (the Hermes layer is shared,
so every feature but the standard-library-only ones the broker imports may use it). A tool about the selected game
resolves the project with ``tool_project`` and then its library game with ``host.library_game_for([root])``.
``backend/library/tool_args.py`` re-exports both for the library's tool handlers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import host
from .results import ADAPTER_ERROR_NEXT_STEP


def tool_error(message: str, code: str, next_step: str | None = None) -> str:
    """A tool's failure answer: ``{"ok": false, "error": message, "code": code, "nextStep": ...}`` as JSON.
    ``nextStep`` tells the agent what to do about it: ``next_step``, else the one its code always has."""
    next_step = next_step or NEXT_STEPS.get(code) or "Fix what the error says, then call the tool again."
    return json.dumps({"ok": False, "error": message, "code": code, "nextStep": next_step})


# The next step of a failure whose code always means the same thing.
NEXT_STEPS = {
    "ADAPTER_ERROR": ADAPTER_ERROR_NEXT_STEP,
    "INVALID_ARGUMENTS": "Fix the argument the error names and call the tool again.",
    "PROJECT_NOT_FOUND": "Leave out project to use this chat's game, or pass the absolute folder of an existing "
    "project.",
    "NO_PROJECT": "Create or select the game's project first, then call the tool again.",
    "PARENT_ONLY": "Return what you found to the main conversation; it makes this call.",
}


def _same_folder(one, other) -> bool:
    try:
        return os.path.samefile(one, other)
    except (OSError, ValueError):
        return False


def other_game_refusal(tool: str, folder: Path, conversation_id: str, session_id: str) -> str | None:
    """The refusal when this chat may not act on ``folder``: a library game is acted on only from its own
    conversation. ``ONE_GAME_PER_CONVERSATION`` for a game's Build conversation and another folder, ``NEW_GAME_ONLY``
    for a New Game conversation and an existing library game, ``GAME_CHAT_ONLY`` for any other chat and a library
    game; None when the chat may act on it."""
    registry = host._registry()
    data = registry.load()
    ids = [value for value in (conversation_id, session_id) if value]
    kind, bound = registry.binding_for(host._profile_identity(), ids, snapshot=data) if ids else (None, None)
    # The game the folder is in: itself, or the deepest game whose folder holds it.
    other = registry.owning_game(str(folder), snapshot=data)
    if kind == "game":
        if other is not None and other["id"] == bound.get("id") and _same_folder(folder, other["projectRoot"]):
            return None
        title = bound.get("title") or Path(bound["projectRoot"]).name
        return tool_error(
            f"This conversation belongs to the game \"{title}\" ({bound['projectRoot']}), so {tool} cannot act on "
            f"{folder}. Nothing was changed.",
            "ONE_GAME_PER_CONVERSATION",
            f"Leave out project to act on \"{title}\". To work on another game, tell the user to open it on the "
            "hermretro Build page.",
        )
    if other is None:
        return None
    title = other.get("title") or Path(other["projectRoot"]).name
    if kind == "pending":
        return tool_error(
            f"This conversation is for a new game, so {tool} cannot act on \"{title}\" ({other['projectRoot']}). "
            "Nothing was changed.",
            "NEW_GAME_ONLY",
            "Create the new game's project first and leave out project. To work on that game, tell the user to open "
            "it on the hermretro Build page.",
        )
    return tool_error(
        f"\"{title}\" ({other['projectRoot']}) is worked on only in its own conversation, so {tool} cannot act on "
        "it from this chat. Nothing was changed.",
        "GAME_CHAT_ONLY",
        f"Tell the user to open \"{title}\" on the hermretro Build page and continue there.",
    )


def tool_project(tool: str, args: dict, kwargs: dict) -> tuple[str | None, str | None]:
    """The project a plugin-owned tool acts on: ``project`` when given, else this chat's. A game's Build
    conversation acts on its own game only. Returns ``(root, None)`` or ``(None, error json)``; the codes are
    ``INVALID_ARGUMENTS``, ``PROJECT_NOT_FOUND``, ``ONE_GAME_PER_CONVERSATION``, ``NEW_GAME_ONLY``, ``GAME_CHAT_ONLY``
    and ``NO_PROJECT``."""
    conversation_id = str(kwargs.get("conversation_id") or "")
    session_id = str(kwargs.get("session_id") or "")
    project = args.get("project")
    if project is not None and (not isinstance(project, str) or not project.strip()):
        return None, tool_error("project must be an absolute folder path.", "INVALID_ARGUMENTS")
    if project:
        candidate = Path(project).expanduser()
        if not candidate.is_absolute() or not candidate.is_dir():
            return None, tool_error(
                f"{project} is not an existing project folder (give an absolute path).", "PROJECT_NOT_FOUND"
            )
        refused = other_game_refusal(tool, candidate, conversation_id, session_id)
        if refused:
            return None, refused
        return str(candidate), None
    root = host._chat_project(conversation_id, session_id)
    if not root or not Path(root).is_dir():
        return None, tool_error(
            f"This chat has no current project. Select or create the game's project, then call {tool} again (or "
            "pass project).",
            "NO_PROJECT",
        )
    # The chat's project can be a game this chat no longer owns (its chat link after Stop editing).
    refused = other_game_refusal(tool, Path(root), conversation_id, session_id)
    if refused:
        return None, refused
    return root, None
