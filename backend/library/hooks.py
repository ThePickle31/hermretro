"""The library's Hermes hooks: a game's Build conversation is told which game it works on (``pre_llm_call``,
ephemeral context every turn)."""

from __future__ import annotations

from pathlib import Path

from ..hermes import host, workflow
from ..hermes.declare import hook


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
        guidance = _game_guidance(bound, root)
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


def _game_guidance(game: dict, root: str | None) -> str:
    presented = game.get("presented")
    if isinstance(presented, dict) and isinstance(presented.get("t"), (int, float)):
        return workflow.EDIT_GAME

    plan = game.get("initialPlan", (game.get("session") or {}).get("plan"))
    if plan is True:
        return workflow.PLAN_BOUND
    if plan is False:
        return workflow.BUILD_BOUND
    if root:
        # Older bindings did not keep the mode. Their plan files still say what
        # remains in scope. ROMs and web exports can be intermediate checkpoints.
        docs = Path(root, "docs", "game")
        if (docs / "GAME-BRIEF.md").is_file():
            return workflow.PLAN_BOUND
        if (docs / "FIRST-BUILD.md").is_file():
            return workflow.BUILD_BOUND
    return workflow.EDIT_GAME
