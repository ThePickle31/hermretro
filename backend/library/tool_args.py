"""Helpers every library tool shares: the error answer and the project a tool acts on. A new tool module
imports these from here (``from .tool_args import tool_error, tool_project``) rather than from tools.py,
so tool modules never import each other. The library itself is ``host._registry()``.

The ``code`` of a library tool's failure answer, each in use (tests/backend/library/test_tool_args.py keeps this
list and the code in step):

- ``INVALID_ARGUMENTS``: an argument has the wrong type or shape (``project``, ``note``, ``cover``).
- ``PROJECT_NOT_FOUND``: ``project`` (or the game's folder) is not an existing folder.
- ``NO_PROJECT``: no ``project`` was given and this chat has none.
- ``PARENT_ONLY``: a delegated subagent called a tool only the main conversation may call.
- ``BUILD_FIRST``: ``chromatic_present_game`` while the game's build is missing or out of date (``export_freshness``).
- ``GAME_INFO_INCOMPLETE``: ``chromatic_present_game`` before the game card is finished.
- ``INVALID_GAME_INFO``: ``chromatic_game_info`` refused the card (``problems`` says why; nothing changed).
- ``INVALID_REPORT``: ``chromatic_build_report`` refused the report (``problems`` says why).
- ``ADAPTER_ERROR``: an unexpected error inside the plugin (its type and message).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..hermes import host


def tool_error(message: str, code: str) -> str:
    """A tool's failure answer: ``{"ok": false, "error": message, "code": code}`` as JSON."""
    return json.dumps({"ok": False, "error": message, "code": code})


def tool_project(tool: str, args: dict, kwargs: dict) -> tuple[str | None, str | None]:
    """The project a plugin-owned tool acts on: ``project`` when given, else this chat's. Returns
    ``(root, None)`` or ``(None, error json)``."""
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


# The names tools.py has always used.
_present_error = tool_error
_tool_project = tool_project
