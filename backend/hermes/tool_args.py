"""Helpers any feature's plugin-owned tool shares: the failure answer and the project the tool acts on.

A tool module imports them as ``from ..hermes.tool_args import tool_error, tool_project`` (the Hermes layer is shared,
so every feature but the standard-library-only ones the broker imports may use it). A tool about the selected game
resolves the project with ``tool_project`` and then its library game with ``host.library_game_for([root])``.
``backend/library/tool_args.py`` re-exports both and lists the codes the library's tools answer with.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import host


def tool_error(message: str, code: str) -> str:
    """A tool's failure answer: ``{"ok": false, "error": message, "code": code}`` as JSON."""
    return json.dumps({"ok": False, "error": message, "code": code})


def tool_project(tool: str, args: dict, kwargs: dict) -> tuple[str | None, str | None]:
    """The project a plugin-owned tool acts on: ``project`` when given, else this chat's. Returns
    ``(root, None)`` or ``(None, error json)``; the codes are ``INVALID_ARGUMENTS``, ``PROJECT_NOT_FOUND`` and
    ``NO_PROJECT``."""
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
        return str(candidate), None
    root = host._chat_project(conversation_id, session_id)
    if not root or not Path(root).is_dir():
        return None, tool_error(
            f"This chat has no current project. Select or create the game's project, then call {tool} again (or "
            "pass project).",
            "NO_PROJECT",
        )
    return root, None
