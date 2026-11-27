"""The engine's tools, pinned in engine/contract/tools.json, each exposed as ``chromatic_<name>`` and
handled by sending the call to the broker (host.make_tool_handler). Their step words live on the page."""

from __future__ import annotations

from . import contracts, host
from .declare import Tool


def TOOLS() -> list[Tool]:  # noqa: N802 - the name every feature's tools.py uses
    return [
        Tool(contracts.hermes_schema(tool), make=lambda ctx, tool=tool: host.make_tool_handler(ctx, tool))
        for tool in contracts.pinned_tools()
    ]
