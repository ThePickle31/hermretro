"""The Games, Build and Emulator pages' RPCs: the library, the game <-> conversation binding, the real player
and captures. Declared with @rpc; registered in this order (backend/hermes/declare.py)."""
from __future__ import annotations

import time
from pathlib import Path

from .. import player as player_server
from ..hermes import host
from ..hermes.declare import rpc
from ..system import paths
from . import games as library

logger = host.logger   # one logger for the Hermes side of the backend

# Shared helpers (the data folder, the profile, the library, the broker client) stay in backend.hermes.host and are
# looked up there at call time, so one patch of host.<name> reaches every module.

def _games_dir_made():
    """The games folder, created so "Open games folder" opens it on a fresh install (a reveal of a missing
    folder does nothing). A folder that cannot be made is still named."""
    try:
        return paths.games_dir(create=True)
    except OSError:
        return paths.games_dir()


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
        database = host._data_dir().parents[1] / "state.db"
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
        database = host._data_dir().parents[1] / "state.db"
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
    client, _error = host.try_connect(paths.runtime_dir())
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
    return player_server.demo_captures_root() if player_server.is_demo(identifier) else host._game_root(identifier)


@rpc("games")
def rpc_games(ctx):
    def games(params, **_kwargs):
        try:
            registry = host._registry()
            try:
                _seed_library(registry)
            except Exception:
                logger.debug("hermretro: seeding the library from the broker failed", exc_info=True)
            listed = registry.library()
            here = host._profile_identity()
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


@rpc("game_thumb")
def rpc_game_thumb(ctx):
    def game_thumb(params, **_kwargs):
        try:
            params = params or {}
            identifier = str(params.get("id") or "")
            if host._game_root(identifier) is None:
                return {"ok": False, "error": "Unknown game."}
            png = library.decode_png(params.get("png"), library.MAX_THUMB_BYTES)
            host._registry().save_thumb(identifier, png)
            return {"ok": True}
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro game_thumb failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return game_thumb


@rpc("player")
def rpc_player(ctx):
    """Open ModRetro's real player for one game, served from this process's loopback server. Without
    an id (or with ``demo``) it opens the built-in demo cartridge, which needs no project."""
    def player(params, **_kwargs):
        try:
            identifier = str((params or {}).get("id") or "") or player_server.DEMO_ID
            if player_server.is_demo(identifier):
                build = player_server.demo_build()
                server = player_server.get_server(host._game_root)
                return {"ok": True, "url": server.url(identifier), "romSha256": build["romSha256"],
                        "title": player_server.DEMO["title"], "demo": True}
            root = host._game_root(identifier)
            if root is None:
                return {"ok": False, "error": "Unknown game."}
            title = library.project_title(root)
            if not library.has_web_export(root):
                return {"ok": False, "title": title,
                        "error": f"{title} has no playable build yet. Ask Hermes in its chat to build the game, "
                                 "then press Play again."}
            build = player_server.game_build(root)
            server = player_server.get_server(host._game_root)
            return {"ok": True, "url": server.url(identifier), "romSha256": build["romSha256"], "title": title}
        except player_server.PlayerError as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro player failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return player


@rpc("presentations")
def rpc_presentations(ctx):
    """Games the agent presented (``chromatic_present_game``) after ``since`` (seconds), for a desktop
    that did not hear the tool complete. ``now`` is the backend's clock for the next ``since``."""
    def presentations(params, **_kwargs):
        try:
            since = (params or {}).get("since")
            since = float(since) if isinstance(since, (int, float)) and not isinstance(since, bool) else None
            here = host._profile_identity()
            listed = []
            for item in host._registry().presentations(since)[-20:]:
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


@rpc("captures")
def rpc_captures(ctx):
    def captures(params, **_kwargs):
        try:
            identifier = str((params or {}).get("id") or "")
            root = _capture_root(identifier)
            if root is None:
                return {"ok": False, "error": "Unknown game.", "captures": []}
            server = player_server.get_server(host._game_root)
            found = player_server.list_captures(root, identifier)
            return {"ok": True, "captures": [{"path": c["path"], "kind": c["kind"], "createdAt": c["createdAt"],
                                              "url": server.capture_url(identifier, c["id"])} for c in found]}
        except Exception as error:
            logger.exception("hermretro captures failed")
            return {"ok": False, "error": f"{type(error).__name__}: {error}", "captures": []}
    return captures


@rpc("capture_image")
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


@rpc("build")
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
        here = host._profile_identity()
        try:
            registry = host._registry()
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
