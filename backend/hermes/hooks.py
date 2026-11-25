"""The Hermes layer's own hooks: hardware approvals, tracking delegated subagents (whose tool calls some tools
refuse), and where a chat stands after a context compaction (``chat_state``; the engine tool handler delivers it).
Other features chain their own hooks onto the same names from their folders."""

from __future__ import annotations

from . import chat_state, host
from .declare import hook

hook("pre_tool_call", needs_ctx=True)(host.make_pre_tool_call)
hook("subagent_start")(host.on_subagent_start)
hook("subagent_start")(chat_state.child_started)
hook("subagent_stop")(host.on_subagent_stop)
hook("subagent_stop")(chat_state.child_stopped)
hook("post_tool_call")(chat_state.observe)
hook("post_compaction")(chat_state.compacted)
