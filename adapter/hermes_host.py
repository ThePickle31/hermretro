"""Everything that touches Hermes: tool handlers, RPC methods, hooks, prompt section.

Handlers run wherever Hermes dispatches tools (gateway, plugin host or an isolated
turn process). They hold no state of their own: every call goes to the broker.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path

from . import contracts, game_card, host_os, onboarding, paths, player_server, provision, results, snapshots, studio_profile
from . import games as library
from .client import BrokerUnavailable, ensure_broker, try_connect

logger = logging.getLogger(__name__)

_COMPONENT_LABELS = {
    "node": "Node.js", "runtime": "Chromatic engine", "cli": "GB Studio CLI", "gbdk": "GBDK compiler",
    "python": "Python (emulator)", "pyboy": "PyBoy emulator", "pillow": "Pillow imaging", "uv": "uv installer",
    "desktop": "GB Studio desktop editor",
}
_OPTIONAL_COMPONENTS = {"desktop"}
_APPROVAL_TOOLS = {"chromatic_flash", "chromatic_play", "chromatic_setup"}

# Runtime session ids of delegated subagents alive in this process. The subagent_start hook and
# the child's tool calls run in the same process, so this is host-observed, not model-supplied.
_child_sessions: dict[str, float] = {}
_child_lock = threading.Lock()


def _data_dir() -> Path:
    from plugins.plugin_storage import plugin_data_dir
    return plugin_data_dir(paths.PLUGIN_ID)


def _profile_identity() -> str:
    """Canonical identity of the active Hermes profile: its plugin data directory."""
    return str(_data_dir().resolve())


def _attach_images() -> bool:
    """Whether the active model route takes images inside tool results.

    Hermes has no public helper for this yet; core tools share this private gate. Any failure
    means "do not attach", and the saved files still carry the images."""
    try:
        from tools.vision_tools import _should_use_native_vision_fast_path
        return bool(_should_use_native_vision_fast_path())
    except Exception:
        return False


def _is_child(session_id: str) -> bool:
    with _child_lock:
        return bool(session_id) and session_id in _child_sessions


def on_subagent_start(child_session_id=None, **_kwargs):
    if child_session_id:
        with _child_lock:
            _child_sessions[str(child_session_id)] = time.time()
            for stale in sorted(_child_sessions, key=lambda key: _child_sessions[key])[:-512]:
                del _child_sessions[stale]


def on_subagent_stop(child_session_id=None, **_kwargs):
    if child_session_id:
        with _child_lock:
            _child_sessions.pop(str(child_session_id), None)


def _deliver(response: dict, name: str, encode=results.encode):
    """Shape a broker response for the model. By now the tool has already run, so a failure here
    (for example the frames folder cannot be written) must not read as "the tool did not run"."""
    try:
        return encode(response, name, _data_dir() / "frames", _attach_images())
    except Exception as error:
        logger.exception("Chromatic tool %s ran but its result could not be fully delivered", name)
        problem = f"{type(error).__name__}: {error}"
    try:
        plain = encode(response, name, None, False)       # the same result, without saving images
        payload = json.loads(plain) if isinstance(plain, str) else None
        if isinstance(payload, dict):
            payload["deliveryProblem"] = ("The tool ran. Its images could not be saved or attached "
                                          f"({problem}); the rest of the result is complete.")
            return json.dumps(payload)
        return plain
    except Exception:
        logger.exception("Chromatic tool %s: plain delivery failed too", name)
        if response.get("denied") or not (response.get("ok") or response.get("dispatched")):
            return json.dumps({"error": f"hermretro could not report why this call did not run ({problem}).",
                               "code": "ADAPTER_ERROR", "dispatched": False})
        return json.dumps({
            "error": f"The tool ran, but hermretro could not deliver its result ({problem}).",
            "code": "RESULT_NOT_DELIVERED", "dispatched": True,
            "guidance": "The operation was sent to the engine. Inspect current state before deciding what to "
                        "do; do not simply repeat it."})


def make_tool_handler(ctx, tool: dict):
    original = tool["name"]
    name = contracts.hermes_name(original)

    def handler(args: dict, **kwargs) -> object:
        try:
            conversation_id = str(kwargs.get("conversation_id") or "")
            session_id = str(kwargs.get("session_id") or "")
            owner = {"profile": _profile_identity(), "conversation_id": conversation_id} if conversation_id else None
            origin = {"session_id": session_id, "task_id": str(kwargs.get("task_id") or ""),
                      "delegated": _is_child(session_id)}
            policy = {"hardware_enabled": bool(ctx.get_config("hardware_enabled", False)),
                      "live_player": bool(ctx.get_config("live_player", True))}
            if original in contracts.CREATORS and isinstance(args, dict) and not args.get("destinationPath"):
                # New games live in the Studio's games folder unless the user asked for another place.
                paths.games_dir(create=True)
                args = {**args, "destinationPath": contracts.default_destination(args.get("name"))}
            with ensure_broker() as client:
                response = client.call(owner, original, args if isinstance(args, dict) else {},
                                       origin=origin, policy=policy)
            if conversation_id and session_id and session_id != conversation_id and not origin["delegated"]:
                try:  # a game's conversation keeps its game when compression rotates the session id
                    _registry().note_alias(_profile_identity(), conversation_id, session_id)
                except Exception:
                    logger.debug("hermretro: could not record the session alias", exc_info=True)
            return _deliver(response, name)
        except BrokerUnavailable as error:
            return json.dumps({"error": str(error), "code": "UNAVAILABLE", "dispatched": False,
                               "guidance": "Load the skill hermretro:setup for how to prepare this machine."})
        except Exception as error:  # a handler must never raise
            logger.exception("Chromatic tool %s failed in the host adapter", name)
            return json.dumps({"error": f"hermretro adapter error: {type(error).__name__}: {error}",
                               "code": "ADAPTER_ERROR"})

    return handler


# -- plugin-owned setup tool ------------------------------------------------------

DEVICE_CLI_TOOL = {
    "name": "chromatic_studio_device_cli",
    "description": (
        "Check or install ModRetro's official Chromatic CLI for this computer. hermretro does not ship it: "
        "'install' downloads it from ModRetro's own npm package, verifies it against pinned SHA-256 digests and "
        "places it in hermretro's folder in the Hermes home. It is needed only for hardware features (device "
        "discovery, streaming, capture, cartridge flashing); creating, building and playtesting games never use it. "
        "This tool never touches USB, drivers or a device. The CLI is proprietary ModRetro software: install only "
        "after the user has agreed to ModRetro's terms, and pass acceptVendorTerms true to record that. "
        "'status' is passive and needs no consent."),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "install"]},
            "acceptVendorTerms": {"type": "boolean",
                                  "description": "Install only: true once the user has agreed to ModRetro's terms."},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}


def device_cli_handler(args: dict, **_kwargs) -> str:
    try:
        args = args if isinstance(args, dict) else {}
        if args.get("action") == "install":
            answer = provision.install_device_cli(args.get("acceptVendorTerms") is True)
            answer["next"] = ("Hardware tools pick this up in a new chat. They also need 'Chromatic hardware tools' "
                              "turned on in Settings > Plugins > hermretro.")
            return json.dumps(answer)
        return json.dumps(provision.summary())
    except provision.ProvisionError as error:
        return json.dumps({"error": str(error), "code": error.code, "installed": False})
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_studio_device_cli failed")
        return json.dumps({"error": f"hermretro adapter error: {type(error).__name__}: {error}",
                           "code": "ADAPTER_ERROR"})


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
        "returned studio.playerUrl with desktop_preview."),
    "parameters": {
        "type": "object",
        "properties": {
            "note": {"type": "string", "maxLength": library.MAX_NOTE_CHARS,
                     "description": "Optional short line shown to the user above the player, e.g. what to try."},
            "project": {"type": "string", "maxLength": 4096,
                        "description": "Optional absolute project folder. Default: this chat's current project."},
        },
        "additionalProperties": False,
    },
}


def _chat_project(conversation_id: str, session_id: str) -> str | None:
    """The project this chat works on: its broker lane's selection (memory only, never starts the
    broker or a worker), else the library game whose chat link is this conversation."""
    ids = [value for value in (conversation_id, session_id) if value]
    if not ids:
        return None
    client, _error = try_connect(paths.runtime_dir())
    if client is not None:
        with client:
            answer = client.request({"op": "activity", "profile": _profile_identity(), "ids": ids, "limit": 1})
        root = (answer.get("lane") or {}).get("project_root") if answer.get("ok") and answer.get("matched") == "chat" \
            else None
        if isinstance(root, str) and root:
            return root
    here = _profile_identity()
    linked = [entry for entry in _registry().load()["games"].values()
              if isinstance(entry, dict) and isinstance(entry.get("chat"), dict)
              and entry["chat"].get("profile") in (None, here)
              and (entry["chat"].get("conversationId") in ids or entry["chat"].get("sessionId") in ids)]
    linked.sort(key=lambda entry: -(entry.get("updatedAt") or 0))
    return linked[0]["projectRoot"] if linked and isinstance(linked[0].get("projectRoot"), str) else None


def _present_error(message: str, code: str) -> str:
    return json.dumps({"ok": False, "error": message, "code": code})


def _tool_project(tool: str, args: dict, kwargs: dict) -> tuple[str | None, str | None]:
    """The project a plugin-owned tool acts on: ``project`` when given, else this chat's. Returns
    ``(root, None)`` or ``(None, error json)``."""
    conversation_id = str(kwargs.get("conversation_id") or "")
    session_id = str(kwargs.get("session_id") or "")
    project = args.get("project")
    if project is not None and (not isinstance(project, str) or not project.strip()):
        return None, _present_error("project must be an absolute folder path.", "INVALID_ARGUMENTS")
    if project:
        candidate = Path(project).expanduser()
        if not candidate.is_absolute() or not candidate.is_dir():
            return None, _present_error(f"{project} is not an existing project folder (give an absolute path).",
                                        "PROJECT_NOT_FOUND")
        return str(candidate), None
    root = _chat_project(conversation_id, session_id)
    if not root or not Path(root).is_dir():
        return None, _present_error(
            f"This chat has no current project. Select or create the game's project, then call {tool} again (or "
            "pass project).", "NO_PROJECT")
    return root, None


def present_game_handler(args: dict, **kwargs) -> str:
    """``chromatic_present_game``: record the presentation; the desktop opens the emulator tab when it
    sees this tool complete. Reads files and the library only: no engine call, no device."""
    try:
        args = args if isinstance(args, dict) else {}
        conversation_id = str(kwargs.get("conversation_id") or "")
        session_id = str(kwargs.get("session_id") or "")
        if _is_child(session_id):
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
                return _present_error(f"{project} is not an existing project folder (give an absolute path).",
                                      "PROJECT_NOT_FOUND")
            root = str(candidate)
        else:
            root = _chat_project(conversation_id, session_id)
        if not root or not Path(root).is_dir():
            return _present_error(
                "This chat has no current project. Select or create the game's project, build it with "
                "chromatic_rom_build, then call chromatic_present_game again (or pass project).", "NO_PROJECT")
        registry = _registry()
        entry = registry.get(library.game_id(root))
        fresh, why = library.export_freshness(Path(root), entry.get("lastBuild") if entry else None,
                                              entry.get("lastWebExport") if entry else None)
        if not fresh:
            return json.dumps({"ok": False, "error": why, "code": "BUILD_FIRST",
                               "guidance": "Run chromatic_rom_build for this project, then call "
                                           "chromatic_present_game again."})
        # Every game reaches the user with its card: cover art, title, tagline, description, genres.
        try:
            game_card.scaffold(Path(root), library.project_title(Path(root)))
        except OSError:
            pass
        card = game_card.status(Path(root), strict=True)
        if not card["complete"]:
            return json.dumps({"ok": False, "code": "GAME_INFO_INCOMPLETE",
                               "error": "The game card is not finished, so the game is not shown yet. Missing: "
                                        + ", ".join(card["missing"]) + ".",
                               "missing": card["missing"], "problems": card["problems"],
                               "guidance": game_card.next_step(card["missing"]) + " Then call "
                                                                                "chromatic_present_game again."})
        chat = None
        if conversation_id:
            chat = {"conversationId": conversation_id, "sessionId": session_id or conversation_id,
                    "profile": _profile_identity()}
        presented = registry.present(root, chat=chat, note=note)
        if presented is None:
            return _present_error(f"{root} is not an existing project folder.", "PROJECT_NOT_FOUND")
        record = presented["presentation"]
        url = player_server.get_server(_game_root).url(record["gameId"])
        return json.dumps({"ok": True,
                           "studio": {"gameId": record["gameId"], "playerUrl": url, "title": record["title"],
                                      "note": record["note"], "presentedAt": record["t"]},
                           "message": "Shown to the user beside the chat."})
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
        "game sources or a device."),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "maxLength": game_card.LIMITS["title"][1],
                      "description": "The game's name as players see it."},
            "tagline": {"type": "string", "maxLength": game_card.LIMITS["tagline"][1],
                        "description": "One line that sells the game, e.g. 'Walk a tabby through a sunny meadow.'"},
            "description": {"type": "string", "maxLength": game_card.LIMITS["description"][1],
                            "description": f"{game_card.LIMITS['description'][0]} to "
                                           f"{game_card.LIMITS['description'][1]} characters: what the game is "
                                           "and what you do in it."},
            "about": {"type": "string", "maxLength": game_card.LIMITS["about"][1],
                      "description": "Optional longer notes: story, how to play, tips."},
            "genres": {"type": "array", "maxItems": game_card.MAX_GENRES,
                       "items": {"type": "string", "enum": list(game_card.GENRES)},
                       "description": "1 to 3 genres."},
            "tags": {"type": "array", "maxItems": game_card.MAX_TAGS,
                     "items": {"type": "string", "maxLength": game_card.MAX_TAG_CHARS},
                     "description": "Optional short free-form tags, e.g. 'cozy', 'animals'."},
            "controls": {"type": "object", "additionalProperties": {"type": "string"},
                         "description": "Optional button to action, e.g. {\"D-pad\": \"walk\", \"A\": \"pounce\"}."},
            "cover": {"type": "string", "maxLength": 4096,
                      "description": "Path of the cover PNG you drew (absolute, or relative to the project)."},
            "project": {"type": "string", "maxLength": 4096,
                        "description": "Optional absolute project folder. Default: this chat's current project."},
        },
        "additionalProperties": False,
    },
}

_CARD_FIELDS = ("title", "tagline", "description", "about", "genres", "tags", "controls")


def game_info_handler(args: dict, **kwargs) -> str:
    """``chromatic_game_info``: check and store the game card. Files only: no engine call, no device."""
    try:
        args = args if isinstance(args, dict) else {}
        if _is_child(str(kwargs.get("session_id") or "")):
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
            entry = _registry().get(library.game_id(root)) or {}
            build = entry.get("lastBuild") if isinstance(entry.get("lastBuild"), dict) else {}
            result = game_card.update(path, fields, cover_source=cover, build_sha=build.get("sha256"),
                                      default_title=title)
            if not result["ok"]:
                return json.dumps({"ok": False, "code": "INVALID_GAME_INFO", "problems": result["problems"],
                                   "error": "Nothing was changed. " + " ".join(result["problems"])})
            state = result["status"]
        else:
            state = game_card.status(path, strict=True)
        card = game_card.public(path) or {}
        card.pop("missing", None)
        return json.dumps({
            "ok": True, "card": card, "file": str(game_card.card_path(path)), "complete": state["complete"],
            "missing": state["missing"], "problems": state["problems"],
            "nextStep": "The game card is complete; you can present the game with chromatic_present_game."
            if state["complete"] else game_card.next_step(state["missing"])})
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_game_info failed")
        return _present_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


# -- plugin-owned tool: the Build page's build card ------------------------------------------

REPORT_LIMITS = {"title": 48, "summary": 280, "change": 100, "tested": 80, "untested": 80, "notes": 160,
                 "suggestions": 40}
REPORT_COUNTS = {"changes": 8, "tested": 6, "untested": 6, "notes": 3, "suggestions": 4}
REPORT_KINDS = ("added", "changed", "removed")
BUILD_REPORT_GUIDANCE = (
    "At the end of a turn that changed or built the game (after building, your own playtest and presenting), "
    "call chromatic_build_report once (title, summary, changes with asset paths, tested/untested, notes, up to 4 "
    "suggestions), then keep the written reply to one or two short sentences.")
REPORT_MESSAGE = ("The Build page shows this as the build card. Keep your written reply to one or two short "
                  "sentences; do not repeat the report.")


def _report_list(key: str, limit: int, item_description: str, description: str) -> dict:
    return {"type": "array", "maxItems": REPORT_COUNTS[key], "description": description,
            "items": {"type": "string", "minLength": 1, "maxLength": limit, "description": item_description}}


BUILD_REPORT_TOOL = {
    "name": "chromatic_build_report",
    "description": (
        "Report what this turn did to the game, for the hermretro Build page. Call it once at the end of every "
        "turn that changed or built the game: after chromatic_rom_build and your own playtest, and after "
        "chromatic_present_game when you present. Never call it in a subagent. The page draws the title, summary, "
        "changes (with the images they made or edited), tested and untested checks, notes and suggestions as a "
        "build card, so the written reply after it should be one or two short sentences (for example a "
        "question about a note), not a recap. Reads and writes nothing in the project; never touches a device."),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": REPORT_LIMITS["title"],
                      "description": "Short name for this build, e.g. 'Robin in the sky' or 'Chubbier robin'."},
            "summary": {"type": "string", "minLength": 1, "maxLength": REPORT_LIMITS["summary"],
                        "description": "One or two plain sentences on what the user can do now."},
            "changes": {
                "type": "array", "maxItems": REPORT_COUNTS["changes"],
                "description": "What changed in the game this turn.",
                "items": {"type": "object", "additionalProperties": False, "required": ["kind", "text"],
                          "properties": {
                              "kind": {"type": "string", "enum": list(REPORT_KINDS)},
                              "text": {"type": "string", "minLength": 1, "maxLength": REPORT_LIMITS["change"]},
                              "asset": {"type": "string", "maxLength": 4096,
                                        "description": "Optional path (absolute or relative to the project) "
                                                       "of an image this change made or edited."}}}},
            "tested": _report_list("tested", REPORT_LIMITS["tested"], "One check.",
                                   "What you verified yourself in the emulator."),
            "untested": _report_list("untested", REPORT_LIMITS["untested"], "One check.",
                                     "What you did not check (sound, edge cases, the real Chromatic...)."),
            "notes": _report_list("notes", REPORT_LIMITS["notes"], "One note.",
                                  "Things the user might notice."),
            "suggestions": _report_list("suggestions", REPORT_LIMITS["suggestions"],
                                        "Phrased as the user's own request, e.g. 'Make it fly faster'.",
                                        "Next steps the user can pick."),
            "project": {"type": "string", "maxLength": 4096,
                        "description": "Optional absolute project folder. Default: this chat's current project."},
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
        text = text[len("file://"):]
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
        if _is_child(str(kwargs.get("session_id") or "")):
            return _present_error("Only the main conversation reports a build.", "PARENT_ONLY")
        problems: list[str] = []
        known = set(BUILD_REPORT_TOOL["parameters"]["properties"])
        problems += [f"Unknown field {key!r}." for key in sorted(set(args) - known)]
        root = None
        project = args.get("project")
        if project is not None:
            if not isinstance(project, str) or not project.strip() or not Path(project).expanduser().is_absolute() \
                    or not Path(project).expanduser().is_dir():
                problems.append("project must be an absolute path of an existing project folder.")
            else:
                root = Path(project).expanduser()
        else:
            try:
                found = _chat_project(str(kwargs.get("conversation_id") or ""), str(kwargs.get("session_id") or ""))
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
                problems += [f"{where} has unknown field {key!r}." for key in sorted(set(change) - {"kind", "text", "asset"})]
                if change.get("kind") not in REPORT_KINDS:
                    problems.append(f"{where}.kind must be one of {', '.join(REPORT_KINDS)}.")
                item = {"kind": change.get("kind"),
                        "text": _report_text(change.get("text"), f"{where}.text", REPORT_LIMITS["change"], problems)}
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
                report[key] = [_report_text(value, f"{key}[{index}]", REPORT_LIMITS[key], problems)
                               for index, value in enumerate(values, 1)]
        if problems:
            return json.dumps({"ok": False, "code": "INVALID_REPORT", "problems": problems,
                               "error": "The build report was not shown. " + " ".join(problems)})
        # The card shows each image as it is now, even after a later turn rewrites it.
        _keep_paths(change.get("asset") for change in report["changes"])
        answer = {"ok": True, "report": report, "project": str(root) if root else None, "message": REPORT_MESSAGE}
        if warnings:
            answer["warnings"] = warnings
        return json.dumps(answer)
    except Exception as error:  # a handler must never raise
        logger.exception("chromatic_build_report failed")
        return _present_error(f"hermretro adapter error: {type(error).__name__}: {error}", "ADAPTER_ERROR")


# -- desktop RPC -----------------------------------------------------------------

def _platform_report() -> dict:
    found = host_os.describe()
    reported = provision._node_platform()   # cached per Node executable
    node_arch = reported[1] if reported else None
    return {**found, "node_arch": node_arch,
            "qualified": found["supported"] and not found["rosetta"] and found["machine"] in ("arm64", "x64")
            and node_arch in (None, found["machine"])}


def _games_dir_made():
    """The games folder, created so "Open games folder" opens it on a fresh install (a reveal of a missing
    folder does nothing). A folder that cannot be made is still named."""
    try:
        return paths.games_dir(create=True)
    except OSError:
        return paths.games_dir()


# The adapter code this gateway process loaded. When the files on disk change (a plugin update), the running
# Hermes keeps the old code until it restarts: the page says so.
LOADED_FINGERPRINT = paths.code_fingerprint()


def rpc_status(ctx):
    def status(params, *, session_id=None, **_kwargs):
        try:
            node = paths.find_node()
            answer = {
                "ok": True,
                "plugin": {"id": paths.PLUGIN_ID, "version": paths.PLUGIN_VERSION},
                # Linux and macOS on arm64 or x64 are supported alike; Rosetta works but is slow.
                "platform": _platform_report(),
                "node": {"found": node["found"], "version": node["version"], "required": node["required"],
                         "ok": node["ok"]},
                "engine": paths.verify_engine(),
                "deps": provision.summary(),
                "hardware_enabled": bool(ctx.get_config("hardware_enabled", False)),
                "broker": {"running": False},
                "project": None,
                "profile": studio_profile.describe(_data_dir().parents[1]),
                "restart_needed": paths.code_fingerprint() != LOADED_FINGERPRINT,
            }
            client, _error = try_connect(paths.runtime_dir())  # never starts the broker
            if client is not None:
                with client:
                    answer["broker"]["running"] = True
                    # The page names the focused chat as "chat": a "session_id" parameter would make the
                    # gateway authorize it as a live session and fail the call for a draft chat.
                    wanted = (params or {}).get("chat") or session_id or (params or {}).get("session_id")
                    lane = client.request({"op": "lane_status", "profile": _profile_identity(),
                                           "session_id": wanted}).get("lane")
                    if lane and lane.get("selected_root"):
                        answer["project"] = {"root": lane["selected_root"], "name": Path(lane["selected_root"]).name,
                                             "emulator_active": bool(lane.get("emulator_active")),
                                             "writer": bool(lane.get("writer"))}
            return answer
        except Exception as error:
            logger.exception("hermretro status failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return status


def rpc_install(ctx):
    """The page's own toolchain install: ``{"action": "status"}`` (passive, never starts the broker)
    or ``{"action": "start"}``. Always returns the download list, so the page can show it first."""
    def install(params, **_kwargs):
        try:
            action = (params or {}).get("action") or "status"
            answer = {"ok": True, "manifest": onboarding.manifest(), "root": str(paths.setup_root()),
                      "install": {"state": "idle"}}
            if action == "start":
                with ensure_broker() as client:
                    reply = client.request({"op": "install_start"})
            elif action == "status":
                client, _error = try_connect(paths.runtime_dir())
                if client is None:
                    return answer
                with client:
                    reply = client.request({"op": "install_status"})
            else:
                return {"ok": False, "error": f"Unknown action {action!r}."}
            if not reply.get("ok"):
                denied = reply.get("denied") or {}
                if denied.get("code") == "UNKNOWN_OP":
                    # An older broker kept alive by a running game; it retires once that game is closed.
                    return {**answer, "ok": False, "code": "BROKER_OUTDATED",
                            "error": "hermretro is still running an older session for a game in a chat. Close "
                                     "that game's chat (or wait a few minutes), then try again."}
                return {**answer, "ok": False, "code": denied.get("code"),
                        "error": denied.get("message") or reply.get("error") or "The install could not start."}
            answer["install"] = reply.get("install") or {"state": "idle"}
            return answer
        except BrokerUnavailable as error:
            return {"ok": False, "code": "UNAVAILABLE", "error": str(error)}
        except Exception as error:
            logger.exception("hermretro install failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return install


def rpc_remove_tools(ctx):
    """Delete the downloaded tools (Setup's "Remove downloaded tools"). Stops an idle broker first; refused while
    a game's chat has a live worker or an install runs. Games and the library are not touched."""
    def remove(params, **_kwargs):
        try:
            run = paths.runtime_dir()
            client, _error = try_connect(run)   # never starts the broker
            if client is not None:
                with client:
                    reply = client.request({"op": "shutdown"})
                if not reply.get("ok"):
                    return {"ok": False, "code": "BUSY", "error": _REMOVE_BUSY}
            # The broker's election lock: held by a running broker until it exits, and while we hold it any
            # broker another call starts loses the election and exits, so nothing runs from the folder.
            with _broker_lock(run) as held:
                if not held:
                    return {"ok": False, "code": "BUSY", "error": _REMOVE_BUSY}
                return provision.remove_downloads()
        except provision.ProvisionError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro remove_tools failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return remove


BROKER_STOP_WAIT = 15.0  # seconds a stopping broker gets to close its workers
_REMOVE_BUSY = ("A game is open in a chat or an install is running. Close those chats (or wait for the install), "
                "then try again.")


@contextlib.contextmanager
def _broker_lock(run: Path, seconds: float | None = None):
    """Hold the broker election lock, waiting for a stopping broker to let go of it. Yields False on timeout."""
    import fcntl
    with open(run / "broker.lock", "a+") as handle:
        deadline = time.monotonic() + (BROKER_STOP_WAIT if seconds is None else seconds)
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    yield False
                    return
                time.sleep(0.1)
        try:
            time.sleep(0.5)  # workers exit when the broker's pipe closes; give them a moment
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def rpc_studio_profile(ctx):
    """Finish the dedicated profile after the page has created it with Hermes's profiles.create."""
    def finish(params, **_kwargs):
        try:
            return studio_profile.finish(_data_dir().parents[1])
        except studio_profile.StudioProfileError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro studio profile setup failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return finish


def rpc_activity(ctx):
    """Live development view for one chat: project, last build, the latest emulator frame and a
    short log. Read from the broker's memory; never starts the broker or a worker."""
    def activity(params, *, session_id=None, **_kwargs):
        try:
            params = params or {}
            ids = [value for value in (params.get("chat"), params.get("stored"), session_id) if value]
            client, _error = try_connect(paths.runtime_dir())
            if client is None:
                return {"ok": True, "lane": None, "matched": None, "running": False}
            with client:
                answer = client.request({"op": "activity", "profile": _profile_identity(), "ids": ids,
                                         "limit": params.get("limit")})
            if not answer.get("ok"):
                return {"ok": False, "error": (answer.get("denied") or {}).get("message") or answer.get("error")}
            frame = answer.get("frame")
            if frame:
                answer["frame"] = {"t": frame["t"], "tool": frame["tool"], "frame": frame.get("frame"),
                                   "src": f"data:{frame['mimeType']};base64,{frame['data']}"}
            answer["running"] = True
            return answer
        except Exception as error:
            logger.exception("hermretro activity failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return activity


def rpc_doctor(ctx):
    def doctor(params, *, session_id=None, **_kwargs):
        try:
            with ensure_broker() as client:
                answer = client.request({"op": "doctor", "probe": bool((params or {}).get("probe"))})
            if not answer.get("ok"):
                return {"ok": False, "error": (answer.get("denied") or {}).get("message") or answer.get("error")}
            data = (answer["result"].get("structuredContent") or {})
            components = []
            for item in data.get("components") or []:
                components.append({
                    "id": item.get("id"), "label": _COMPONENT_LABELS.get(item.get("id"), item.get("id")),
                    "status": item.get("status") if item.get("status") in ("ready", "missing", "incompatible") else "unknown",
                    "required": item.get("requiredVersion"), "detected": item.get("detectedVersion"),
                    "optional": item.get("id") in _OPTIONAL_COMPONENTS,
                    "probe": item.get("probeStatus"),
                    # An optional part that is simply absent needs no diagnostics on the page.
                    "detail": "" if item.get("status") == "ready"
                    or (item.get("id") in _OPTIONAL_COMPONENTS and item.get("status") == "missing")
                    else "; ".join(item.get("detectionEvidence") or [])[:300],
                })
            ready = {task: bool(info.get("ready")) for task, info in (data.get("tasks") or {}).items()}
            return {"ok": True, "ready": ready, "components": components,
                    "missing_required": [c["id"] for c in components if c["status"] != "ready" and not c["optional"]],
                    "setup_root": (data.get("roots") or {}).get("setupRoot")}
        except BrokerUnavailable as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro doctor failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return doctor


# -- games library and the real player (desktop Games and Emulator pages) ----------------

def _registry() -> library.Registry:
    return library.Registry(paths.library_dir())


def _game_root(identifier) -> Path | None:
    entry = _registry().get(identifier) if library.valid_id(identifier) else None
    root = Path(entry["projectRoot"]) if entry else None
    return root if root is not None and root.is_dir() else None


def _profile_name(identity) -> str | None:
    """Profile name from a profile identity (its plugin data directory)."""
    try:
        home = Path(identity).parents[1]
    except (TypeError, IndexError):
        return None
    return home.name if home.parent.name == "profiles" else "default"


def _chat_titles(ids: set[str]) -> dict[str, str]:
    """Titles of this profile's chats, read-only from its session database. Best effort."""
    if not ids:
        return {}
    try:
        import sqlite3
        database = _data_dir().parents[1] / "state.db"
        if not database.is_file():
            return {}
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=1.0)
        try:
            marks = ",".join("?" * len(ids))
            rows = connection.execute(f"SELECT id, title FROM sessions WHERE id IN ({marks})", sorted(ids)).fetchall()
        finally:
            connection.close()
        return {row[0]: row[1] for row in rows if row[1]}
    except Exception:
        return {}


def _existing_sessions(ids: set[str]) -> set[str] | None:
    """Which of these session ids have a row in this profile's session database; None if unreadable."""
    if not ids:
        return set()
    try:
        import sqlite3
        database = _data_dir().parents[1] / "state.db"
        if not database.is_file():
            return None
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=1.0)
        try:
            marks = ",".join("?" * len(ids))
            rows = connection.execute(f"SELECT id FROM sessions WHERE id IN ({marks})", sorted(ids)).fetchall()
        finally:
            connection.close()
        return {row[0] for row in rows}
    except Exception:
        return None


def _seed_library(registry: library.Registry) -> None:
    """Add projects the running broker has selected but the library has not seen (for example work
    done before the library existed). Never starts the broker."""
    client, _error = try_connect(paths.runtime_dir())
    if client is None:
        return
    with client:
        answer = client.request({"op": "stats"})
    for lane in answer.get("lanes") or [] if answer.get("ok") else []:
        root = lane.get("selected_root")
        if isinstance(root, str) and root:
            seen = [s for s in lane.get("sessions_seen") or [] if isinstance(s, str)]
            registry.upsert(root, chat={"sessionId": seen[-1]} if seen else None, only_if_missing=True)


def _demo_entry() -> dict:
    return dict(player_server.DEMO)


def _capture_root(identifier) -> Path | None:
    """Where a game's captures live: its project, or the library folder for the demo cartridge."""
    return player_server.demo_captures_root() if player_server.is_demo(identifier) else _game_root(identifier)


def rpc_games(ctx):
    def games(params, **_kwargs):
        try:
            registry = _registry()
            try:
                _seed_library(registry)
            except Exception:
                logger.debug("hermretro: seeding the library from the broker failed", exc_info=True)
            listed = registry.library()
            here = _profile_identity()
            wanted = {value for g in listed if g.get("chat")
                      for value in (g["chat"].get("sessionId"), g["chat"].get("conversationId"))
                      if isinstance(value, str) and value}
            titles = _chat_titles(wanted)
            pending = registry.pending(here)
            # Whether each Build conversation still exists in this profile's session store (None: unknown).
            stored_ids = {g["session"]["storedId"] for g in listed if g.get("session")} | {p["storedId"] for p in pending}
            existing = _existing_sessions(stored_ids)
            for item in pending:
                item.pop("profile", None)
                item["exists"] = None if existing is None else item["storedId"] in existing
            for game in listed:
                session = game.get("session")
                if session:
                    owner = session.pop("profile", None)
                    session["thisProfile"] = owner in (None, here)
                    session["profileName"] = _profile_name(owner) if owner else None
                    session["exists"] = (None if existing is None or not session["thisProfile"]
                                         else session["storedId"] in existing)
                chat = game.get("chat")
                if chat and chat.get("sessionId"):
                    owner = chat.get("profile")
                    game["chat"] = {"sessionId": chat["sessionId"],
                                    "title": titles.get(chat["sessionId"]) or titles.get(chat.get("conversationId")),
                                    "conversationId": chat.get("conversationId"),
                                    "profile": _profile_name(owner) if owner else None,
                                    "thisProfile": owner == here if owner else None}
                else:
                    game["chat"] = None
                game.pop("updatedAt", None)
            # The built-in demo cartridge is not part of the library (the Games shelf stays the user's own
            # games); the Emulator page plays it when there is nothing else to play.
            return {"ok": True, "games": listed, "pending": pending, "demo": _demo_entry(),
                    "gamesDir": str(_games_dir_made()),
                    "device": {"hardwareEnabled": bool(ctx.get_config("hardware_enabled", False)), "skipped": False}}
        except Exception as error:
            logger.exception("hermretro games failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}", "games": [], "demo": _demo_entry()}
    return games


def rpc_build(ctx):
    """The Build page's game ↔ conversation binding. Params use ``stored`` (a stored session id), never
    ``session_id``: the gateway would authorize that as a live session and refuse the whole call.
      {action: "start", stored, name?, plan?}     a New Game conversation, before its project exists
      {action: "bind", game, stored, replace?}    give a game its conversation (replace: the old one is gone)
      {action: "cancel", stored}                  forget a New Game conversation that made nothing
      {action: "unbind", game, stored}            stop editing: the game lets go of its conversation"""
    def build(params, **_kwargs):
        params = params if isinstance(params, dict) else {}
        action = params.get("action")
        stored = params.get("stored")
        here = _profile_identity()
        try:
            registry = _registry()
            if action == "start":
                record = registry.build_start(stored, here, params.get("name"), plan=params.get("plan") is True)
                return {"ok": True, "pending": {"storedId": record["storedId"], "name": record["name"]}}
            if action == "bind":
                entry = registry.bind(str(params.get("game") or ""), stored, here, replace=params.get("replace") is True)
                return {"ok": True, "game": entry["id"], "session": library.public_session(entry.get("session"))}
            if action == "cancel":
                return {"ok": True, "cancelled": registry.build_cancel(stored, here)}
            if action == "unbind":
                return {"ok": True, "unbound": registry.unbind(str(params.get("game") or ""), stored, here)}
            return {"ok": False, "code": "INVALID", "error": "Unknown action."}
        except library.BindingError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro build failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return build


SHOW_ART_CONTEXT = (
    "To show the user a game's art (a sprite, background or cover), put the real file on its own line as "
    "MEDIA:<absolute path>, e.g. its assets/sprites/<name>.png: the Build page draws it in the game's colours, "
    "animates a sprite and opens it in its viewer (frames, palette, scenes, versions) on a click. Do not draw a "
    "preview or contact sheet to show existing art; make one only when the user asks for a picture that "
    "does not exist yet.")


def build_context(session_id=None, is_first_turn=False, **_kwargs):
    """``pre_llm_call``: tell a game's Build conversation which game it is (ephemeral, per turn)."""
    if not isinstance(session_id, str) or not session_id:
        return None
    try:
        kind, bound = _registry().binding_for(_profile_identity(), [session_id])
    except Exception:
        return None
    if kind == "game":
        title = bound.get("title") or Path(bound.get("projectRoot") or "").name
        return {"context": (f"[hermretro] This is the Build conversation of the game \"{title}\" "
                            f"({bound.get('projectRoot')}). The game is selected for you on the first chromatic "
                            "call. This conversation works on this one game: do not create or open other "
                            "projects here; for another game the user uses New Game or picks it on the "
                            "hermretro Build page. " + SHOW_ART_CONTEXT + " " + BUILD_REPORT_GUIDANCE)}
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
                            "conversation's game. " + BUILD_REPORT_GUIDANCE)}
    return None


ASSET_SUFFIXES = {".png": "image/png", ".gif": "image/gif", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
ASSET_MAX_BYTES = 6 * 1024 * 1024


def _image_size(data: bytes) -> tuple[int, int]:
    """Width and height from a PNG, GIF or JPEG header; (0, 0) when unknown."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                break
            marker, length = data[index + 1], int.from_bytes(data[index + 2:index + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return int.from_bytes(data[index + 7:index + 9], "big"), int.from_bytes(data[index + 5:index + 7], "big")
            index += 2 + length
    return 0, 0


def _asset_kind(relative: str | None) -> str:
    parts = (relative or "").split("/")
    if parts[:2] == ["assets", "sprites"]:
        return "sprite"
    if parts[:2] == ["assets", "backgrounds"]:
        return "background"
    if parts[:2] == ["assets", "ui"] or parts[:2] == ["assets", "fonts"]:
        return "ui"
    if "playtests" in parts or "frames" in parts:
        return "frame"
    if "captures" in parts:
        return "capture"
    return "image"


ASSET_KEEP_VERSIONS = 40
# A line of a reply that delivers a file (``MEDIA:/path``), quotes or backticks allowed around the path.
_MEDIA_LINE = re.compile(r"^[ \t]*MEDIA:[ \t]*([`\"']?)(.+?\.(?:png|gif|jpe?g|webp))\1[ \t]*$", re.IGNORECASE | re.MULTILINE)


def _asset_roots() -> list[Path]:
    roots = [(_data_dir() / "frames").resolve()]
    for game in _registry().library():
        try:
            roots.append(Path(game["projectRoot"]).resolve())
        except (KeyError, OSError, RuntimeError):
            continue
    return roots


def _asset_file(raw) -> tuple[Path, Path] | None:
    """The real file and the root it is shown from, for an image inside a library game or the saved
    frames; None for anything else."""
    raw = str(raw or "")
    if raw.startswith("file://"):
        raw = raw[len("file://"):]
    candidate = Path(raw).expanduser()
    # Cheap checks first: this runs after every tool call.
    if not raw or not candidate.is_absolute() or candidate.suffix.lower() not in ASSET_SUFFIXES:
        return None
    try:
        real = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if real.suffix.lower() not in ASSET_SUFFIXES or not real.is_file():
        return None
    root = next((base for base in _asset_roots() if real == base or base in real.parents), None)
    return (real, root) if root is not None else None


def _versions_dir(real: Path) -> Path:
    return _data_dir() / "asset-versions" / hashlib.sha256(str(real).encode("utf-8")).hexdigest()[:24]


def _keep_version(real: Path) -> None:
    """Keep this version of a game image (named by its modification time), so a later rewrite of the
    same file (cover.png made again) does not change what an earlier reply showed."""
    try:
        stat = real.stat()
        if stat.st_size > ASSET_MAX_BYTES:
            return
        folder = _versions_dir(real)
        target = folder / f"{stat.st_mtime_ns}{real.suffix.lower()}"
        if target.exists():
            return
        folder.mkdir(parents=True, exist_ok=True)
        data = real.read_bytes()
        kept = sorted(folder.iterdir(), key=lambda item: item.name)
        if kept and kept[-1].read_bytes() == data:
            return
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(data)
        partial.replace(target)
        for old in kept[: max(0, len(kept) + 1 - ASSET_KEEP_VERSIONS)]:
            old.unlink(missing_ok=True)
    except OSError:
        logger.debug("hermretro could not keep an image version", exc_info=True)


def _version_at(real: Path, at_ms) -> Path | None:
    """The kept version of ``real`` that was current at ``at_ms`` (a reply's time), when the file has
    been rewritten since; None when the file on disk is still that version (or nothing older was kept)."""
    try:
        at_ns = int(float(at_ms) * 1_000_000)
    except (TypeError, ValueError):
        return None
    if at_ns <= 0 or real.stat().st_mtime_ns <= at_ns:
        return None
    folder = _versions_dir(real)
    if not folder.is_dir():
        return None
    older = [item for item in folder.iterdir() if item.suffix != ".part" and item.stem.isdigit() and int(item.stem) <= at_ns]
    return max(older, key=lambda item: int(item.stem)) if older else None


def _keep_paths(values) -> None:
    for value in values:
        if isinstance(value, str) and value:
            found = _asset_file(value)
            if found:
                _keep_version(found[0])


def keep_delivered_images(assistant_response=None, **_kwargs):
    """``post_llm_call``: keep the images a reply delivered (``MEDIA:`` lines), as they are right now."""
    try:
        if isinstance(assistant_response, str) and "MEDIA:" in assistant_response:
            _keep_paths(match.group(2).strip() for match in _MEDIA_LINE.finditer(assistant_response))
    except Exception:
        logger.debug("hermretro keep_delivered_images failed", exc_info=True)


def keep_inspected_images(tool_name=None, args=None, **_kwargs):
    """``post_tool_call``: keep the images a step looked at or wrote, as they are right after it."""
    try:
        if isinstance(args, dict):
            _keep_paths(args.get(key) for key in ("image_url", "image", "assetPath", "outputPath", "path"))
    except Exception:
        logger.debug("hermretro keep_inspected_images failed", exc_info=True)


def _snapshots_dir() -> Path:
    return _data_dir() / "snapshots"


def _result_payload(result):
    """A tool result as the model saw it: the JSON text, or the multimodal envelope's text summary."""
    if isinstance(result, dict) and result.get("_multimodal"):
        result = result.get("text_summary")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return None
    return result if isinstance(result, dict) else None


def build_succeeded(result, status=None) -> bool:
    """Whether a delivered ``chromatic_rom_build`` result is a successful build: no error from Hermes or
    the adapter, and the engine's own ``structuredContent.success`` is true."""
    if status not in (None, "", "ok"):
        return False
    payload = _result_payload(result)
    if not payload or payload.get("error") or payload.get("isError"):
        return False
    structured = payload.get("structuredContent")
    return isinstance(structured, dict) and structured.get("success") is True


def _library_root_for(candidates) -> tuple[str, Path] | None:
    """The first library game whose project is, or contains, one of ``candidates``."""
    games = [entry for entry in _registry().load()["games"].values()
             if isinstance(entry, dict) and isinstance(entry.get("projectRoot"), str)]
    roots = []
    for entry in games:
        try:
            roots.append(Path(os.path.realpath(entry["projectRoot"])))
        except (OSError, ValueError):
            continue
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate:
            continue
        try:
            real = Path(os.path.realpath(candidate))
        except (OSError, ValueError):
            continue
        for root in roots:
            if (real == root or root in real.parents) and root.is_dir():
                return library.game_id(root), root
    return None


def snapshot_after_build(tool_name=None, args=None, result=None, status=None, conversation_id=None,
                         session_id=None, **_kwargs):
    """``post_tool_call``: after a successful build of a library game, keep a snapshot of its files for
    the Build page's history (Restore). Never raises."""
    try:
        if tool_name != "chromatic_rom_build" or not build_succeeded(result, status):
            return
        args = args if isinstance(args, dict) else {}
        if args.get("sourcePath"):
            return  # a standalone C experiment, not the game's build
        structured = (_result_payload(result) or {}).get("structuredContent") or {}
        candidates = [structured.get("projectRoot"), args.get("projectPath")]
        try:
            candidates.append(_chat_project(str(conversation_id or ""), str(session_id or "")))
        except Exception:
            logger.debug("hermretro: no chat project for the build snapshot", exc_info=True)
        candidates += [structured.get("outputPath"), structured.get("romPath")]
        found = _library_root_for(candidates)
        if found is None:
            return
        game, root = found
        taken = snapshots.take(_snapshots_dir(), game, root, "build")
        if taken.get("skipped"):
            logger.debug("hermretro: build snapshot of %s skipped: %s", root, taken["skipped"])
    except Exception:
        logger.debug("hermretro snapshot_after_build failed", exc_info=True)


def after_tool_call(**kwargs):
    """``post_tool_call``: keep inspected image versions, then snapshot a successful build."""
    keep_inspected_images(**kwargs)
    snapshot_after_build(**kwargs)


def rpc_asset(ctx):
    """One image for the Build page (a thumbnail, the asset viewer): only from a library game's folder
    or the frames Hermes saved from tool results. Answers a data URL, its size and, for a sprite, the
    frame size and speed from its sidecar, so the page can animate it. With ``at`` (a reply's time, in
    ms) it answers the version the file had then, when it was kept and the file has changed since."""
    def asset(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            raw = str(params.get("path") or "")
            if raw.startswith("file://"):
                raw = raw[len("file://"):]
            candidate = Path(raw).expanduser()
            if not raw or not candidate.is_absolute():
                return {"ok": False, "code": "INVALID", "error": "An absolute image path is required."}
            real = candidate.resolve(strict=True)
            mime = ASSET_SUFFIXES.get(real.suffix.lower())
            if mime is None or not real.is_file():
                return {"ok": False, "code": "NOT_IMAGE", "error": "Not an image."}
            roots = _asset_roots()
            root = next((base for base in roots if real == base or base in real.parents), None)
            if root is None:
                return {"ok": False, "code": "OUTSIDE", "error": "Only images in your games are shown here."}
            size = real.stat().st_size
            if size > ASSET_MAX_BYTES:
                return {"ok": False, "code": "TOO_LARGE", "error": "The image is too large to preview."}
            _keep_version(real)
            earlier = None
            wanted = str(params.get("version") or "")
            if wanted:
                # One kept version by its id (the file's modification time in ns), as the viewer lists them.
                if not wanted.isdigit():
                    return {"ok": False, "code": "INVALID", "error": "Unknown version."}
                if int(wanted) != real.stat().st_mtime_ns:
                    kept = _versions_dir(real) / f"{wanted}{real.suffix.lower()}"
                    if not kept.is_file():
                        return {"ok": False, "code": "MISSING", "error": "That version is no longer kept."}
                    earlier = kept
            elif params.get("at") is not None:
                earlier = _version_at(real, params.get("at"))
            source = earlier or real
            data = source.read_bytes()
            width, height = _image_size(data)
            relative = real.relative_to(root).as_posix() if root != (_data_dir() / "frames").resolve() else None
            answer = {"ok": True, "path": str(real), "relative": relative, "name": real.name, "kind": _asset_kind(relative)
                      if relative else "frame", "width": width, "height": height, "bytes": len(data),
                      "modifiedAt": (int(earlier.stem) / 1e9) if earlier else real.stat().st_mtime,
                      "earlier": earlier is not None,
                      "versionId": earlier.stem if earlier else str(real.stat().st_mtime_ns),
                      "dataUrl": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"}
            sidecar = real.with_name(real.name + ".gbsres")
            if answer["kind"] == "sprite" and sidecar.is_file() and sidecar.stat().st_size < 2 * 1024 * 1024:
                try:
                    meta = json.loads(sidecar.read_text(encoding="utf-8"))
                    frame_width, frame_height = int(meta.get("canvasWidth") or 0), int(meta.get("canvasHeight") or 0)
                    if frame_width > 0 and frame_height > 0:
                        answer["sprite"] = {"name": meta.get("name"), "frameWidth": frame_width, "frameHeight": frame_height,
                                            "animSpeed": meta.get("animSpeed")}
                        if isinstance(meta, dict) and meta.get("id"):
                            answer["sprite"].update(_sprite_look(root, meta))
                except (ValueError, TypeError, OSError):
                    pass
            return answer
        except FileNotFoundError:
            return {"ok": False, "code": "MISSING", "error": "The image is gone."}
        except Exception as error:
            logger.exception("hermretro asset failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return asset


# GB Studio's animation slots, by sprite type (the compiler's order).
_ANIMATION_NAMES = {
    "fixed": ["Idle"],
    "fixed_movement": ["Idle", None, None, None, "Moving"],
    "multi": ["Right", "Left", "Up", "Down"],
    "multi_movement": ["Idle right", "Idle left", "Idle up", "Idle down", "Walk right", "Walk left", "Walk up", "Walk down"],
    "horizontal": ["Right", "Left"],
    "horizontal_movement": ["Idle right", "Idle left", None, None, "Walk right", "Walk left"],
    "platform_player": ["Idle right", "Idle left", "Run right", "Run left", "Jump right", "Jump left", "Climb", "Climb idle"],
    "cursor": ["Idle", "Hover"],
}
# The slot an actor facing each way shows when it stands still.
_FACING_SLOT = {"multi": {"right": 0, "left": 1, "up": 2, "down": 3},
                "multi_movement": {"right": 0, "left": 1, "up": 2, "down": 3},
                "horizontal": {"right": 0, "left": 1}, "horizontal_movement": {"right": 0, "left": 1},
                "platform_player": {"right": 0, "left": 1}}
_ASSET_INFO_SCENES = 6
_ASSET_INFO_ACTORS = 40


def _read_json(path: Path, limit: int = 4 * 1024 * 1024):
    try:
        if path.is_file() and path.stat().st_size <= limit:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        pass
    return None


def _tiles(frame) -> list[dict]:
    tiles = []
    for tile in (frame or {}).get("tiles") or []:
        if isinstance(tile, dict):
            tiles.append({key: tile.get(key) for key in ("x", "y", "sliceX", "sliceY", "flipX", "flipY")})
    return tiles


def _sprite_animations(meta: dict) -> dict:
    """The first sprite state's animations, named the way GB Studio names its slots. A left slot left
    empty with ``flipLeft`` is drawn as the right one mirrored."""
    states = [state for state in meta.get("states") or [] if isinstance(state, dict)]
    state = states[0] if states else {}
    kind = str(state.get("animationType") or "fixed")
    names = _ANIMATION_NAMES.get(kind, [])
    animations = []
    for index, animation in enumerate(state.get("animations") or []):
        frames = [_tiles(frame) for frame in (animation or {}).get("frames") or [] if isinstance(frame, dict)]
        name = names[index] if index < len(names) else None
        animations.append({"slot": index, "name": name or f"Animation {index + 1}", "frames": frames[:64]})
    return {"name": meta.get("name"), "id": meta.get("id"), "type": kind, "flipLeft": bool(state.get("flipLeft")),
            "states": [str(item.get("name") or "") for item in states],
            "canvasWidth": int(meta.get("canvasWidth") or 16), "canvasHeight": int(meta.get("canvasHeight") or 16),
            "animSpeed": meta.get("animSpeed"), "numTiles": meta.get("numTiles"), "animations": animations}


def _standing_frame(sprite: dict, direction: str) -> dict:
    """The tiles an actor shows standing still, facing ``direction``, and whether they are mirrored."""
    animations = sprite.get("animations") or []
    facing = _FACING_SLOT.get(str(sprite.get("type") or ""), {})
    slot = facing.get(direction or "down", 0)

    def first(index):
        frames = animations[index]["frames"] if 0 <= index < len(animations) else []
        return frames[0] if frames else []

    if not first(slot) and direction == "left" and sprite.get("flipLeft"):
        return {"tiles": first(facing.get("right", 0)), "flip": True}
    return {"tiles": first(slot) or first(0), "flip": False}


def _project_index(root: Path) -> dict:
    """Sprites, backgrounds, palettes, scenes and settings of a distributed GB Studio project."""
    resources = root / "project"
    index = {"sprites": {}, "backgrounds": {}, "palettes": {}, "scenes": [], "settings": _read_json(resources / "settings.gbsres") or {}}
    for folder, key in (("sprites", "sprites"), ("backgrounds", "backgrounds")):
        for sidecar in sorted((root / "assets" / folder).glob("*.gbsres")):
            meta = _read_json(sidecar)
            if meta and meta.get("id"):
                index[key][meta["id"]] = {"meta": meta, "path": sidecar.with_name(sidecar.name[: -len(".gbsres")])}
    for sidecar in sorted((resources / "palettes").glob("*.gbsres")):
        meta = _read_json(sidecar)
        if meta and meta.get("id") and isinstance(meta.get("colors"), list):
            index["palettes"][meta["id"]] = meta
    for scene_file in sorted((resources / "scenes").glob("*/scene.gbsres")):
        scene = _read_json(scene_file)
        if not scene:
            continue
        actors = [actor for actor in (_read_json(item) for item in sorted((scene_file.parent / "actors").glob("*.gbsres"))) if actor]
        scene["_actors"] = actors
        index["scenes"].append(scene)
    index["scenes"].sort(key=lambda scene: (scene.get("_index", 0) if isinstance(scene.get("_index"), int) else 0))
    return index


def _palette(index: dict, palette_id) -> dict | None:
    palette = index["palettes"].get(palette_id) if palette_id else None
    if not palette:
        return None
    colors = [f"#{str(color).lstrip('#')}" for color in palette.get("colors") or []][:4]
    return {"id": palette_id, "name": palette.get("name") or "", "colors": colors} if len(colors) == 4 else None


def _player_sprite_id(settings: dict, scene: dict):
    return scene.get("playerSpriteSheetId") or (settings.get("defaultPlayerSprites") or {}).get(scene.get("type")) \
        or settings.get("playerSpriteSheetId")


def _actor_palette(index: dict, scene: dict, palette_id) -> dict | None:
    settings = index["settings"]
    scene_palettes = [item for item in scene.get("spritePaletteIds") or [] if item]
    return _palette(index, palette_id) or _palette(index, scene_palettes[0] if scene_palettes else None) \
        or _palette(index, settings.get("defaultSpritePaletteId")) \
        or _palette(index, (settings.get("defaultSpritePaletteIds") or [None])[0])


def _scene_view(index: dict, scene: dict, sprites_cache: dict) -> dict:
    """What a scene draws: its background, and each actor's standing frame at its place (the player at
    the start position in the start scene)."""
    settings = index["settings"]
    background = index["backgrounds"].get(scene.get("backgroundId"))
    actors = []

    def add(name, sprite_id, x, y, direction, palette_id, player=False):
        entry = index["sprites"].get(sprite_id)
        if not entry or len(actors) >= _ASSET_INFO_ACTORS:
            return
        sprite = sprites_cache.setdefault(sprite_id, _sprite_animations(entry["meta"]))
        actors.append({"name": name, "spriteId": sprite_id, "sprite": str(entry["path"]), "x": x, "y": y, "player": player,
                       "canvasWidth": sprite["canvasWidth"], "canvasHeight": sprite["canvasHeight"],
                       **_standing_frame(sprite, direction), "palette": _actor_palette(index, scene, palette_id)})

    if scene.get("id") and scene.get("id") == settings.get("startSceneId"):
        add("Player", _player_sprite_id(settings, scene), settings.get("startX", 0), settings.get("startY", 0),
            settings.get("startDirection") or "down", settings.get("playerPaletteId"), player=True)
    for actor in scene.get("_actors") or []:
        add(actor.get("name") or "Actor", actor.get("spriteSheetId"), actor.get("x", 0), actor.get("y", 0),
            actor.get("direction") or "down", actor.get("paletteId"))
    return {"id": scene.get("id"), "name": scene.get("name") or "Scene", "width": scene.get("width"), "height": scene.get("height"),
            "background": str(background["path"]) if background else None, "actors": actors}


_SPRITE_USES: dict[str, tuple] = {}
_SPRITE_USES_ROOTS = 16
# The animation that plays while an actor moves, from the slot it stands in (GB Studio's slot order).
_MOVING_OFFSET = {"multi_movement": 4, "horizontal_movement": 4, "platform_player": 2}


def _project_stamp(root: Path) -> tuple:
    """What a sprite's look depends on besides its own sidecar: settings, palettes, scenes and actors."""
    resources = root / "project"
    files = [resources / "settings.gbsres", *resources.glob("palettes/*.gbsres"), *resources.glob("scenes/*/scene.gbsres"),
             *resources.glob("scenes/*/actors/*.gbsres"), *(root / "assets" / "sprites").glob("*.gbsres")]
    stamp = []
    for item in files:
        try:
            stamp.append((str(item), item.stat().st_mtime_ns))
        except OSError:
            continue
    return tuple(sorted(stamp))


def _sprite_uses(root: Path) -> dict:
    """For each sprite of a project: how its first use in the game shows it (facing, palette), and the
    palette a sprite nobody uses yet would get. Cached per project until one of its files changes."""
    stamp = _project_stamp(root)
    cached = _SPRITE_USES.get(str(root))
    if cached and cached[0] == stamp:
        return cached[1]
    index = _project_index(root)
    settings = index["settings"]
    uses = {}
    for scene in index["scenes"]:
        candidates = []
        if scene.get("id") and scene.get("id") == settings.get("startSceneId"):
            candidates.append((_player_sprite_id(settings, scene), settings.get("startDirection"), settings.get("playerPaletteId")))
        for actor in scene.get("_actors") or []:
            candidates.append((actor.get("spriteSheetId"), actor.get("direction"), actor.get("paletteId")))
        for sprite_id, direction, palette_id in candidates:
            if sprite_id and sprite_id not in uses:
                uses[sprite_id] = {"direction": direction or "down", "palette": _actor_palette(index, scene, palette_id)}
    result = {"uses": uses, "default": _actor_palette(index, {}, None)}
    if len(_SPRITE_USES) >= _SPRITE_USES_ROOTS:
        _SPRITE_USES.pop(next(iter(_SPRITE_USES)))
    _SPRITE_USES[str(root)] = (stamp, result)
    return result


def _sprite_look(root: Path, meta: dict) -> dict:
    """How the game shows a sprite, for thumbnails: the palette it is painted with, the tiles of the
    frame it stands in (facing the way its first use faces) and the frames it moves with."""
    try:
        sprite = _sprite_animations(meta)
        found = _sprite_uses(root)
        use = found["uses"].get(meta.get("id")) or {}
        palette = use.get("palette") or found["default"]
        direction = use.get("direction") or "down"
        standing = _standing_frame(sprite, direction)
        animations = sprite.get("animations") or []
        facing = _FACING_SLOT.get(sprite.get("type") or "", {})
        slot = facing.get(direction, 0) + _MOVING_OFFSET.get(sprite.get("type") or "", 0)
        if sprite.get("type") == "fixed_movement":
            slot = 4
        moving = animations[slot]["frames"] if 0 <= slot < len(animations) else []
        moving_flip = False
        if not any(moving) and direction == "left" and sprite.get("flipLeft"):
            right = facing.get("right", 0) + _MOVING_OFFSET.get(sprite.get("type") or "", 0)
            moving, moving_flip = (animations[right]["frames"] if 0 <= right < len(animations) else []), True
        return {"canvasWidth": sprite["canvasWidth"], "canvasHeight": sprite["canvasHeight"],
                "palette": palette["colors"] if palette else None,
                "standing": standing,
                "moving": {"frames": [frame for frame in moving if frame][:16], "flip": moving_flip}}
    except Exception:
        logger.debug("hermretro could not work out how a sprite looks", exc_info=True)
        return {}


def _versions(real: Path) -> list[dict]:
    """Every kept version of a file, oldest first, with the current one marked."""
    folder = _versions_dir(real)
    kept = sorted((item for item in folder.iterdir() if item.stem.isdigit() and item.suffix != ".part"), key=lambda item: int(item.stem)) \
        if folder.is_dir() else []
    current = real.stat().st_mtime_ns
    data = real.read_bytes()
    versions = [{"id": item.stem, "at": int(item.stem) // 1_000_000, "file": str(item), "current": False} for item in kept]
    match = next((entry for entry in reversed(versions) if int(entry["id"]) == current), None)
    if match is None and kept and kept[-1].read_bytes() == data:
        match = versions[-1]
    if match is None:
        versions.append({"id": str(current), "at": current // 1_000_000, "file": str(real), "current": True})
    else:
        match["current"] = True
    return versions


def rpc_asset_info(ctx):
    """What the asset viewer shows beside an image: its kind, every kept version, and for a sprite or
    background its animations, the palette the game paints it with, and the scenes that use it (drawn
    by the page as the game would)."""
    def asset_info(params, **_kwargs):
        try:
            found = _asset_file((params or {}).get("path") if isinstance(params, dict) else None)
            if not found:
                return {"ok": False, "code": "OUTSIDE", "error": "Only images in your games are shown here."}
            real, root = found
            _keep_version(real)
            frames = root == (_data_dir() / "frames").resolve()
            relative = None if frames else real.relative_to(root).as_posix()
            kind = "frame" if frames else _asset_kind(relative)
            answer = {"ok": True, "path": str(real), "relative": relative, "kind": kind, "versions": _versions(real)}
            if not frames and real == game_card.cover_path(root).resolve():
                answer["kind"] = "cover"
            if frames or kind not in ("sprite", "background"):
                return answer
            meta = _read_json(real.with_name(real.name + ".gbsres"))
            if not meta or not meta.get("id"):
                return answer
            index = _project_index(root)
            sprites_cache = {}
            uses, scenes = [], []
            if kind == "sprite":
                sprite = _sprite_animations(meta)
                sprites_cache[meta["id"]] = sprite
                answer["sprite"] = sprite
                palette = None
                for scene in index["scenes"]:
                    view = _scene_view(index, scene, sprites_cache)
                    mine = [actor for actor in view["actors"] if actor["spriteId"] == meta["id"]]
                    if mine:
                        palette = palette or mine[0]["palette"]
                        uses.append({"scene": view["name"], "sceneId": view["id"],
                                     "as": [actor["name"] for actor in mine][:6], "count": len(mine)})
                        if len(scenes) < _ASSET_INFO_SCENES:
                            scenes.append(view)
                answer["palette"] = palette or _actor_palette(index, {}, None)
            else:
                for scene in index["scenes"]:
                    if scene.get("backgroundId") == meta["id"]:
                        view = _scene_view(index, scene, sprites_cache)
                        uses.append({"scene": view["name"], "sceneId": view["id"], "as": ["Background"], "count": 1})
                        if len(scenes) < _ASSET_INFO_SCENES:
                            scenes.append(view)
                answer["background"] = {"name": meta.get("name"), "autoColor": bool(meta.get("autoColor"))}
            answer["usedIn"] = uses
            answer["scenes"] = scenes
            answer["sprites"] = {sprite_id: {key: sprite[key] for key in ("canvasWidth", "canvasHeight")}
                                 for sprite_id, sprite in sprites_cache.items()}
            return answer
        except FileNotFoundError:
            return {"ok": False, "code": "MISSING", "error": "The image is gone."}
        except Exception as error:
            logger.exception("hermretro asset_info failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return asset_info


def rpc_asset_restore(ctx):
    """Put a kept version of a game image back in place (the one there now is kept first, so this can
    be undone the same way)."""
    def asset_restore(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            found = _asset_file(params.get("path"))
            wanted = str(params.get("version") or "")
            if not found or not wanted.isdigit():
                return {"ok": False, "code": "INVALID", "error": "Only a kept version of an image in your games can be restored."}
            real, root = found
            if root == (_data_dir() / "frames").resolve():
                return {"ok": False, "code": "INVALID", "error": "Playtest frames are not restored."}
            kept = _versions_dir(real) / f"{wanted}{real.suffix.lower()}"
            if not kept.is_file():
                return {"ok": False, "code": "MISSING", "error": "That version is no longer kept."}
            _keep_version(real)
            partial = real.with_name(f".{real.name}.restore")
            partial.write_bytes(kept.read_bytes())
            partial.replace(real)
            _keep_version(real)
            return {"ok": True, "path": str(real), "versions": _versions(real)}
        except Exception as error:
            logger.exception("hermretro asset_restore failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return asset_restore


_ASSET_LIST_FOLDERS = (("sprites", "sprite"), ("backgrounds", "background"), ("ui", "ui"), ("fonts", "ui"))
ASSET_LIST_LIMIT = 400


def _list_root(params) -> Path | None:
    """The library game a list is for, by id or by its folder (never a folder outside the library)."""
    root = _game_root(str(params.get("game") or "")) if params.get("game") else None
    if root is None and params.get("root"):
        try:
            wanted = Path(str(params["root"])).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        frames = (_data_dir() / "frames").resolve()
        root = next((base for base in _asset_roots() if base == wanted and base != frames), None)
    return root


def rpc_assets(ctx):
    """Every picture of one game, for the Build page's Assets panel: the game card's cover, then its
    sprites, backgrounds and interface art, each with the name its sidecar gives it. Lists files only
    (no image data); the page fetches each one through ``asset``."""
    def assets(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            root = _list_root(params)
            if root is None:
                return {"ok": False, "code": "NO_GAME", "error": "Only a game in your library can be listed."}
            items = []
            cover = game_card.cover_path(root)
            if cover.is_file():
                stat = cover.stat()
                items.append({"path": str(cover.resolve()), "relative": cover.relative_to(root).as_posix(), "name": "Cover",
                              "file": cover.name, "kind": "cover", "modifiedAt": stat.st_mtime, "bytes": stat.st_size})
            for folder, kind in _ASSET_LIST_FOLDERS:
                base = root / "assets" / folder
                if not base.is_dir():
                    continue
                for image in sorted(base.rglob("*")):
                    if len(items) >= ASSET_LIST_LIMIT:
                        break
                    if image.suffix.lower() not in ASSET_SUFFIXES or not image.is_file():
                        continue
                    try:
                        real = image.resolve(strict=True)
                    except (OSError, RuntimeError):
                        continue
                    if real != root and root not in real.parents:
                        continue
                    meta = _read_json(image.with_name(image.name + ".gbsres"), 2 * 1024 * 1024) or {}
                    stat = real.stat()
                    items.append({"path": str(real), "relative": real.relative_to(root).as_posix(),
                                  "name": str(meta.get("name") or image.stem), "file": image.name, "kind": kind,
                                  "modifiedAt": stat.st_mtime, "bytes": stat.st_size})
            return {"ok": True, "root": str(root), "assets": items, "truncated": len(items) >= ASSET_LIST_LIMIT}
        except Exception as error:
            logger.exception("hermretro assets failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return assets


def rpc_builds(ctx):
    """The Build page's build history for one library game: ``{game}`` → its snapshots, newest first."""
    def builds(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            game = str(params.get("game") or "")
            if _game_root(game) is None:
                return {"ok": False, "code": "NO_GAME", "error": "Only a game in your library has builds."}
            return {"ok": True, "builds": snapshots.list_snapshots(_snapshots_dir(), game)}
        except Exception as error:
            logger.exception("hermretro builds failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return builds


def rpc_build_restore(ctx):
    """Put a game's files back as they were at one build (``{game, id}``). The current files are kept
    first as a ``before-restore`` snapshot; the page then asks the agent to rebuild."""
    def build_restore(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            game = str(params.get("game") or "")
            root = _game_root(game)
            if root is None:
                return {"ok": False, "code": "NO_GAME", "error": "Only a game in your library can be restored."}
            identifier = str(params.get("id") or "")
            return {"ok": True, **snapshots.restore(_snapshots_dir(), game, root, identifier)}
        except snapshots.SnapshotError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro build_restore failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}
    return build_restore


def rpc_game_thumb(ctx):
    def game_thumb(params, **_kwargs):
        try:
            params = params or {}
            identifier = str(params.get("id") or "")
            if _game_root(identifier) is None:
                return {"ok": False, "error": "Unknown game."}
            png = library.decode_png(params.get("png"), library.MAX_THUMB_BYTES)
            _registry().save_thumb(identifier, png)
            return {"ok": True}
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro game_thumb failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return game_thumb


def rpc_player(ctx):
    """Open ModRetro's real player for one game, served from this process's loopback server. Without
    an id (or with ``demo``) it opens the built-in demo cartridge, which needs no project."""
    def player(params, **_kwargs):
        try:
            identifier = str((params or {}).get("id") or "") or player_server.DEMO_ID
            if player_server.is_demo(identifier):
                build = player_server.demo_build()
                server = player_server.get_server(_game_root)
                return {"ok": True, "url": server.url(identifier), "romSha256": build["romSha256"],
                        "title": player_server.DEMO["title"], "demo": True}
            root = _game_root(identifier)
            if root is None:
                return {"ok": False, "error": "Unknown game."}
            title = library.project_title(root)
            if not library.has_web_export(root):
                return {"ok": False, "title": title,
                        "error": f"{title} has no playable build yet. Ask Hermes in its chat to build the game, "
                                 "then press Play again."}
            build = player_server.game_build(root)
            server = player_server.get_server(_game_root)
            return {"ok": True, "url": server.url(identifier), "romSha256": build["romSha256"], "title": title}
        except player_server.PlayerError as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro player failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return player


def rpc_presentations(ctx):
    """Games the agent presented (``chromatic_present_game``) after ``since`` (seconds), for a desktop
    that did not hear the tool complete. ``now`` is the backend's clock for the next ``since``."""
    def presentations(params, **_kwargs):
        try:
            since = (params or {}).get("since")
            since = float(since) if isinstance(since, (int, float)) and not isinstance(since, bool) else None
            here = _profile_identity()
            listed = []
            for item in _registry().presentations(since)[-20:]:
                owner = item.get("profile")
                listed.append({"gameId": item["gameId"], "title": item.get("title"), "t": item["t"],
                               "note": item.get("note"), "sessionId": item.get("sessionId"),
                               "conversationId": item.get("conversationId"),
                               "profile": _profile_name(owner) if owner else None,
                               "thisProfile": owner == here if owner else None})
            return {"ok": True, "now": time.time(), "presentations": listed}
        except Exception as error:
            logger.exception("hermretro presentations failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}", "presentations": []}
    return presentations


def rpc_captures(ctx):
    def captures(params, **_kwargs):
        try:
            identifier = str((params or {}).get("id") or "")
            root = _capture_root(identifier)
            if root is None:
                return {"ok": False, "error": "Unknown game.", "captures": []}
            server = player_server.get_server(_game_root)
            found = player_server.list_captures(root, identifier)
            return {"ok": True, "captures": [{"path": c["path"], "kind": c["kind"], "createdAt": c["createdAt"],
                                              "url": server.capture_url(identifier, c["id"])} for c in found]}
        except Exception as error:
            logger.exception("hermretro captures failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}", "captures": []}
    return captures


def rpc_capture_image(ctx):
    """Save a game-screen image (Ask Hermes / annotate) under the project's captures folder, so the
    chat text can name a file the agent opens itself."""
    def capture_image(params, **_kwargs):
        try:
            params = params or {}
            identifier = str(params.get("id") or "")
            root = _capture_root(identifier)
            if root is None:
                return {"ok": False, "error": "Unknown game."}
            png = library.decode_png(params.get("png"), 4 * 1024 * 1024)
            receipt = player_server.save_capture(root, identifier, "annotation", png, "image/png", None)
            return {"ok": True, "path": receipt["path"]}
        except (ValueError, player_server.PlayerError) as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro capture_image failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return capture_image


# -- hooks -------------------------------------------------------------------------

def make_pre_tool_call(ctx):
    def pre_tool_call(tool_name=None, args=None, **_kwargs):
        """Send every hardware-changing call, and the vendor download, through Hermes's own
        human-approval gate. Denial, timeout or nobody to ask all leave the tool unrun."""
        if tool_name == DEVICE_CLI_TOOL["name"]:
            if not isinstance(args, dict) or args.get("action") != "install":
                return None  # status is passive
            try:
                host = provision.host_target()
                pins = provision._pins(host["target"]) if host["target"] else None
            except Exception:
                pins = None
            if pins is None:
                return None  # nothing can be installed here; the tool explains why
            megabytes = pins["package"]["bytes"] / 1_000_000
            return {"action": "approve",
                    "message": (f"Download ModRetro's Chromatic CLI {pins['version']} ({megabytes:.1f} MB) from "
                                f"{pins['package']['url']} into hermretro's folder in the Hermes home. It is proprietary "
                                f"ModRetro software; approving means you agree to ModRetro's terms "
                                f"({provision.VENDOR_TERMS_URL}). Nothing is sent to a device."),
                    # One key per CLI release: "always" covers a reinstall, never a different version.
                    "rule_key": f"hermretro:device-cli-install:{pins['version']}"}
        if tool_name not in _APPROVAL_TOOLS or not ctx.get_config("hardware_enabled", False):
            return None  # disabled hardware is refused by the broker; nothing to approve
        args = args or {}
        if tool_name == "chromatic_flash":
            message = ("Write a ROM to the cartridge in the connected Chromatic. Existing cartridge game data is "
                       f"erased, saves may be lost and no backup is made. ROM: {args.get('romPath')} "
                       f"({args.get('expectedSizeBytes')} bytes, SHA-256 {args.get('expectedSha256')}).")
        elif tool_name == "chromatic_play":
            message = ("Stream a host-emulated demo to the connected Chromatic. This loads a streaming image into "
                       f"the device; it does not write the cartridge. ROM: {args.get('romPath')}.")
        else:
            message = ("Chromatic device setup: " + str(args.get("command")) + ". Installing drivers changes "
                       "system USB access; cartridge detection reconfigures the device.")
        # A unique rule key per request, so one approval can never cover a later or different operation.
        detail = json.dumps([args.get(key) for key in
                             ("requestId", "command", "romPath", "expectedSizeBytes", "expectedSha256")],
                            default=str)       # unambiguous: a path may itself contain a separator
        return {"action": "approve", "message": message, "rule_key": f"hermretro:{tool_name}:{detail}"}
    return pre_tool_call


SYSTEM_PROMPT_SECTION = (
    "hermretro is installed: tools named chromatic_* build real Game Boy / Game Boy Color games "
    "(native GB Studio projects) for the ModRetro Chromatic. When the user wants to plan, create, edit, build, "
    "playtest or deploy such a game, first load the matching skill with skill_view: "
    "hermretro:setup (install or repair dependencies; load it for any setup request), hermretro:game-planning, hermretro:authoring, "
    "hermretro:pixel-art, hermretro:rom-debugging (build and emulator testing), "
    "hermretro:deployment (physical Chromatic). Call chromatic_* tools directly, never from execute_code. "
    "One conversation works on one project folder; use a new chat for a different project. "
    "New games go in the hermretro games folder: leave destinationPath out of chromatic_project_create "
    "and chromatic_project_create_blank unless the user names another folder. "
    "Build after each meaningful change. Nothing opens for the user after a build: when the game is ready for "
    "the user to try (after your own testing), fill in its game card with chromatic_game_info (pixel-art cover, "
    "title, tagline, description, genres), then call chromatic_present_game, optionally with a short note on what "
    "to try; it shows the game in the hermretro emulator beside the chat. Call it again after later "
    "changes the user should test. " + BUILD_REPORT_GUIDANCE + " "
    "Do not open the game with desktop_preview or reload it with drive_preview. "
    "Only if the user says they cannot see the emulator, open studio.playerUrl from chromatic_present_game with "
    "desktop_preview (action \"open\"); without desktop tools, give the user that url. "
    "Hardware tools stay off until the user enables them in Settings > Plugins > hermretro."
)
