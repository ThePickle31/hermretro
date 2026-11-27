"""A conversation's lane in the broker: its engine worker, its project selection and writer lease (the
one-game-per-conversation guard of the Build page is ``selection.py``).

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
# Arguments that name a file an engine call writes; checked against the games inside this chat's game (guard_ownership).
WRITE_PATH_KEYS = ("outputPath", "assetPath", "atlasPath", "recipePath", "backgroundPath", "recordingPath")


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
        # A game installed without its source: the folder its worker must have as its workspace (set per call), and
        # the one the running worker was started with.
        self.rom_workspace: str | None = None
        self.engine_workspace: str | None = None
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

    def remember(
        self,
        tool: str,
        kind: str,
        result: dict,
        seconds: float,
        arguments: dict | None = None,
        sources_before: str | None = None,
    ) -> None:
        """Keep a short, display-only record of one finished call; the observer also gets ``sources_before`` (a
        build's source digest from before it started)."""
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
                self.observer(self, tool, arguments or {}, structured, failed, sources_before)
            except Exception:  # the library is bookkeeping; it must never fail a call
                pass


class LaneMixin:
    """The Broker's lane work: starting and stopping workers, writer leases and project selection."""

    # -- engine workers --------------------------------------------------------
    def new_engine(self, client_name: str, workspace: str | None = None) -> EngineProcess:
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
        # A worker in a prepared copy holds its lease for as long as it runs, so the copy is never removed under it.
        lease = setup.hold_copy(selection["root"]) if selection["prepared"] else None
        try:
            engine = EngineProcess(
                selection["root"],
                node=self.node,
                client_name=client_name,
                env=sanitized_environment(
                    {
                        "PATH": os.pathsep.join([str(Path(self.node).parent), os.environ.get("PATH", "")]),
                        "GB_STUDIO_SETUP_ROOT": str(paths.setup_root()),
                        # A game installed without its source: its folder is the worker's whole authorization.
                        **({"GB_STUDIO_WORKSPACE_ROOT": workspace} if workspace else {}),
                    }
                ),
                keep_fds=() if lease is None else (lease,),
            )
            engine.start()
        finally:
            if lease is not None:
                os.close(lease)  # the worker holds its own
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
            if lane.engine is not None and lane.engine.alive() and lane.engine_workspace == lane.rom_workspace:
                return lane.engine
            restarted = lane.engine is not None and lane.engine_workspace == lane.rom_workspace
            if lane.engine is not None:
                lane.engine.close(grace=1.0)  # reap anything the dead worker left behind, or one with another workspace
            if lane.engine is not None and not restarted:  # the new worker opens nothing the old one had
                self._release_root(lane)
                lane.selected_root = lane.selected_project_path = None
            engine = self.new_engine("chromatic-studio", lane.rom_workspace)
            lane.engine_workspace = lane.rom_workspace
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
                # Source selection is rebuildable from disk, so restore that and say what was lost; never a game
                # this chat no longer owns (Stop editing, or another chat's).
                try:
                    owned = self.ownership_refusal(lane) is None
                except Exception:
                    owned = False
                result = (
                    engine.call_tool("project_select", {"projectPath": lane.selected_project_path}, timeout=120)
                    if owned
                    else {"isError": True}
                )
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
