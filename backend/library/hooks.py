"""The library's Hermes hooks: a game's Build conversation is told which game it works on (``pre_llm_call``,
ephemeral context every turn)."""
from __future__ import annotations

from pathlib import Path

from ..hermes import host
from ..hermes.declare import hook


SHOW_ART_CONTEXT = (
    "To show the user a game's art (a sprite, background or cover), put the real file on its own line as "
    "MEDIA:<absolute path>, e.g. its assets/sprites/<name>.png: the Build page draws it in the game's colours, "
    "animates a sprite and opens it in its viewer (frames, palette, scenes, versions) on a click. Do not draw a "
    "preview or contact sheet to show existing art; make one only when the user asks for a picture that "
    "does not exist yet.")


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
        title = bound.get("title") or Path(bound.get("projectRoot") or "").name
        return {"context": (f"[hermretro] This is the Build conversation of the game \"{title}\" "
                            f"({bound.get('projectRoot')}). The game is selected for you on the first chromatic "
                            "call. This conversation works on this one game: do not create or open other "
                            "projects here; for another game the user uses New Game or picks it on the "
                            "hermretro Build page. " + SHOW_ART_CONTEXT + " " + host.BUILD_REPORT_GUIDANCE)}
    if kind == "pending":
        name = bound.get("name")
        called = f" called \"{name}\"" if name else ""
        how = ("Plan it first: load hermretro:game-planning, interview the user briefly, create the project, and "
               "write the game brief, backlog and test plan into it before building anything."
               if bound.get("plan") else
               "Ask the user a few quick questions first, then create the project, build it, fill in its game card "
               "with chromatic_game_info and show it with chromatic_present_game.")
        start = ("; their message is the idea. " + how) if is_first_turn else \
            ". If its project does not exist yet, create it once the user is ready."
        return {"context": (f"[hermretro] The user started a new Game Boy Color game{called} with New Game on the "
                            "hermretro Build page" + start + " Create exactly one new "
                            "project (chromatic_project_create or chromatic_project_create_blank): it becomes this "
                            "conversation's game. " + host.BUILD_REPORT_GUIDANCE)}
    return None
