"""hermretro for Hermes: plugin registration.

Registration is fast and offline. It starts no process, downloads nothing and touches no USB:
the broker and engine workers start lazily on the first tool call.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Linux and macOS only. Checked before the rest of the adapter is imported (it uses POSIX-only modules), so
# Windows gets one plain sentence in `hermes plugins list` instead of an import error. host_os is stdlib-only.
from .adapter.host_os import unsupported_reason

_UNSUPPORTED = unsupported_reason()

if not _UNSUPPORTED:
    from .adapter import contracts, hermes_host, studio_profile


def _profile(ctx) -> str | None:
    try:
        return ctx.profile_name
    except Exception:  # noqa: BLE001  (an older Hermes without it: the plugin's data folder names the profile)
        return studio_profile.profile_name(hermes_host._data_dir().parents[1])


def register(ctx):
    if _UNSUPPORTED:
        raise RuntimeError(_UNSUPPORTED)
    # The page's RPCs answer in every profile the plugin is on: the profile it was installed into sets up
    # the hermretro profile and the shared library. Everything an agent sees (tools, skills, hooks, the
    # prompt section) exists only in the hermretro profile.
    _register_rpcs(ctx)
    if studio_profile.is_studio(_profile(ctx)):
        _register_agent(ctx)


def _register_agent(ctx):
    for tool in contracts.pinned_tools():
        schema = contracts.hermes_schema(tool)
        ctx.register_tool(name=schema["name"], toolset=contracts.TOOLSET, schema=schema,
                          handler=hermes_host.make_tool_handler(ctx, tool), emoji="🎮")

    ctx.register_tool(name=hermes_host.DEVICE_CLI_TOOL["name"], toolset=contracts.TOOLSET,
                      schema=hermes_host.DEVICE_CLI_TOOL, handler=hermes_host.device_cli_handler, emoji="🎮")
    # Plugin-owned, not an engine tool: shows the finished game beside the chat; never touches hardware.
    ctx.register_tool(name=hermes_host.PRESENT_TOOL["name"], toolset=contracts.TOOLSET,
                      schema=hermes_host.PRESENT_TOOL, handler=hermes_host.present_game_handler, emoji="🎮")
    # Plugin-owned: the game card (game.json + cover.png) that presenting requires.
    ctx.register_tool(name=hermes_host.GAME_INFO_TOOL["name"], toolset=contracts.TOOLSET,
                      schema=hermes_host.GAME_INFO_TOOL, handler=hermes_host.game_info_handler, emoji="🎮")
    # Plugin-owned: the turn's build card on the Build page (checked and handed back; stores nothing).
    ctx.register_tool(name=hermes_host.BUILD_REPORT_TOOL["name"], toolset=contracts.TOOLSET,
                      schema=hermes_host.BUILD_REPORT_TOOL, handler=hermes_host.build_report_handler, emoji="🎮")

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if child.is_dir() and (child / "SKILL.md").is_file():
                ctx.register_skill(child.name, child / "SKILL.md")

    ctx.register_hook("pre_tool_call", hermes_host.make_pre_tool_call(ctx))
    ctx.register_hook("subagent_start", hermes_host.on_subagent_start)
    ctx.register_hook("subagent_stop", hermes_host.on_subagent_stop)
    # A game's Build conversation is told which game it works on (ephemeral context, every turn).
    ctx.register_hook("pre_llm_call", hermes_host.build_context)
    # Images a reply delivered or a step looked at are kept per version, so rewriting a file
    # (cover.png made again) does not change what an earlier reply on the Build page shows.
    ctx.register_hook("post_llm_call", hermes_host.keep_delivered_images)
    # The same hook also snapshots a library game after each successful build (Build page history).
    ctx.register_hook("post_tool_call", hermes_host.after_tool_call)

    register_section = getattr(ctx, "register_system_prompt_section", None)
    if callable(register_section):
        register_section("hermretro.guide", hermes_host.SYSTEM_PROMPT_SECTION,
                         position="after_memory", max_chars=2000)


def _register_rpcs(ctx):
    ctx.register_rpc("status", hermes_host.rpc_status(ctx))
    ctx.register_rpc("doctor", hermes_host.rpc_doctor(ctx))
    ctx.register_rpc("activity", hermes_host.rpc_activity(ctx))
    ctx.register_rpc("studio_profile", hermes_host.rpc_studio_profile(ctx))
    ctx.register_rpc("install", hermes_host.rpc_install(ctx))
    ctx.register_rpc("remove_tools", hermes_host.rpc_remove_tools(ctx))
    ctx.register_rpc("games", hermes_host.rpc_games(ctx))
    ctx.register_rpc("game_thumb", hermes_host.rpc_game_thumb(ctx))
    ctx.register_rpc("player", hermes_host.rpc_player(ctx))
    ctx.register_rpc("presentations", hermes_host.rpc_presentations(ctx))
    ctx.register_rpc("captures", hermes_host.rpc_captures(ctx))
    ctx.register_rpc("capture_image", hermes_host.rpc_capture_image(ctx))
    ctx.register_rpc("build", hermes_host.rpc_build(ctx))
    ctx.register_rpc("asset", hermes_host.rpc_asset(ctx))
    ctx.register_rpc("asset_info", hermes_host.rpc_asset_info(ctx))
    ctx.register_rpc("asset_restore", hermes_host.rpc_asset_restore(ctx))
    ctx.register_rpc("assets", hermes_host.rpc_assets(ctx))
    ctx.register_rpc("builds", hermes_host.rpc_builds(ctx))
    ctx.register_rpc("build_restore", hermes_host.rpc_build_restore(ctx))
