"""Helpers every library tool shares: the error answer and the project a tool acts on, defined in
``backend/hermes/tool_args.py`` (any feature's tools use them from there) and re-exported here. A new library tool
module imports these from here (``from .tool_args import tool_error, tool_project``) rather than from tools.py,
so tool modules never import each other. The library itself is ``host._registry()``.

The ``code`` of a library tool's failure answer (with a ``nextStep`` saying what to do), each in use (tests/backend/library/test_tool_args.py keeps this
list and the code in step):

- ``INVALID_ARGUMENTS``: an argument has the wrong type or shape (``project``, ``note``, ``cover``).
- ``PROJECT_NOT_FOUND``: ``project`` (or the game's folder) is not an existing folder.
- ``NO_PROJECT``: no ``project`` was given and this chat has none.
- ``ONE_GAME_PER_CONVERSATION``: ``project`` names another game than the one this Build conversation belongs to.
- ``NEW_GAME_ONLY``: a New Game conversation named an existing game's folder in ``project``.
- ``PARENT_ONLY``: a delegated subagent called a tool only the main conversation may call.
- ``BUILD_FIRST``: ``chromatic_present_game`` while the game's playable copy is missing, out of date or not the
  engine's own (``export_freshness``; ``nextStep`` says which fix).
- ``GAME_INFO_INCOMPLETE``: ``chromatic_present_game`` before the game card is finished.
- ``INVALID_GAME_INFO``: ``chromatic_game_info`` refused the card (``problems`` says why; nothing changed).
- ``INVALID_REPORT``: ``chromatic_build_report`` refused the report (``problems`` says why).
- ``ADAPTER_ERROR``: an unexpected error inside the plugin (its type and message).
"""

from __future__ import annotations

from ..hermes.tool_args import other_game_refusal, tool_error, tool_project

__all__ = ["other_game_refusal", "tool_error", "tool_project"]
