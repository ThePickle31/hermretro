"""Helpers every library tool shares: the error answer and the project a tool acts on, defined in
``backend/hermes/tool_args.py`` (any feature's tools use them from there) and re-exported here. A new library tool
module imports these from here (``from .tool_args import tool_error, tool_project``) rather than from tools.py,
so tool modules never import each other. The library itself is ``host._registry()``.

"""

from __future__ import annotations

from ..hermes.tool_args import other_game_refusal, tool_error, tool_project

__all__ = ["other_game_refusal", "tool_error", "tool_project"]
