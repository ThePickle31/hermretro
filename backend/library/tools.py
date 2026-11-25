"""The library's plugin-owned tools (named on the Tools line of backend/library/README.md), with their schemas and
handlers. Declared in TOOLS at the end (backend/hermes/declare.py)."""

from __future__ import annotations

import json
from pathlib import Path

from .. import player as player_server
from ..hermes import host
from ..hermes.declare import Tool
from ..system.events import emit
from . import game_card, layout, pipeline, playtest_tools, report_tools
from . import games as library
from .tool_args import tool_error, tool_project

logger = host.logger  # one logger for the Hermes side of the backend

# Shared helpers (the data folder, the profile, the library, the broker client) stay in backend.hermes.host and are
# looked up there at call time, so one patch of host.<name> reaches every module.


# -- plugin-owned tool: show the finished game to the user -------------------------

PRESENT_TOOL = {
    "name": "chromatic_present_game",
    "description": (
        "Show the game to the user in the hermretro emulator beside the chat (ModRetro's player, served "
        "by the plugin). Call it once everything agreed with the user is built and you have tested it, and again after later "
        "changes the user should test; each call loads the newest build there. Nothing opens by itself after a "
        "build. Needs a fresh playable copy (run chromatic_rom_build first), for a game with a test plan its bound "
        "checks and F1 passed on this build (chromatic_playtest after every rebuild; unfinished only when the user "
        "asked to see it before that), and a complete game card (cover art, title, tagline, description, genres; "
        "set them with chromatic_game_info). Never touches a device. Do not open "
        "the game with desktop_preview instead or reload it with drive_preview; only if the user says they cannot "
        "see the emulator, open the returned studio.playerUrl with desktop_preview (action \"open\"), and without "
        "desktop tools give the user that url."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "maxLength": library.MAX_NOTE_CHARS,
                "description": "Optional short line shown to the user above the player, e.g. what to try.",
            },
            pipeline.OVERRIDE: {
                "type": "string",
                "minLength": 1,
                "maxLength": pipeline.MAX_OVERRIDE,
                "description": "Only when the user asked to see the game before its bound test-plan checks and F1 "
                "pass on this build: their request in a few words. The game is shown as it is, and the answer says "
                "what is not verified.",
            },
            "project": {
                "type": "string",
                "maxLength": 4096,
                "description": "Optional absolute project folder. Default: this chat's current project.",
            },
        },
        "additionalProperties": False,
    },
}


def present_game_handler(args: dict, **kwargs) -> str:
    """``chromatic_present_game``: record the presentation; the desktop opens the emulator tab when it
    sees this tool complete. Reads files and the library only: no engine call, no device."""
    try:
        args = args if isinstance(args, dict) else {}
        conversation_id = str(kwargs.get("conversation_id") or "")
        session_id = str(kwargs.get("session_id") or "")
        if host._is_child(session_id):
            return tool_error("Only the main conversation can show the game to the user.", "PARENT_ONLY")
        note = args.get("note")
        if note is not None and not isinstance(note, str):
            return tool_error("note must be a string.", "INVALID_ARGUMENTS")
        root, error = tool_project("chromatic_present_game", args, kwargs)
        if error or root is None:  # narrows root to str for pyright: tool_project gives one or the other
            return error or tool_error("chromatic_present_game: no project folder.", "NO_PROJECT")
        registry = host._registry()
        entry = registry.get(library.game_id(root))
        fresh, why, next_step = library.export_freshness(
            Path(root), entry.get("lastBuild") if entry else None, entry.get("lastWebExport") if entry else None
        )
        if not fresh:
            return tool_error(why or "The playable copy is not this build.", "BUILD_FIRST", next_step)
        unfinished, why = pipeline.override(args.get(pipeline.OVERRIDE))
        if why:
            return tool_error(why, "INVALID_ARGUMENTS")
        held = pipeline.gate("chromatic_present_game", Path(root), (entry or {}).get("lastBuild"))
        if held and not unfinished:
            return json.dumps(held)
        # Every game reaches the user in the game layout, with its card: cover art, title, tagline, description,
        # genres.
        try:
            layout.ensure(Path(root))
        except OSError:
            pass
        problems = layout.check(Path(root))["problems"]
        if problems:
            return tool_error(
                "The game folder is not in the game layout: " + " ".join(item["message"] for item in problems),
                "LAYOUT",
                "Restore what is missing (the game's .gbsproj, its project/ folder and a readable game.json), then "
                "call chromatic_present_game again. Never edit the id in game.json or anything in .hermretro/.",
            )
        card = game_card.status(Path(root), strict=True)
        if not card["complete"]:
            return json.dumps(
                {
                    "ok": False,
                    "code": "GAME_INFO_INCOMPLETE",
                    "error": "The game card is not finished, so the game is not shown yet. Missing: "
                    + ", ".join(card["missing"])
                    + ".",
                    "missing": card["missing"],
                    "problems": card["problems"],
                    "nextStep": game_card.next_step(card["missing"]) + " Then call chromatic_present_game again.",
                }
            )
        chat = None
        if conversation_id:
            chat = {
                "conversationId": conversation_id,
                "sessionId": session_id or conversation_id,
                "profile": host._profile_identity(),
            }
        presented = registry.present(root, chat=chat, note=note)
        if presented is None:
            return tool_error(f"{root} is not an existing project folder.", "PROJECT_NOT_FOUND")
        record = presented["presentation"]
        emit("library.game_presented", game=record["gameId"], root=root)
        url = player_server.get_server(host._game_root).url(record["gameId"])
        return json.dumps(
            {
                "ok": True,
                "studio": {
                    "gameId": record["gameId"],
                    "playerUrl": url,
                    "title": record["title"],
                    "note": record["note"],
                    "presentedAt": record["t"],
                    # Presented by the game's own Build conversation: the Build page plays it, nothing opens beside.
                    "buildConversation": (host._bound_game(conversation_id, session_id) or {}).get("id")
                    == record["gameId"],
                },
                "message": "Shown to the user beside the chat.",
                **({"unfinished": {"request": unfinished, "notVerified": held["error"]}} if held else {}),
            }
        )
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_present_game failed")
        return tool_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


# -- plugin-owned tool: the game card (game.json + cover.png) ------------------------------

COVER_RULES = (
    f"The cover is pixel art you draw yourself in the game's own palette (see hermretro:pixel-art), never Image "
    f"Generation and never an unchanged copy of an image under assets/: exactly {game_card.COVER_WIDTH}x"
    f"{game_card.COVER_HEIGHT}, every pixel opaque, {game_card.MIN_COVER_COLOURS} to {game_card.MAX_COVER_COLOURS} "
    f"colours, a plain 8-bit or palette PNG (not interlaced) of at most {game_card.MAX_COVER_BYTES // 1024} KB."
)

GAME_INFO_TOOL = {
    "name": "chromatic_game_info",
    "description": (
        "Read or fill in the game card that the hermretro Games page shows and chromatic_present_game requires: "
        "game.json (title, tagline, description, about, genres, tags, controls) and cover.png at the project root. "
        "Call it with no fields to see what is missing. Required to present: title, tagline, description, 1 to "
        f"{game_card.MAX_GENRES} genres and a cover; no placeholder words (TODO, TBD, lorem ipsum, coming soon). "
        "The cover's rules are on the cover field; pass the path of its PNG and it is copied into the project. A call with any invalid field changes nothing "
        "and lists the problems. Never touches game sources or a device."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "minLength": game_card.LIMITS["title"][0],
                "maxLength": game_card.LIMITS["title"][1],
                "description": "The game's name as players see it.",
            },
            "tagline": {
                "type": "string",
                "minLength": game_card.LIMITS["tagline"][0],
                "maxLength": game_card.LIMITS["tagline"][1],
                "description": f"{game_card.LIMITS['tagline'][0]} to {game_card.LIMITS['tagline'][1]} characters: one "
                "line that sells the game, e.g. 'Walk a tabby through a sunny meadow.'",
            },
            "description": {
                "type": "string",
                "minLength": game_card.LIMITS["description"][0],
                "maxLength": game_card.LIMITS["description"][1],
                "description": f"{game_card.LIMITS['description'][0]} to "
                f"{game_card.LIMITS['description'][1]} characters: what the game is "
                "and what you do in it.",
            },
            "about": {
                "type": "string",
                "maxLength": game_card.LIMITS["about"][1],
                "description": "Optional longer notes: story, how to play, tips.",
            },
            "genres": {
                "type": "array",
                "maxItems": game_card.MAX_GENRES,
                "items": {"type": "string", "enum": list(game_card.GENRES)},
                "description": f"1 to {game_card.MAX_GENRES} genres (at least one to present).",
            },
            "tags": {
                "type": "array",
                "maxItems": game_card.MAX_TAGS,
                "items": {"type": "string", "maxLength": game_card.MAX_TAG_CHARS},
                "description": "Optional short free-form tags, e.g. 'cozy', 'animals'.",
            },
            "controls": {
                "type": "object",
                "maxProperties": game_card.MAX_CONTROLS,
                "additionalProperties": {"type": "string", "maxLength": game_card.MAX_CONTROL_CHARS},
                "description": "Optional button to action, e.g. {\"D-pad\": \"walk\", \"A\": \"pounce\"}.",
            },
            "cover": {
                "type": "string",
                "maxLength": 4096,
                "description": "Path of the cover PNG you drew (absolute, or relative to the project). " + COVER_RULES,
            },
            "project": {
                "type": "string",
                "maxLength": 4096,
                "description": "Optional absolute project folder. Default: this chat's current project.",
            },
        },
        "additionalProperties": False,
    },
}

_CARD_FIELDS = ("title", "tagline", "description", "about", "genres", "tags", "controls")


def game_info_handler(args: dict, **kwargs) -> str:
    """``chromatic_game_info``: check and store the game card. Files only: no engine call, no device."""
    try:
        args = args if isinstance(args, dict) else {}
        if host._is_child(str(kwargs.get("session_id") or "")):
            return tool_error("Only the main conversation can change the game card.", "PARENT_ONLY")
        root, error = tool_project("chromatic_game_info", args, kwargs)
        if error or root is None:  # narrows root to str for pyright: tool_project gives one or the other
            return error or tool_error("chromatic_game_info: no project folder.", "NO_PROJECT")
        path = Path(root)
        title = library.project_title(path)
        game_card.scaffold(path, title)
        fields = {key: args[key] for key in _CARD_FIELDS if key in args}
        cover = args.get("cover")
        if cover is not None and (not isinstance(cover, str) or not cover.strip()):
            return tool_error("cover must be the path of a PNG.", "INVALID_ARGUMENTS")
        if fields or cover:
            entry = host._registry().get(library.game_id(root)) or {}
            build = entry.get("lastBuild") if isinstance(entry.get("lastBuild"), dict) else {}
            result = game_card.update(
                path, fields, cover_source=cover, build_sha=build.get("sha256"), default_title=title
            )
            if not result["ok"]:
                return json.dumps(
                    {
                        "ok": False,
                        "code": "INVALID_GAME_INFO",
                        "problems": result["problems"],
                        "error": "Nothing was changed. " + " ".join(result["problems"]),
                        "nextStep": "Fix every listed problem and call chromatic_game_info again with all the fields "
                        "you meant to set: it stores all of them or none.",
                    }
                )
            state = result["status"]
            try:
                layout.ensure(path)  # the README follows the card
            except OSError:
                pass
        else:
            state = game_card.status(path, strict=True)
        card = game_card.public(path) or {}
        card.pop("missing", None)
        return json.dumps(
            {
                "ok": True,
                "card": card,
                "file": str(game_card.card_path(path)),
                "complete": state["complete"],
                "missing": state["missing"],
                "problems": state["problems"],
                "nextStep": "The game card is complete; you can present the game with chromatic_present_game."
                if state["complete"]
                else game_card.next_step(state["missing"]),
            }
        )
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_game_info failed")
        return tool_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


TOOLS = (
    Tool(PRESENT_TOOL, present_game_handler, step_words=("Handing you the game", "Handed you the game")),
    Tool(GAME_INFO_TOOL, game_info_handler, step_words=("Writing the game card", "Wrote the game card")),
    *playtest_tools.TOOLS,
    *report_tools.TOOLS,
)
