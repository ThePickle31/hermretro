"""The Hermes layer's own hooks: hardware approvals, and tracking delegated subagents (whose tool calls some
tools refuse). Other features chain their own hooks onto the same names from their folders."""

from __future__ import annotations

from . import host
from .declare import hook

hook("pre_tool_call", needs_ctx=True)(host.make_pre_tool_call)
hook("subagent_start")(host.on_subagent_start)
hook("subagent_stop")(host.on_subagent_stop)
