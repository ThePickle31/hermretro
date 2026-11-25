"""A conversation's lane in the broker: its engine worker, its project selection and writer lease,
and the one-game-per-conversation guard of the Build page.

Stdlib only and no Hermes imports: the broker runs as `python -m backend.broker`.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .. import library, setup
from ..system import paths
from .engine import EngineError, EngineProcess, sanitized_environment

DEFAULT_CALL_TIMEOUT = 900.0
# A recording started by a call runs for its duration (the engine's default when none is given), then takes up to the
# engine's 30 s to save.
RECORDING_DEFAULT = 180.0
RECORDING_SAVE = 30.0


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _same_folder(one: str | None, other: str | None) -> bool:
    return bool(one and other) and os.path.realpath(one) == os.path.realpath(other)


class Denied(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Lane:
    """One conversation's private engine worker and what the broker knows about it."""

    def __init__(self, owner: tuple[str, str]):
        self.owner = owner
        self.key = hashlib.sha256("\0".join(owner).encode()).hexdigest()[:16]
        self.start_lock = threading.Lock()
        self.engine: EngineProcess | None = None
        self.generation = 0
        self.selected_root: str | None = None
        self.selected_project_path: str | None = None
        self.sessions_seen: list[str] = []
        self.child_leases: dict[str, str] = {}
        self.inflight = 0
        self.inflight_writes = 0
        self.last_used = time.monotonic()
        self.last_write = 0.0
        self.live_surface = False  # browser preview or capture feed opened in this worker
        self.recording_until = 0.0  # monotonic: a recording a call started may run and save until then
        self.pending_notice: str | None = None
        # What the desktop panel shows. Memory only: it describes this worker's life, nothing more.
        self.activity: collections.deque = collections.deque(maxlen=80)
        self.current_tool: str | None = None
        self.last_frame: dict | None = None
        self.last_build: dict | None = None
        self.preview_url: str | None = None
        self.last_activity = 0.0
        # Told about every finished call (the broker records the game library through it).
        self.observer: Callable[..., None] | None = None

    def note_surface(self, tool: str, arguments: dict) -> None:
        """After a successful preview or capture call: whether a browser preview or capture feed is open, and until
        when a recording the call started may still run and save (a retiring broker lets it finish)."""
        if tool == "web_preview_close":
            self.live_surface, self.recording_until = False, 0.0
            return
        if tool not in ("web_preview", "device_capture"):
            return
        self.live_surface = True
        action = arguments.get("action")
        if action == "start_recording":
            asked = arguments.get("recordingDurationMs" if tool == "web_preview" else "durationMs")
            seconds = asked / 1000 if isinstance(asked, (int, float)) and asked > 0 else RECORDING_DEFAULT
            self.recording_until = max(self.recording_until, time.monotonic() + seconds + RECORDING_SAVE)
        elif action in ("stop_recording", "close"):
            self.recording_until = 0.0

    def remember(self, tool: str, kind: str, result: dict, seconds: float, arguments: dict | None = None) -> None:
        """Keep a short, display-only record of one finished call."""
        structured = result.get("structuredContent")
        structured = structured if isinstance(structured, dict) else {}
        failed = bool(result.get("isError")) or structured.get("success") is False
        now = time.time()
        entry = {"t": now, "tool": tool, "kind": kind, "ok": not failed, "seconds": round(seconds, 2)}
        for key in ("frame", "frames", "name"):
            if isinstance(structured.get(key), (int, str)):
                entry[key] = structured[key]
        if failed:
            message = structured.get("error") or next(
                (b.get("text") for b in result.get("content") or [] if b.get("type") == "text"), ""
            )
            entry["error"] = str(message)[:240]
        self.activity.append(entry)
        self.last_activity = now
        images = [b for b in result.get("content") or [] if b.get("type") == "image" and b.get("data")]
        if images:
            # A scaled contact sheet can be too large to keep: the frame moves on without a picture rather than
            # showing the previous one as current.
            image = images[-1]
            self.last_frame = {
                "t": now,
                "tool": tool,
                "frame": structured.get("frame"),
                "mimeType": image.get("mimeType") or "image/png",
                "data": image["data"] if len(image["data"]) < 400_000 else None,
            }
        if tool == "rom_build":
            rom = structured.get("romPath") or structured.get("outputPath")
            self.last_build = {
                "t": now,
                "ok": not failed,
                "seconds": round(seconds, 1),
                "rom": rom if isinstance(rom, str) else None,
                "sha256": structured.get("romSha256") or structured.get("sha256"),
                "error": entry.get("error"),
            }
        if tool == "web_preview" and not failed and isinstance(structured.get("url"), str):
            self.preview_url = structured["url"]
        elif tool == "web_preview_close" and not failed:
            self.preview_url = None
        if self.observer is not None:
            try:
                self.observer(self, tool, arguments or {}, structured, failed)
            except Exception:  # the library is bookkeeping; it must never fail a call
                pass


class LaneMixin:
    """The Broker's lane work: starting and stopping workers, writer leases and project selection."""

    # -- engine workers --------------------------------------------------------
    def new_engine(self, client_name: str) -> EngineProcess:
        # Re-read each start: setup may have prepared a copy since, or the engine changed under the copy (rebuilt here).
        selection = setup.select_engine(self.node if paths.node_usable(self.node) else None)
        if not selection["check"].get("verified"):
            raise Denied(
                "ENGINE_NOT_VERIFIED",
                "The bundled engine does not match its recorded manifest: "
                + (selection["check"].get("detail") or "unknown difference")
                + ". Reinstall the plugin.",
            )
        if not paths.node_usable(self.node):
            # A client replaces an idle broker in this state; this one stays for the games it still runs.
            raise Denied(
                "NODE_MISSING",
                f"The Node.js hermretro's game tools started with ({self.node}) is no longer installed. Finish or "
                "close the chats that are running games: the game tools restart with the current Node.js once "
                "no game is running, then try again.",
            )
        engine = EngineProcess(
            selection["root"],
            node=self.node,
            client_name=client_name,
            env=sanitized_environment(
                {
                    "PATH": os.pathsep.join([str(Path(self.node).parent), os.environ.get("PATH", "")]),
                    "GB_STUDIO_SETUP_ROOT": str(paths.setup_root()),
                }
            ),
        )
        engine.start()
        return engine

    def view_lane(self, profile, ids) -> tuple[Lane | None, str | None]:
        """The lane a desktop pane should show: the chat's own, or none. Never another chat's: its game, frame and
        build belong to that chat."""
        ids = {value for value in ids or [] if isinstance(value, str) and value}
        with self.table_lock:
            mine = [lane for lane in self.lanes.values() if lane.owner[0] == profile]
        lane = next((l for l in mine if l.owner[1] in ids or ids.intersection(l.sessions_seen)), None)
        return (lane, "chat") if lane is not None else (None, None)

    @staticmethod
    def _open_preview(engine: EngineProcess) -> tuple[dict | None, str | None]:
        """Ask the engine for the playable browser copy. Returns (result, None) or (None, why not)."""
        try:
            preview = engine.call_tool("web_preview", {}, timeout=DEFAULT_CALL_TIMEOUT)
        except EngineError as error:
            return None, str(error)[:240]
        structured = preview.get("structuredContent")
        structured = structured if isinstance(structured, dict) else {}
        if preview.get("isError") or structured.get("success") is False or not isinstance(structured.get("url"), str):
            return None, str(structured.get("error") or "The playable copy could not be built.")[:240]
        return preview, None

    def refresh_player(self, lane: Lane, engine: EngineProcess) -> dict:
        """After a successful project build, rebuild the playable browser copy so the player the
        user is watching can show this build.

        The engine replaces a running preview only when every open player tab acknowledges. When
        one does not, the engine keeps the old preview, still bound to the previous build, although
        the files behind it are already new: that player can no longer install to a Chromatic, and
        every later attempt fails the same way. So a failed replacement is followed by one clean
        close and reopen; if that fails too, the result says the player is stale."""
        previous = lane.preview_url
        started = time.time()
        preview, error = self._open_preview(engine)
        if error is not None and previous is not None:
            self.trace(event="player_refresh_failed", owner_key=lane.key, error=error[:200])
            try:
                closed = engine.call_tool("web_preview_close", {}, timeout=120)
                closed_ok = (
                    not closed.get("isError") and (closed.get("structuredContent") or {}).get("success") is not False
                )
            except EngineError:
                closed_ok = False
            if closed_ok:
                lane.live_surface = False
                preview, error = self._open_preview(engine)
        if error is not None:
            self.trace(event="player_refresh_failed", owner_key=lane.key, error=error[:200], final=True)
            return {"ready": False, "error": error, "stale": previous is not None}
        lane.remember("web_preview", "runtime", preview, time.time() - started)
        url = preview["structuredContent"]["url"]
        lane.live_surface = True
        moved = previous is not None and url != previous
        self.trace(
            event="player_refreshed",
            owner_key=lane.key,
            first=previous is None,
            moved=moved,
            seconds=round(time.time() - started, 2),
        )
        if lane.selected_root and not library.plays_game_rom(Path(lane.selected_root)):
            self.trace(event="player_plays_another_rom", owner_key=lane.key)
            return {"ready": False, "error": "The playable copy was made, but it does not play this build's ROM."}
        return {"ready": True, "url": url, "first": previous is None, "moved": moved}

    def ensure_engine(self, lane: Lane) -> EngineProcess:
        with lane.start_lock:
            if lane.engine is not None and lane.engine.alive():
                return lane.engine
            restarted = lane.engine is not None
            if restarted:
                lane.engine.close(grace=1.0)  # reap anything the dead worker left behind
            engine = self.new_engine("chromatic-studio")
            live, _pages = engine.list_tools()
            if canonical_hash(live) != self.pinned_hash:
                engine.close()
                raise Denied("ENGINE_PIN_MISMATCH", "Live engine contracts differ from the pinned baseline.")
            lane.engine = engine
            lane.generation += 1
            lane.live_surface = False
            self.trace(
                event="worker_started",
                owner_key=lane.key,
                engine_pid=engine.pid,
                engine_generation=lane.generation,
                ready_seconds=round(engine.ready_seconds or 0, 3),
            )
            if restarted and lane.selected_project_path:
                # The previous worker is gone, and with it the emulator, preview and held input.
                # Source selection is rebuildable from disk, so restore that and say what was lost.
                result = engine.call_tool("project_select", {"projectPath": lane.selected_project_path}, timeout=120)
                restored = not result.get("isError")
                if not restored:
                    self._release_root(lane)
                    lane.selected_root = lane.selected_project_path = None
                lane.pending_notice = (
                    "The engine worker for this conversation was restarted. "
                    + ("The project selection was restored. " if restored else "The project is no longer selected. ")
                    + "Any running emulator, browser preview and held buttons were reset; start them again if needed."
                )
                self.trace(event="worker_reselected", owner_key=lane.key, restored=restored)
            return engine

    def close_lane_engine(self, lane: Lane, reason: str) -> None:
        with lane.start_lock:
            engine = lane.engine
            if engine is None:
                return
            engine.close()
            self.trace(event="worker_closed", owner_key=lane.key, reason=reason)

    def close_lane_if_idle(self, lane: Lane) -> bool:
        """Close an idle worker unless a call has arrived for it. A call marks the lane used before
        it asks for the engine, and asking for the engine takes ``start_lock``: so either the call
        is seen here and the worker is kept, or the call waits and gets a fresh worker."""
        with lane.start_lock:
            with self.table_lock:
                idle_for = self.lane_idle * 4 if lane.live_surface else self.lane_idle
                if lane.inflight != 0 or time.monotonic() - lane.last_used < idle_for:
                    return False
            engine = lane.engine
            if engine is None:
                return False
            self._release_root(lane)  # the selection itself is kept and restored on the next call
            engine.close()
            lane.live_surface = False
            lane.preview_url = None
            self.trace(event="worker_closed", owner_key=lane.key, reason="idle")
            return True

    # -- project writer coordination ---------------------------------------------
    def _release_root(self, lane: Lane) -> None:
        with self.table_lock:
            if lane.selected_root and self.writer_leases.get(lane.selected_root) == lane.owner:
                del self.writer_leases[lane.selected_root]

    def _sync_selection(self, lane: Lane) -> None:
        status = lane.engine.call_tool("session_status", {}, timeout=60)
        self._apply_selection(lane, status.get("structuredContent") or {})

    def _apply_selection(self, lane: Lane, data: dict) -> None:
        root = os.path.realpath(data["projectRoot"]) if data.get("projectRoot") else None
        with self.table_lock:
            if root != lane.selected_root:
                self._release_root(lane)
                lane.selected_root = root
            lane.selected_project_path = data.get("projectPath") if root else None
            if root:
                self.writer_leases.setdefault(root, lane.owner)

    def holds_writer(self, lane: Lane) -> bool:
        with self.table_lock:
            return bool(lane.selected_root) and self.writer_leases.get(lane.selected_root) == lane.owner

    def acquire_writer(self, lane: Lane) -> None:
        """Give this lane the writer lease, or refuse while another conversation is actively writing.

        A holder that has no write in flight and has been quiet for the handoff interval yields.
        The engine's own revision checks remain the second guard against stale writes."""
        with self.table_lock:
            root = lane.selected_root
            if not root:
                return  # the engine reports "no project selected" itself
            holder_owner = self.writer_leases.get(root)
            if holder_owner in (None, lane.owner):
                self.writer_leases[root] = lane.owner
                # Count the write as begun here, under the same lock that decides handoffs: the
                # in-flight counter is only raised later, and a quiet holder must not lose the lease
                # in between.
                lane.last_write = time.monotonic()
                return
            holder = self.lanes.get(holder_owner)
            quiet = holder is None or (
                holder.inflight_writes == 0 and time.monotonic() - holder.last_write >= self.writer_handoff_idle
            )
            if quiet:
                self.writer_leases[root] = lane.owner
                lane.last_write = time.monotonic()
                self.trace(
                    event="writer_handoff",
                    root_hash=hashlib.sha256(root.encode()).hexdigest()[:12],
                    to_owner=lane.key,
                    from_owner=holder.key if holder else None,
                )
                return
        raise Denied(
            "PROJECT_WRITER_BUSY",
            "Another conversation is editing or building this project right now. Wait for it to "
            "finish, or continue the work in that conversation. Nothing was changed.",
        )

    # -- one game, one conversation (the Build page) --------------------------------
    def _selection_target(self, lane: Lane, tool: str, arguments: dict) -> str | None:
        """The project root a selector would work on: the selected project, or the new folder, resolved as the engine
        resolves it (trimmed; a relative path against the project the conversation has open)."""
        path = arguments.get("projectPath") if tool == "project_select" else arguments.get("destinationPath")
        if not isinstance(path, str) or not path.strip():
            return None
        path = os.path.expanduser(path.strip())
        if not os.path.isabs(path):
            if not lane.selected_root:
                raise Denied(
                    "INVALID_ARGUMENTS",
                    f"{'projectPath' if tool == 'project_select' else 'destinationPath'} must be an absolute path "
                    "here. Nothing was changed.",
                )
            path = os.path.join(lane.selected_root, path)
        real = os.path.realpath(path)
        return os.path.dirname(real) if tool == "project_select" and os.path.isfile(real) else real

    def _project_holding(self, target: str) -> str | None:
        """The game folder ``target`` would be made inside: a library game's existing folder above it, or a folder
        above it holding a GB Studio project (one another chat is making right now is not in the library yet).
        ``target`` itself is the engine's to refuse: it only makes a project in a new folder."""
        game = self.games.game_around(target)
        if game is not None:
            return os.path.realpath(game["projectRoot"])
        for folder in Path(target).parents:
            try:
                if any(folder.glob("*.gbsproj")):
                    return str(folder)
            except OSError:
                continue
        return None

    def guard_selection(self, owner: tuple[str, str], lane: Lane, tool: str, arguments: dict) -> None:
        """A library game is opened and edited only from its own conversation: a game's conversation works on that game
        only, a New Game conversation only makes its new project, and any other chat makes new projects (each becomes
        that chat's game) but opens no library game."""
        profile, conversation = owner
        kind, bound = self.games.binding_for(profile, [conversation, *lane.sessions_seen])
        target = self._selection_target(lane, tool, arguments)
        if kind == "game":
            mine = os.path.realpath(bound["projectRoot"])
            title = bound.get("title") or os.path.basename(mine)
            if tool == "project_select" and target == mine:
                return
            if not os.path.isdir(mine):
                raise Denied(
                    "GAME_FOLDER_MISSING",
                    f"This conversation belongs to the game \"{title}\", but its folder {mine} no longer "
                    "exists (moved or deleted). Tell the user; this conversation can continue once the "
                    "folder is back where it was. Nothing was changed.",
                )
            what = "create another project" if tool != "project_select" else "open another project"
            raise Denied(
                "ONE_GAME_PER_CONVERSATION",
                f"This conversation belongs to the game \"{title}\" ({mine}), and each hermretro game "
                f"has its own conversation, so it cannot {what}. Tell the user: to make a different "
                "game, start one with New Game on the hermretro Build page; to work on another game, "
                "open that game on the Build page. Nothing was changed.",
            )
        if tool != "project_select":
            holder = self._project_holding(target) if target else None
            if holder is not None:
                where = os.path.realpath(paths.games_dir())
                inside = where == holder or where.startswith(holder.rstrip(os.sep) + os.sep)
                raise Denied(
                    "INSIDE_ANOTHER_GAME",
                    f"{target} is inside the game folder {holder}. A new game gets a folder of its own. "
                    + (
                        "hermretro's games folder is itself inside that folder, so tell the user; do not make the "
                        "game there."
                        if inside
                        else "Leave destinationPath out to make it in the hermretro games folder."
                    )
                    + " Nothing was changed.",
                )
            return
        if kind == "pending":
            # A New Game conversation makes its own project: one it opened would stay selected after the new project
            # claims the conversation, and its edits and builds would go there.
            raise Denied(
                "NEW_GAME_ONLY",
                "This conversation is for a new game, so it opens no existing project. Create the new game's "
                "project with chromatic_project_create or chromatic_project_create_blank. To work on an existing "
                "game, tell the user to open it on the hermretro Build page. Nothing was changed.",
            )
        # The game itself, or the game whose folder holds it (a project inside a game's folder is that game's files).
        entry = (self.games.game_for_root(target) or self.games.game_around(target)) if target else None
        if isinstance(entry, dict):
            title = entry.get("title") or os.path.basename(target)
            raise Denied(
                "GAME_CHAT_ONLY",
                f"\"{title}\" is a hermretro game, and a game is worked on only in its own conversation. Tell the "
                f"user to open \"{title}\" on the hermretro Build page and continue there. Nothing was changed.",
            )

    def select_bound_game(self, lane: Lane, engine: EngineProcess) -> None:
        """A game's conversation works on its game: selected for it when nothing is, and again when another project
        is (a New Game conversation whose new project claimed it after it had opened something else). When its worker
        still has another project open, nothing runs for it."""
        kind, bound = self.games.binding_for(lane.owner[0], [lane.owner[1], *lane.sessions_seen])
        if kind != "game" or not os.path.isdir(bound.get("projectRoot") or ""):
            return
        root = bound["projectRoot"]
        if not _same_folder(lane.selected_root, root) and getattr(lane, "auto_select_failed", None) != lane.generation:
            self._select_game(lane, engine, bound)  # a failure is not repeated on every call with this worker
        if lane.selected_root and not _same_folder(lane.selected_root, root):
            title = bound.get("title") or os.path.basename(root)
            raise Denied(
                "ONE_GAME_PER_CONVERSATION",
                f"This conversation belongs to the game \"{title}\" ({root}), but its game worker has "
                f"{lane.selected_root} open and could not switch, so nothing runs here. Tell the user; the worker is "
                "replaced once this conversation has been idle for a while. Nothing was changed.",
            )

    def _select_game(self, lane: Lane, engine: EngineProcess, bound: dict) -> None:
        root = bound["projectRoot"]
        project = library.project_file(Path(root))
        try:
            result = engine.call_tool("project_select", {"projectPath": str(project or root)}, timeout=60)
            if result.get("isError"):
                raise RuntimeError("the engine refused the selection")
        except Exception as error:
            lane.auto_select_failed = lane.generation
            self.trace(event="auto_select_failed", owner_key=lane.key, error=f"{type(error).__name__}: {error}"[:200])
            return
        try:
            self._sync_selection(lane)
        except Exception as error:
            # The selection itself succeeded: take the root from its result, as call() does.
            self.trace(event="selection_sync_failed", owner_key=lane.key, error=str(error)[:200])
            selected = result.get("structuredContent")
            if isinstance(selected, dict) and selected.get("projectRoot"):
                self._apply_selection(lane, selected)
        self.trace(event="auto_select", owner_key=lane.key)
        title = bound.get("title") or os.path.basename(root)
        notice = (
            f"hermretro selected this conversation's game \"{title}\" ({root}) for you: this "
            "conversation works on that game only."
        )
        lane.pending_notice = f"{lane.pending_notice} {notice}" if lane.pending_notice else notice
