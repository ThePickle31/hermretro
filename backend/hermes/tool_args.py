"""Helpers any feature's plugin-owned tool shares: the failure answer and the project the tool acts on.

A tool module imports them as ``from ..hermes.tool_args import tool_error, tool_project`` (the Hermes layer is shared,
so every feature but the standard-library-only ones the broker imports may use it). A tool about the selected game
resolves the project with ``tool_project`` and then its library game with ``host.library_game_for([root])``.
``backend/library/tool_args.py`` re-exports both and lists the codes the library's tools answer with.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import host
from .results import ADAPTER_ERROR_NEXT_STEP


def tool_error(message: str, code: str, next_step: str | None = None) -> str:
    """A tool's failure answer: ``{"ok": false, "error": message, "code": code, "nextStep": ...}`` as JSON.
    ``nextStep`` tells the agent what to do about it; ``ADAPTER_ERROR`` always gets the same one."""
    payload = {"ok": False, "error": message, "code": code}
    next_step = next_step or (ADAPTER_ERROR_NEXT_STEP if code == "ADAPTER_ERROR" else None)
    if next_step:
        payload["nextStep"] = next_step
    return json.dumps(payload)


def other_game_refusal(tool: str, folder: Path, conversation_id: str, session_id: str) -> str | None:
    """The ``ONE_GAME_PER_CONVERSATION`` answer when this chat is a game's Build conversation and ``folder`` is not
    that game; None when the chat may act on ``folder``."""
    bound = host._bound_game(conversation_id, session_id)
    if bound is None or os.path.realpath(folder) == os.path.realpath(bound["projectRoot"]):
        return None
    title = bound.get("title") or Path(bound["projectRoot"]).name
    return tool_error(
        f"This conversation belongs to the game \"{title}\" ({bound['projectRoot']}), so {tool} cannot act on "
        f"{folder}. Nothing was changed.",
        "ONE_GAME_PER_CONVERSATION",
        f"Leave out project to act on \"{title}\". To work on another game, tell the user to open it on the "
        "hermretro Build page.",
    )


def tool_project(tool: str, args: dict, kwargs: dict) -> tuple[str | None, str | None]:
    """The project a plugin-owned tool acts on: ``project`` when given, else this chat's. A game's Build
    conversation acts on its own game only. Returns ``(root, None)`` or ``(None, error json)``; the codes are
    ``INVALID_ARGUMENTS``, ``PROJECT_NOT_FOUND``, ``ONE_GAME_PER_CONVERSATION`` and ``NO_PROJECT``."""
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
    return root, None
