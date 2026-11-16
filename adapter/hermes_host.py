"""Everything that touches Hermes: tool handlers, RPC methods, hooks, prompt section.

Handlers run wherever Hermes dispatches tools (gateway, plugin host or an isolated
turn process). They hold no state of their own: every call goes to the broker.
"""
from __future__ import annotations

import json
import logging
import platform
import threading
import time
from pathlib import Path

from . import contracts, onboarding, paths, player_server, provision, results, studio_profile
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
        "places it inside the hermretro plugin folder. It is needed only for hardware features (device "
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
        "build. Needs a fresh playable copy: run chromatic_rom_build first. Never touches a device. Do not open "
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


# -- desktop RPC -----------------------------------------------------------------

def rpc_status(ctx):
    def status(params, *, session_id=None, **_kwargs):
        try:
            node = paths.find_node()
            answer = {
                "ok": True,
                "plugin": {"id": paths.PLUGIN_ID, "version": paths.PLUGIN_VERSION},
                "platform": {"system": platform.system().lower(), "machine": platform.machine(),
                             "qualified": platform.system() == "Linux" and platform.machine() in ("x86_64", "AMD64")},
                "node": {"found": node["found"], "version": node["version"], "required": node["required"],
                         "ok": node["ok"]},
                "engine": paths.verify_engine(),
                "deps": provision.summary(),
                "hardware_enabled": bool(ctx.get_config("hardware_enabled", False)),
                "broker": {"running": False},
                "project": None,
                "profile": studio_profile.describe(_data_dir().parents[1]),
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
            for game in listed:
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
            return {"ok": True, "games": listed, "demo": _demo_entry(), "gamesDir": str(paths.games_dir()),
                    "device": {"hardwareEnabled": bool(ctx.get_config("hardware_enabled", False)), "skipped": False}}
        except Exception as error:
            logger.exception("hermretro games failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}", "games": [], "demo": _demo_entry()}
    return games


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
                                f"{pins['package']['url']} into the hermretro plugin folder. It is proprietary "
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
    "the user to try (after your own testing), call chromatic_present_game, optionally with a short note on what "
    "to try; it shows the game in the hermretro emulator beside the chat. Call it again after later "
    "changes the user should test. Do not open the game with desktop_preview or reload it with drive_preview. "
    "Only if the user says they cannot see the emulator, open studio.playerUrl from chromatic_present_game with "
    "desktop_preview (action \"open\"); without desktop tools, give the user that url. "
    "Hardware tools stay off until the user enables them in Settings > Plugins > hermretro."
)
