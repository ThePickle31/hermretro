"""The library's plugin-owned tools (named on the Tools line of backend/library/README.md), with their schemas and
handlers. Declared in TOOLS at the end (backend/hermes/declare.py)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .. import player as player_server
from ..hermes import host
from ..hermes.declare import Tool
from ..system.events import emit
from . import game_card, games as library
from .tool_args import _present_error, _tool_project  # shared by every tool module (re-exported here)

logger = host.logger  # one logger for the Hermes side of the backend

# Shared helpers (the data folder, the profile, the library, the broker client) stay in backend.hermes.host and are
# looked up there at call time, so one patch of host.<name> reaches every module.


# -- plugin-owned tool: show the finished game to the user -------------------------

PRESENT_TOOL = {
    "name": "chromatic_present_game",
    "description": (
        "Show the game to the user in the hermretro emulator beside the chat (ModRetro's player, served "
        "by the plugin). Call it once the game is built and ready for the user to try, and again after later "
        "changes the user should test; each call loads the newest build there. Nothing opens by itself after a "
        "build. Needs a fresh playable copy (run chromatic_rom_build first) and a complete game card (cover art, "
        "title, tagline, description, genres; set them with chromatic_game_info). Never touches a device. Do not open "
        "the game with desktop_preview instead; only if the user says they cannot see the emulator, open the "
        "returned studio.playerUrl with desktop_preview."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "maxLength": library.MAX_NOTE_CHARS,
                "description": "Optional short line shown to the user above the player, e.g. what to try.",
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
            return _present_error("Only the main conversation can show the game to the user.", "PARENT_ONLY")
        note = args.get("note")
        if note is not None and not isinstance(note, str):
            return _present_error("note must be a string.", "INVALID_ARGUMENTS")
        project = args.get("project")
        if project is not None and (not isinstance(project, str) or not project.strip()):
            return _present_error("project must be an absolute folder path.", "INVALID_ARGUMENTS")
        if project:
            candidate = Path(project).expanduser()
            if not candidate.is_absolute() or not candidate.is_dir():
                return _present_error(
                    f"{project} is not an existing project folder (give an absolute path).", "PROJECT_NOT_FOUND"
                )
            root = str(candidate)
        else:
            root = host._chat_project(conversation_id, session_id)
        if not root or not Path(root).is_dir():
            return _present_error(
                "This chat has no current project. Select or create the game's project, build it with "
                "chromatic_rom_build, then call chromatic_present_game again (or pass project).",
                "NO_PROJECT",
            )
        registry = host._registry()
        entry = registry.get(library.game_id(root))
        fresh, why = library.export_freshness(
            Path(root), entry.get("lastBuild") if entry else None, entry.get("lastWebExport") if entry else None
        )
        if not fresh:
            return json.dumps(
                {
                    "ok": False,
                    "error": why,
                    "code": "BUILD_FIRST",
                    "guidance": "Run chromatic_rom_build for this project, then call chromatic_present_game again.",
                }
            )
        # Every game reaches the user with its card: cover art, title, tagline, description, genres.
        try:
            game_card.scaffold(Path(root), library.project_title(Path(root)))
        except OSError:
            pass
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
                    "guidance": game_card.next_step(card["missing"]) + " Then call chromatic_present_game again.",
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
            return _present_error(f"{root} is not an existing project folder.", "PROJECT_NOT_FOUND")
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
                },
                "message": "Shown to the user beside the chat.",
            }
        )
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_present_game failed")
        return _present_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


# -- plugin-owned tool: the game card (game.json + cover.png) ------------------------------

GAME_INFO_TOOL = {
    "name": "chromatic_game_info",
    "description": (
        "Read or fill in the game card that the hermretro Games page shows and chromatic_present_game requires: "
        "game.json (title, tagline, description, about, genres, tags, controls) and cover.png at the project root. "
        "Call it with no fields to see what is missing. The cover must be pixel art you draw yourself: exactly "
        f"{game_card.COVER_WIDTH}x{game_card.COVER_HEIGHT}, opaque, at most {game_card.MAX_COVER_COLOURS} colours, "
        "in the game's own palette, never Image Generation (see hermretro:pixel-art); pass the path of its PNG and it is copied "
        "into the project. A call with any invalid field changes nothing and lists the problems. Never touches "
        "game sources or a device."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "maxLength": game_card.LIMITS["title"][1],
                "description": "The game's name as players see it.",
            },
            "tagline": {
                "type": "string",
                "maxLength": game_card.LIMITS["tagline"][1],
                "description": "One line that sells the game, e.g. 'Walk a tabby through a sunny meadow.'",
            },
            "description": {
                "type": "string",
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
                "description": f"1 to {game_card.MAX_GENRES} genres.",
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
                "description": "Path of the cover PNG you drew (absolute, or relative to the project).",
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
            return _present_error("Only the main conversation can change the game card.", "PARENT_ONLY")
        root, error = _tool_project("chromatic_game_info", args, kwargs)
        if error:
            return error
        path = Path(root)
        title = library.project_title(path)
        game_card.scaffold(path, title)
        fields = {key: args[key] for key in _CARD_FIELDS if key in args}
        cover = args.get("cover")
        if cover is not None and (not isinstance(cover, str) or not cover.strip()):
            return _present_error("cover must be the path of a PNG.", "INVALID_ARGUMENTS")
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
                    }
                )
            state = result["status"]
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
        return _present_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


# -- plugin-owned tool: the Build page's build card ------------------------------------------

REPORT_LIMITS = {
    "title": 48,
    "summary": 280,
    "change": 100,
    "tested": 80,
    "untested": 80,
    "notes": 160,
    "suggestions": 40,
}
REPORT_COUNTS = {"changes": 8, "tested": 6, "untested": 6, "notes": 3, "suggestions": 4}
REPORT_KINDS = ("added", "changed", "removed")
REPORT_MESSAGE = (
    "The Build page shows this as the build card. Keep your written reply to one or two short "
    "sentences; do not repeat the report."
)


def _report_list(key: str, limit: int, item_description: str, description: str) -> dict:
    return {
        "type": "array",
        "maxItems": REPORT_COUNTS[key],
        "description": description,
        "items": {"type": "string", "minLength": 1, "maxLength": limit, "description": item_description},
    }


BUILD_REPORT_TOOL = {
    "name": "chromatic_build_report",
    "description": (
        "Report what this turn did to the game, for the hermretro Build page. Call it once at the end of every "
        "turn that changed or built the game: after chromatic_rom_build and your own playtest, and after "
        "chromatic_present_game when you present. Never call it in a subagent. The page draws the title, summary, "
        "changes (with the images they made or edited), tested and untested checks, notes and suggestions as a "
        "build card, so the written reply after it should be one or two short sentences (for example a "
        "question about a note), not a recap. Reads and writes nothing in the project; never touches a device."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "minLength": 1,
                "maxLength": REPORT_LIMITS["title"],
                "description": "Short name for this build, e.g. 'Robin in the sky' or 'Chubbier robin'.",
            },
            "summary": {
                "type": "string",
                "minLength": 1,
                "maxLength": REPORT_LIMITS["summary"],
                "description": "One or two plain sentences on what the user can do now.",
            },
            "changes": {
                "type": "array",
                "maxItems": REPORT_COUNTS["changes"],
                "description": "What changed in the game this turn.",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "text"],
                    "properties": {
                        "kind": {"type": "string", "enum": list(REPORT_KINDS)},
                        "text": {"type": "string", "minLength": 1, "maxLength": REPORT_LIMITS["change"]},
                        "asset": {
                            "type": "string",
                            "maxLength": 4096,
                            "description": "Optional path (absolute or relative to the project) "
                            "of an image this change made or edited.",
                        },
                    },
                },
            },
            "tested": _report_list(
                "tested", REPORT_LIMITS["tested"], "One check.", "What you verified yourself in the emulator."
            ),
            "untested": _report_list(
                "untested",
                REPORT_LIMITS["untested"],
                "One check.",
                "What you did not check (sound, edge cases, the real Chromatic...).",
            ),
            "notes": _report_list("notes", REPORT_LIMITS["notes"], "One note.", "Things the user might notice."),
            "suggestions": _report_list(
                "suggestions",
                REPORT_LIMITS["suggestions"],
                "Phrased as the user's own request, e.g. 'Make it fly faster'.",
                "Next steps the user can pick.",
            ),
            "project": {
                "type": "string",
                "maxLength": 4096,
                "description": "Optional absolute project folder. Default: this chat's current project.",
            },
        },
        "required": ["title", "summary"],
        "additionalProperties": False,
    },
}


def _report_text(value, name: str, limit: int, problems: list) -> str | None:
    if not isinstance(value, str):
        problems.append(f"{name} must be a string.")
        return None
    text = " ".join(value.split())
    if not text:
        problems.append(f"{name} is empty.")
        return None
    if len(text) > limit:
        problems.append(f"{name} is {len(text)} characters; at most {limit}.")
        return None
    return text


def _report_asset(raw: str, root: Path | None) -> tuple[str | None, str | None]:
    """An absolute path for a change's image inside the project, or (None, why it was left out)."""
    text = raw.strip()
    if text.startswith("file://"):
        text = text[len("file://") :]
    candidate = Path(text).expanduser()
    if root is None:
        if not candidate.is_absolute():
            return None, f"{raw}: a relative path needs the game's project"
        return os.path.normpath(str(candidate)), None
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        real = candidate.resolve()
        base = root.resolve()
    except (OSError, RuntimeError):
        return None, f"{raw}: not a usable path"
    if real != base and base not in real.parents:
        return None, f"{raw}: outside the project"
    if not real.is_file():
        return None, f"{raw}: no such file in the project"
    return str(real), None


def build_report_handler(args: dict, **kwargs) -> str:
    """``chromatic_build_report``: check the turn's build card and hand it back for the Build page.
    Stores nothing; the page reads it from the tool call."""
    try:
        args = args if isinstance(args, dict) else {}
        if host._is_child(str(kwargs.get("session_id") or "")):
            return _present_error("Only the main conversation reports a build.", "PARENT_ONLY")
        problems: list[str] = []
        known = set(BUILD_REPORT_TOOL["parameters"]["properties"])
        problems += [f"Unknown field {key!r}." for key in sorted(set(args) - known)]
        root = None
        project = args.get("project")
        if project is not None:
            if (
                not isinstance(project, str)
                or not project.strip()
                or not Path(project).expanduser().is_absolute()
                or not Path(project).expanduser().is_dir()
            ):
                problems.append("project must be an absolute path of an existing project folder.")
            else:
                root = Path(project).expanduser()
        else:
            try:
                found = host._chat_project(
                    str(kwargs.get("conversation_id") or ""), str(kwargs.get("session_id") or "")
                )
            except Exception:
                logger.debug("hermretro: no project for the build report", exc_info=True)
                found = None
            root = Path(found) if found and Path(found).is_dir() else None
        report: dict = {}
        for key in ("title", "summary"):
            if key not in args:
                problems.append(f"{key} is required.")
            else:
                report[key] = _report_text(args[key], key, REPORT_LIMITS[key], problems)
        warnings: list[str] = []
        changes = args.get("changes", [])
        report["changes"] = []
        if not isinstance(changes, list):
            problems.append("changes must be a list.")
        elif len(changes) > REPORT_COUNTS["changes"]:
            problems.append(f"changes has {len(changes)} items; at most {REPORT_COUNTS['changes']}.")
        else:
            for index, change in enumerate(changes, 1):
                where = f"changes[{index}]"
                if not isinstance(change, dict):
                    problems.append(f"{where} must be an object with kind and text.")
                    continue
                problems += [
                    f"{where} has unknown field {key!r}." for key in sorted(set(change) - {"kind", "text", "asset"})
                ]
                if change.get("kind") not in REPORT_KINDS:
                    problems.append(f"{where}.kind must be one of {', '.join(REPORT_KINDS)}.")
                item = {
                    "kind": change.get("kind"),
                    "text": _report_text(change.get("text"), f"{where}.text", REPORT_LIMITS["change"], problems),
                }
                asset = change.get("asset")
                if asset is not None:
                    if not isinstance(asset, str) or not asset.strip() or len(asset) > 4096:
                        problems.append(f"{where}.asset must be a file path.")
                    else:
                        resolved, why = _report_asset(asset, root)
                        if resolved:
                            item["asset"] = resolved
                        else:
                            warnings.append(f"{where}.asset left out ({why}).")
                report["changes"].append(item)
        for key in ("tested", "untested", "notes", "suggestions"):
            values = args.get(key, [])
            report[key] = []
            if not isinstance(values, list):
                problems.append(f"{key} must be a list of strings.")
            elif len(values) > REPORT_COUNTS[key]:
                problems.append(f"{key} has {len(values)} items; at most {REPORT_COUNTS[key]}.")
            else:
                report[key] = [
                    _report_text(value, f"{key}[{index}]", REPORT_LIMITS[key], problems)
                    for index, value in enumerate(values, 1)
                ]
        if problems:
            return json.dumps(
                {
                    "ok": False,
                    "code": "INVALID_REPORT",
                    "problems": problems,
                    "error": "The build report was not shown. " + " ".join(problems),
                }
            )
        # The card shows each image as it is now, even after a later turn rewrites it (assets listens).
        emit(
            "library.build_reported",
            game=library.game_id(root) if root else None,
            assets=[change["asset"] for change in report["changes"] if change.get("asset")],
        )
        answer = {"ok": True, "report": report, "project": str(root) if root else None, "message": REPORT_MESSAGE}
        if warnings:
            answer["warnings"] = warnings
        return json.dumps(answer)
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_build_report failed")
        return _present_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


TOOLS = (
    Tool(PRESENT_TOOL, present_game_handler, step_words=("Handing you the game", "Handed you the game")),
    Tool(GAME_INFO_TOOL, game_info_handler, step_words=("Writing the game card", "Wrote the game card")),
    Tool(BUILD_REPORT_TOOL, build_report_handler, step_words=None),  # drawn as the turn's build card instead
)
