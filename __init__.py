"""hermretro for Hermes: plugin registration.

Registration is fast and offline. It starts no process, downloads nothing and touches no USB:
the broker and engine workers start lazily on the first tool call.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .adapter import contracts, hermes_host

logger = logging.getLogger(__name__)


def register(ctx):
    for tool in contracts.pinned_tools():
        schema = contracts.hermes_schema(tool)
        ctx.register_tool(name=schema["name"], toolset=contracts.TOOLSET, schema=schema,
                          handler=hermes_host.make_tool_handler(ctx, tool), emoji="🎮")

    ctx.register_tool(name=hermes_host.DEVICE_CLI_TOOL["name"], toolset=contracts.TOOLSET,
                      schema=hermes_host.DEVICE_CLI_TOOL, handler=hermes_host.device_cli_handler, emoji="🎮")
    # Plugin-owned, not an engine tool: shows the finished game beside the chat; never touches hardware.
    ctx.register_tool(name=hermes_host.PRESENT_TOOL["name"], toolset=contracts.TOOLSET,
                      schema=hermes_host.PRESENT_TOOL, handler=hermes_host.present_game_handler, emoji="🎮")

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if child.is_dir() and (child / "SKILL.md").is_file():
                ctx.register_skill(child.name, child / "SKILL.md")

    ctx.register_rpc("status", hermes_host.rpc_status(ctx))
    ctx.register_rpc("doctor", hermes_host.rpc_doctor(ctx))
    ctx.register_rpc("activity", hermes_host.rpc_activity(ctx))
    ctx.register_rpc("studio_profile", hermes_host.rpc_studio_profile(ctx))
    ctx.register_rpc("install", hermes_host.rpc_install(ctx))
    ctx.register_rpc("games", hermes_host.rpc_games(ctx))
    ctx.register_rpc("game_thumb", hermes_host.rpc_game_thumb(ctx))
    ctx.register_rpc("player", hermes_host.rpc_player(ctx))
    ctx.register_rpc("presentations", hermes_host.rpc_presentations(ctx))
    ctx.register_rpc("captures", hermes_host.rpc_captures(ctx))
    ctx.register_rpc("capture_image", hermes_host.rpc_capture_image(ctx))

    ctx.register_hook("pre_tool_call", hermes_host.make_pre_tool_call(ctx))
    ctx.register_hook("subagent_start", hermes_host.on_subagent_start)
    ctx.register_hook("subagent_stop", hermes_host.on_subagent_stop)

    register_section = getattr(ctx, "register_system_prompt_section", None)
    if callable(register_section):
        register_section("hermretro.guide", hermes_host.SYSTEM_PROMPT_SECTION,
                         position="after_memory", max_chars=2000)
