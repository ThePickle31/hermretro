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
    "does not exist yet."
)

# Build it: what the first build holds is agreed as a list the user approves, then all of it is built before the game
# is presented.
AGREE_A_LIST = (
    "Ask the user a few quick questions in one short message, offering sensible defaults. Once they have answered, "
    "reply with a short list of what you will make (concept, controls, core loop, rooms or levels, characters, how "
    "to win and lose, art and colours, what is left out) and end your turn: change the list whenever the user asks, "
    "and create nothing until they approve it."
)
BUILD_THE_LIST = (
    "Once the user approves the list, create the project, save the approved list in it as "
    "docs/game/FIRST-BUILD.md and build all of it in one go. Before presenting, check every item against the build "
    "and name in the build report anything that is not in it."
)
# Plan first: once the brief is approved, the same one full build.
BUILD_THE_BRIEF = (
    "Once the user approves the brief, build everything in its scope in one go, then check the test plan against "
    "the build before presenting."
)


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
        return {
            "context": (
                f"[hermretro] This is the Build conversation of the game \"{title}\" "
                f"({bound.get('projectRoot')}). The game is selected for you on the first chromatic "
                "call. This conversation works on this one game: do not create or open other "
                "projects here; for another game the user uses New Game or picks it on the "
                "hermretro Build page. "
                + SHOW_ART_CONTEXT
                + " "
                + host.GAME_STEPS
                + " "
                + host.BUILD_REPORT_GUIDANCE
                + " "
                + host.GAME_RULES
            )
        }
    if kind == "pending":
        name = bound.get("name")
        called = f" called \"{name}\"" if name else ""
        if bound.get("plan"):
            how = (
                "Plan it first: load hermretro:game-planning, interview the user briefly, create the project, write "
                "the game brief, backlog and test plan into it, and wait for the user to approve the brief before "
                "authoring anything. " + BUILD_THE_BRIEF
            )
            later = (
                ". If its project does not exist yet, create it once the user is ready. Author nothing until the "
                "user has approved the game brief (hermretro:game-planning). " + BUILD_THE_BRIEF
            )
        else:
            how = AGREE_A_LIST + " " + BUILD_THE_LIST
            later = (
                ". Until the user approves the list of what you will make, create nothing and change the list as "
                "they ask. " + BUILD_THE_LIST
            )
        start = ("; their message is the idea. " + how) if is_first_turn else later
        return {
            "context": (
                f"[hermretro] The user started a new Game Boy Color game{called} with New Game on the "
                "hermretro Build page" + start + " Create exactly one new "
                "project (chromatic_project_create or chromatic_project_create_blank): it becomes this "
                "conversation's game. " + host.GAME_STEPS + " " + host.GAME_RULES
            )
        }
    return None
