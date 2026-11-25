"""The library's Hermes hooks: a game's Build conversation is told which game it works on (``pre_llm_call``,
ephemeral context every turn), and Hermes's file tools write into a library game's folder only from that game's own
conversation and never into its ``.hermretro/`` (``pre_tool_call``). A terminal command is not parsed, so a shell
command can still write there: this guards the file tools, not the shell."""

from __future__ import annotations

import stat
from pathlib import Path

from ..hermes import host, workflow
from ..hermes.declare import hook
from . import file_guard


@hook("pre_tool_call")
def guard_game_record(tool_name=None, args=None, conversation_id=None, session_id=None, **_kwargs):
    """``pre_tool_call``: refuse a file-tool write into a game's ``.hermretro/`` (its id and publish record), into a
    library game's folder from any chat but that game's own conversation, or into a game without its source
    (``file_guard``)."""
    if tool_name not in file_guard.FILE_WRITE_TOOLS or not isinstance(args, dict):
        return None
    ids = [str(value) for value in (conversation_id, session_id) if value]
    message = file_guard.refusal(args, host._registry(), host._profile_identity(), ids)
    return {"action": "block", "message": message} if message else None


@hook("pre_llm_call")
def build_context(session_id=None, is_first_turn=False, **_kwargs):
    """``pre_llm_call``: tell a game's Build conversation which game it is (ephemeral, per turn)."""
    if not isinstance(session_id, str) or not session_id:
        return None
    try:
        kind, bound = host._registry().binding_for(host._profile_identity(), [session_id])
    except Exception:
        return None
    if kind == "game":
        root = bound.get("projectRoot")
        title = bound.get("title") or Path(root or "").name
        guidance = _game_guidance(bound, root, is_first_turn)
        return {
            "context": (
                f"[hermretro] This is the Build conversation of the game \"{title}\" "
                f"({bound.get('projectRoot')}). The game is selected for you on the first chromatic "
                "call. This conversation works on this one game: do not create or open other "
                "projects here; for another game the user uses New Game or picks it on the "
                "hermretro Build page. "
                + workflow.SHOW_ART_CONTEXT
                + " "
                + guidance
                + " "
                + workflow.BUILD_REPORT_GUIDANCE
                + " "
                + workflow.GAME_RULES
            )
        }
    if kind == "pending":
        name = bound.get("name")
        called = f" called \"{name}\"" if name else ""
        if is_first_turn:
            start = "; their message is the idea. " + (
                workflow.PLAN_START if bound.get("plan") else workflow.BUILD_START
            )
        else:
            start = ". " + (workflow.PLAN_CONTINUE if bound.get("plan") else workflow.BUILD_CONTINUE)
        return {
            "context": (
                f"[hermretro] The user started a new Game Boy Color game{called} with New Game on the "
                "hermretro Build page" + start + " Create exactly one new "
                "project (chromatic_project_create or chromatic_project_create_blank): it becomes this "
                "conversation's game. " + workflow.GAME_RULES
            )
        }
    return None


def _game_guidance(game: dict, root: str | None, first: bool) -> str:
    presented = game.get("presented")
    if isinstance(presented, dict) and isinstance(presented.get("t"), (int, float)):
        return workflow.EDIT_GAME

    session = game.get("session")
    session = session if isinstance(session, dict) else {}
    plan = game.get("initialPlan", session.get("plan"))
    if plan is True:
        return workflow.PLAN_BOUND
    if plan is False:
        return workflow.BUILD_BOUND
    if session.get("edit") is True or first or not root:
        return workflow.EDIT_GAME

    # A legacy New Game bound the chat before writing its plans or making its first build.
    # Earlier plans or activity belong to an existing game, even if later turns updated its notes.
    bound_at = session.get("createdAt")
    activity = (game.get(key) for key in ("lastBuild", "lastWebExport"))
    if isinstance(bound_at, (int, float)) and not any(
        isinstance(record, dict) and isinstance(record.get("t"), (int, float)) and record["t"] < bound_at
        for record in activity
    ):
        docs = Path(root, "docs", "game")
        for name, guidance in (("GAME-BRIEF.md", workflow.PLAN_BOUND), ("FIRST-BUILD.md", workflow.BUILD_BOUND)):
            try:
                info = (docs / name).stat(follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode) and info.st_mtime >= bound_at:
                return guidance
    return workflow.EDIT_GAME
