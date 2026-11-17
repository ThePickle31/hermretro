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

from .. import library
from ..system import paths
from .engine import EngineError, EngineProcess, sanitized_environment

DEFAULT_CALL_TIMEOUT = 900.0


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
        if images and len(images[-1]["data"]) < 400_000:
            self.last_frame = {
                "t": now,
                "tool": tool,
                "frame": structured.get("frame"),
                "mimeType": images[-1].get("mimeType") or "image/png",
                "data": images[-1]["data"],
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
        selection = paths.select_engine()  # re-read each start: setup may have prepared a copy since
        if not selection["check"].get("verified"):
            raise Denied(
                "ENGINE_NOT_VERIFIED",
                "The bundled engine does not match its recorded manifest: "
                + (selection["check"].get("detail") or "unknown difference")
                + ". Reinstall the plugin.",
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
        """The lane a desktop pane should show: the chat's own, else the most recently active."""
        ids = {value for value in ids or [] if isinstance(value, str) and value}
        with self.table_lock:
            mine = [lane for lane in self.lanes.values() if lane.owner[0] == profile]
        lane = next((l for l in mine if l.owner[1] in ids or ids.intersection(l.sessions_seen)), None)
        if lane is not None:
            return lane, "chat"
        recent = max(mine, key=lambda l: l.last_activity, default=None)
        return (recent, "recent") if recent is not None and recent.last_activity else (None, None)

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
    def _selection_target(self, tool: str, arguments: dict) -> str | None:
        """The project root a selector would work on: the selected project, or the new folder."""
        path = arguments.get("projectPath") if tool == "project_select" else arguments.get("destinationPath")
        if not isinstance(path, str) or not path.strip():
            return None
        real = os.path.realpath(os.path.expanduser(path))
        return os.path.dirname(real) if tool == "project_select" and os.path.isfile(real) else real

    def guard_selection(
        self, owner: tuple[str, str], lane: Lane, tool: str, arguments: dict, continue_here: bool
    ) -> None:
        """A game's conversation works on that game only; another conversation that opens a game with
        its own conversation is warned first (it may continue once the user confirms)."""
        profile, conversation = owner
        kind, bound = self.games.binding_for(profile, [conversation, *lane.sessions_seen])
        target = self._selection_target(tool, arguments)
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
        entry = self.games.game_for_root(target) if target and tool == "project_select" else None
        session = entry.get("session") if isinstance(entry, dict) else None
        if not isinstance(session, dict):
            return
        title = entry.get("title") or os.path.basename(target)
        if kind == "pending":
            raise Denied(
                "GAME_HAS_CONVERSATION",
                f"\"{title}\" already has its own conversation on the hermretro Build page, so this new "
                "game's conversation cannot take it over. Create a new project for the new game instead, "
                "or tell the user to open that game on the Build page. Nothing was changed.",
            )
        if continue_here:
            self.trace(event="continued_outside_game_conversation", owner_key=lane.key)
            return
        raise Denied(
            "GAME_HAS_CONVERSATION",
            f"\"{title}\" has its own conversation on the hermretro Build page. Changes made here will "
            "not be in that game's conversation history. Tell the user this and ask whether to continue "
            "here anyway or open the game on the Build page. Only if the user says to continue here, call "
            "chromatic_project_select again with the same projectPath and continueInThisChat set to "
            "true. Nothing was changed.",
        )

    def select_bound_game(self, lane: Lane, engine: EngineProcess) -> None:
        """A game's conversation starts with its game selected, so the agent never has to ask which."""
        if lane.selected_root:
            return
        kind, bound = self.games.binding_for(lane.owner[0], [lane.owner[1], *lane.sessions_seen])
        if kind != "game" or not os.path.isdir(bound.get("projectRoot") or ""):
            return
        if getattr(lane, "auto_select_failed", None) == lane.generation:
            return  # tried with this worker already; do not repeat a slow failure on every call
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
