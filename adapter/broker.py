"""The one authority for hermretro on this machine.

A single elected process per user. Model tools, desktop RPC and every other
caller are clients on a user-only Unix socket, so there is exactly one place
that owns engine workers, project writer coordination and hardware admission.

Each trusted owner (Hermes profile + durable conversation) gets a private,
lazily started engine worker. The engine binds a worker to one project root,
so a lane is "conversation -> its project worker".

Stdlib only and no Hermes imports: this runs as `python -m adapter.broker`.
"""
from __future__ import annotations

import argparse
import fcntl
import collections
import hashlib
import json
import os
import secrets
import signal
import socket
import socketserver
import struct
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from . import games, onboarding, paths
from .engine import EngineError, EngineProcess, sanitized_environment
from . import provision

HARDWARE = frozenset({"device", "setup", "flash", "play", "device_capture"})
PREPARE = frozenset({"toolchain_prepare"})
SELECTORS = frozenset({"project_select", "project_create", "project_create_blank"})
PARENT_ONLY = frozenset({"emulator_close", "web_preview_close"}) | SELECTORS | PREPARE | HARDWARE


def selects_project(tool: str, arguments: dict) -> bool:
    """Whether a successful call changed which project the worker has selected. The create tools
    return the new project's root either way, but only select it when asked to."""
    return tool == "project_select" or (tool in SELECTORS and arguments.get("select") is True)
RUNTIME_PREFIXES = ("emulator_", "web_preview")
DEFAULT_CALL_TIMEOUT = 900.0


def _env_seconds(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _prepare_failure(result: dict, structured: dict) -> str:
    """One readable reason a toolchain_prepare call did not finish: the first failed component's
    error, else the engine's message, else its text."""
    run = structured.get("result")
    for component in (run.get("components") or []) if isinstance(run, dict) else []:
        if isinstance(component, dict) and component.get("status") in ("failed", "blocked"):
            error = component.get("error")
            message = error.get("message") if isinstance(error, dict) else error or component.get("reason")
            if message:
                return f"{component.get('id')}: {message}"
    if isinstance(structured.get("message"), str) and structured["message"]:
        return structured["message"]
    text = " ".join(str(block.get("text", "")) for block in result.get("content") or []
                    if isinstance(block, dict) and block.get("type") == "text")
    return text or "The game tools could not be prepared."


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
                (b.get("text") for b in result.get("content") or [] if b.get("type") == "text"), "")
            entry["error"] = str(message)[:240]
        self.activity.append(entry)
        self.last_activity = now
        images = [b for b in result.get("content") or [] if b.get("type") == "image" and b.get("data")]
        if images and len(images[-1]["data"]) < 400_000:
            self.last_frame = {"t": now, "tool": tool, "frame": structured.get("frame"),
                               "mimeType": images[-1].get("mimeType") or "image/png", "data": images[-1]["data"]}
        if tool == "rom_build":
            rom = structured.get("romPath") or structured.get("outputPath")
            self.last_build = {"t": now, "ok": not failed, "seconds": round(seconds, 1),
                               "rom": rom if isinstance(rom, str) else None,
                               "sha256": structured.get("romSha256") or structured.get("sha256"),
                               "error": entry.get("error")}
        if tool == "web_preview" and not failed and isinstance(structured.get("url"), str):
            self.preview_url = structured["url"]
        elif tool == "web_preview_close" and not failed:
            self.preview_url = None
        if self.observer is not None:
            try:
                self.observer(self, tool, arguments or {}, structured, failed)
            except Exception:  # the library is bookkeeping; it must never fail a call
                pass


class Broker:
    def __init__(self, state_dir: Path, node: str):
        self.state_dir = state_dir
        self.node = node
        pinned = json.loads(paths.PINNED_TOOLS.read_text())["tools"]
        self.pinned_hash = canonical_hash(pinned)
        self.tools = {t["name"]: t for t in pinned}
        self.read_only = {n for n, t in self.tools.items() if t.get("annotations", {}).get("readOnlyHint")}
        self.generation = secrets.token_hex(8)
        self.token = secrets.token_hex(32)
        self.engine_check = paths.verify_engine()
        self.games = games.Registry(paths.library_dir_for(state_dir))
        self.lanes: dict[tuple[str, str], Lane] = {}
        self.writer_leases: dict[str, tuple[str, str]] = {}
        self.table_lock = threading.RLock()
        self.hardware_lock = threading.Lock()
        self.prepare_lock = threading.Lock()
        # The desktop page's own toolchain install (op install_start / install_status).
        self.install: dict = {"state": "idle"}
        self.install_lock = threading.Lock()
        self.install_engine = None
        self.trace_path = state_dir / "trace.jsonl"
        self.trace_lock = threading.Lock()
        self.stopping = threading.Event()
        self.connections = 0
        self.connections_lock = threading.Lock()
        self.last_activity = time.monotonic()
        self.writer_handoff_idle = _env_seconds("HERMRETRO_WRITER_HANDOFF_SECONDS", 45)
        self.lane_idle = _env_seconds("HERMRETRO_LANE_IDLE_SECONDS", 30 * 60)
        self.broker_idle = _env_seconds("HERMRETRO_BROKER_IDLE_SECONDS", 10 * 60)

    # -- evidence (names and outcomes only; never tool arguments or results) ----
    def trace(self, **record) -> None:
        record["t"] = round(time.time(), 3)
        record["broker_generation"] = self.generation
        try:
            with self.trace_lock:
                if self.trace_path.exists() and self.trace_path.stat().st_size > 5 * 1024 * 1024:
                    self.trace_path.replace(self.trace_path.with_suffix(".jsonl.1"))
                with self.trace_path.open("a") as handle:
                    handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        except OSError:
            pass

    # -- identity ------------------------------------------------------------
    @staticmethod
    def owner_of(request: dict) -> tuple[str, str]:
        owner = request.get("owner")
        if not isinstance(owner, dict):
            raise Denied("IDENTITY_REQUIRED",
                         "No trusted conversation identity came with this call. Call Chromatic tools "
                         "directly from the conversation, not from inside execute_code.")
        values = []
        for label in ("profile", "conversation_id"):
            value = owner.get(label)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise Denied("IDENTITY_REQUIRED",
                             f"Trusted owner field '{label}' is missing. Call Chromatic tools directly "
                             "from the conversation, not from inside execute_code.")
            values.append(value)
        return values[0], values[1]

    def lane_for(self, owner: tuple[str, str], create: bool) -> Lane | None:
        with self.table_lock:
            lane = self.lanes.get(owner)
            if lane is None and create:
                lane = self.lanes[owner] = Lane(owner)
                lane.observer = self.record_game
            return lane

    def record_game(self, lane: Lane, tool: str, arguments: dict, structured: dict, failed: bool) -> None:
        """Keep the user's game library current: selections, creations, builds and previews."""
        if tool not in games.SELECTORS and tool not in ("rom_build", "web_preview"):
            return
        try:
            self.games.observe(tool, arguments, structured, failed, lane_root=lane.selected_root,
                               conversation_id=lane.owner[1], sessions_seen=lane.sessions_seen,
                               profile=lane.owner[0])
        except Exception as error:
            self.trace(event="library_record_failed", tool=tool, error=f"{type(error).__name__}: {error}"[:200])

    # -- engine workers --------------------------------------------------------
    def new_engine(self, client_name: str) -> EngineProcess:
        selection = paths.select_engine()  # re-read each start: setup may have prepared a copy since
        if not selection["check"].get("verified"):
            raise Denied("ENGINE_NOT_VERIFIED",
                         "The bundled engine does not match its recorded manifest: "
                         + (selection["check"].get("detail") or "unknown difference") + ". Reinstall the plugin.")
        engine = EngineProcess(selection["root"], node=self.node, client_name=client_name,
                               env=sanitized_environment({
                                   "PATH": os.pathsep.join([str(Path(self.node).parent), os.environ.get("PATH", "")]),
                                   "GB_STUDIO_SETUP_ROOT": str(paths.setup_root())}))
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
                closed_ok = not closed.get("isError") and (closed.get("structuredContent") or {}).get("success") is not False
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
        self.trace(event="player_refreshed", owner_key=lane.key, first=previous is None, moved=moved,
                   seconds=round(time.time() - started, 2))
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
            self.trace(event="worker_started", owner_key=lane.key, engine_pid=engine.pid,
                       engine_generation=lane.generation, ready_seconds=round(engine.ready_seconds or 0, 3))
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
                    + "Any running emulator, browser preview and held buttons were reset; start them again if needed.")
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
            quiet = holder is None or (holder.inflight_writes == 0
                                       and time.monotonic() - holder.last_write >= self.writer_handoff_idle)
            if quiet:
                self.writer_leases[root] = lane.owner
                lane.last_write = time.monotonic()
                self.trace(event="writer_handoff", root_hash=hashlib.sha256(root.encode()).hexdigest()[:12],
                           to_owner=lane.key, from_owner=holder.key if holder else None)
                return
        raise Denied("PROJECT_WRITER_BUSY",
                     "Another conversation is editing or building this project right now. Wait for it to "
                     "finish, or continue the work in that conversation. Nothing was changed.")

    # -- admission -----------------------------------------------------------------
    def classify(self, tool: str) -> str:
        if tool in HARDWARE:
            return "hardware"
        if tool in PREPARE:
            return "prepare"
        if tool in SELECTORS:
            return "select"
        if tool in self.read_only:
            return "read"
        if tool.startswith(RUNTIME_PREFIXES):
            return "runtime"
        return "project-write"

    def call(self, request: dict) -> dict:
        owner = self.owner_of(request)
        tool = request.get("tool")
        arguments = request.get("arguments") or {}
        origin = request.get("origin") or {}
        policy = request.get("policy") or {}
        if not isinstance(tool, str) or tool not in self.tools:
            raise Denied("UNKNOWN_TOOL", f"'{tool}' is not in the pinned contract inventory.")
        if not isinstance(arguments, dict):
            raise Denied("INVALID_ARGUMENTS", "Tool arguments must be an object.")
        kind = self.classify(tool)
        delegated = bool(origin.get("delegated"))
        if kind == "hardware" and not policy.get("hardware_enabled"):
            raise Denied("HARDWARE_DISABLED",
                         "Chromatic hardware tools are turned off. The user can turn them on in "
                         "Settings > Plugins > hermretro (hardware_enabled). Do not retry until they do.")
        lane = self.lane_for(owner, create=not delegated)
        if lane is None:
            raise Denied("NO_PARENT_LANE", "A delegated subagent cannot start Chromatic work for a conversation.")
        if delegated:
            task_id = origin.get("task_id") or origin.get("session_id")
            if tool in PARENT_ONLY:
                raise Denied("PARENT_ONLY", f"A delegated subagent may not call {tool}. "
                                            "Do this from the main conversation.")
            if kind != "read" and lane.child_leases.get(str(task_id)) != "write":
                raise Denied("LEASE_REQUIRED", "Delegated subagents can inspect a Chromatic project but not "
                                               "change it or drive its emulator. Do this from the main conversation.")
        session_id = origin.get("session_id")
        if isinstance(session_id, str) and session_id and not delegated and session_id not in lane.sessions_seen:
            lane.sessions_seen.append(session_id)
            del lane.sessions_seen[:-16]

        with self.table_lock:
            lane.last_used = time.monotonic()  # before the engine is fetched: see close_lane_if_idle
        engine = self.ensure_engine(lane)
        writes = kind == "project-write"
        if writes:
            self.acquire_writer(lane)
        guard = self.hardware_lock if kind == "hardware" else self.prepare_lock if kind == "prepare" else None
        if guard is not None and not guard.acquire(blocking=False):
            raise Denied("OPERATION_IN_PROGRESS",
                         "Another hardware or setup operation is already running on this machine. Wait for it "
                         "to finish and check its original status; do not start a replacement.")
        base = dict(owner_key=lane.key, tool=tool, kind=kind, engine_pid=engine.pid,
                    engine_generation=lane.generation, delegated=delegated,
                    client_pid=request.get("_client_pid"))
        if kind == "prepare":
            # First install: start from another install's verified download cache when there is one.
            try:
                seeded = provision.seed_toolchain_cache()
            except Exception as error:  # reuse is an optimisation; never let it block setup
                seeded = {"seeded": False, "reason": f"{type(error).__name__}: {error}"}
            self.trace(event="toolchain_cache_seed", **seeded)
        started = time.time()
        with self.table_lock:
            lane.inflight += 1
            lane.inflight_writes += int(writes)
            lane.last_used = time.monotonic()
            if writes:
                lane.last_write = time.monotonic()
        self.trace(event="dispatch", **base)
        lane.current_tool = tool
        try:
            try:
                result = engine.call_tool(tool, arguments, timeout=float(request.get("timeout") or DEFAULT_CALL_TIMEOUT))
            except EngineError as error:
                self.trace(event="outcome_unknown", error=str(error)[:300], **base)
                return {"ok": False, "dispatched": True, "outcome": "unknown", "error": str(error),
                        "engine_alive": engine.alive()}
            if kind == "select" and not result.get("isError"):
                try:
                    self._sync_selection(lane)
                except Exception as error:
                    # The selection itself succeeded. Do not report it as failed, and do not leave
                    # this conversation writing without a lease: take the root from the result.
                    self.trace(event="selection_sync_failed", error=str(error)[:200], **base)
                    selected = result.get("structuredContent")
                    if selects_project(tool, arguments) and isinstance(selected, dict) \
                            and selected.get("projectRoot"):
                        self._apply_selection(lane, selected)
            if tool in ("web_preview", "device_capture") and not result.get("isError"):
                lane.live_surface = True
            elif tool == "web_preview_close" and not result.get("isError"):
                lane.live_surface = False
        finally:
            if guard is not None:
                guard.release()
            with self.table_lock:
                lane.inflight -= 1
                lane.inflight_writes -= int(writes)
                lane.last_used = time.monotonic()
                if writes:
                    lane.last_write = time.monotonic()
                if lane.inflight == 0:
                    lane.current_tool = None
        try:
            lane.remember(tool, kind, result, time.time() - started, arguments)
        except Exception as error:  # display bookkeeping must never fail a call
            self.trace(event="activity_record_failed", error=str(error)[:200])
        player = None
        if tool == "rom_build" and policy.get("live_player") and not delegated \
                and "sourcePath" not in arguments and not result.get("isError") \
                and (result.get("structuredContent") or {}).get("success") is not False:
            player = self.refresh_player(lane, engine)
        images = sum(1 for block in result.get("content", []) if block.get("type") == "image")
        self.trace(event="completed", seconds=round(time.time() - started, 3),
                   is_error=bool(result.get("isError")), image_blocks=images, **base)
        notice, lane.pending_notice = lane.pending_notice, None
        answer = {"ok": True, "dispatched": True, "result": result, "notice": notice, "lane": self.lane_info(lane)}
        if player is not None:
            answer["player"] = player
        return answer

    def lane_info(self, lane: Lane) -> dict:
        return {"owner_key": lane.key, "engine_pid": lane.engine.pid if lane.engine else None,
                "engine_generation": lane.generation, "selected_root": lane.selected_root,
                "writer": self.holds_writer(lane), "sessions_seen": list(lane.sessions_seen)}

    # -- the desktop page's toolchain install ------------------------------------------
    def install_running(self) -> bool:
        with self.install_lock:
            return self.install.get("state") == "running"

    def start_install(self) -> dict:
        """Prepare the game toolchain for the desktop page, without a chat. Runs the engine's own
        toolchain_prepare in a throwaway worker on a background thread; install_status reports it."""
        with self.install_lock:
            if self.install.get("state") == "running":
                return dict(self.install)
            if not self.prepare_lock.acquire(blocking=False):
                raise Denied("OPERATION_IN_PROGRESS",
                             "Another setup operation is already running on this machine (probably in a chat). "
                             "Wait for it to finish; this page moves on when the tools are verified.")
            try:
                self.install = {"state": "running", "started_at": time.time(), "finished_at": None, "error": None,
                                "code": None, "seeded": None,
                                "baseline_bytes": onboarding.directory_bytes(paths.setup_root())}
                snapshot = dict(self.install)
                threading.Thread(target=self._run_install, name="hermretro-install", daemon=True).start()
            except BaseException as error:
                # Never leave the setup lock held, or a "running" install nobody runs.
                self.prepare_lock.release()
                self.install = {"state": "failed", "started_at": None, "finished_at": time.time(),
                                "code": "INSTALL_ERROR", "error": f"{type(error).__name__}: {error}"[:800]}
                raise
        self.trace(event="install_started")
        return snapshot

    def _run_install(self) -> None:
        engine = None
        outcome: dict = {"state": "failed", "error": None, "code": None}
        try:
            try:
                seeded = provision.seed_toolchain_cache()
            except Exception as error:  # reuse is an optimisation; never let it block setup
                seeded = {"seeded": False, "reason": f"{type(error).__name__}: {error}"}
            self.trace(event="toolchain_cache_seed", **seeded)
            with self.install_lock:
                self.install["seeded"] = bool(seeded.get("seeded"))
                if seeded.get("seeded"):
                    # The copied cache is not a download: count only what arrives after it.
                    self.install["baseline_bytes"] = onboarding.directory_bytes(paths.setup_root())
            engine = self.new_engine("chromatic-studio-install")
            self.install_engine = engine   # close_all stops it if the broker stops mid-install
            result = engine.call_tool("toolchain_prepare", {"components": ["build", "emulator"]}, timeout=1800)
            structured = result.get("structuredContent")
            structured = structured if isinstance(structured, dict) else {}
            if result.get("isError") or structured.get("success") is not True:
                outcome.update(code=str(structured.get("stage") or "PREPARE_FAILED").upper(),
                               error=_prepare_failure(result, structured)[:800])
            else:
                outcome = {"state": "done", "error": None, "code": None}
        except Denied as denial:
            outcome.update(code=denial.code, error=str(denial))
        except EngineError as error:
            outcome.update(code="ENGINE_ERROR", error=str(error)[:800])
        except Exception as error:  # surface, never hide
            outcome.update(code="INSTALL_ERROR", error=f"{type(error).__name__}: {error}"[:800])
        finally:
            if engine is not None:
                engine.close()
            self.install_engine = None
            self.prepare_lock.release()
            with self.install_lock:
                self.install.update(outcome, finished_at=time.time())
            self.last_activity = time.monotonic()
            self.trace(event="install_finished", state=outcome["state"], code=outcome.get("code"))

    def install_status(self) -> dict:
        with self.install_lock:
            state = dict(self.install)
        return onboarding.progress(state, paths.setup_root())

    # -- control operations ---------------------------------------------------------
    def control(self, request: dict) -> dict:
        op = request.get("op")
        if op == "install_start":
            self.start_install()
            return {"ok": True, "install": self.install_status()}
        if op == "install_status":
            return {"ok": True, "install": self.install_status()}
        if op == "stats":
            with self.table_lock:
                lanes = [{**self.lane_info(l), "alive": bool(l.engine and l.engine.alive()),
                          "inflight": l.inflight, "child_leases": dict(l.child_leases)} for l in self.lanes.values()]
                leases = {root: hashlib.sha256("\0".join(o).encode()).hexdigest()[:16]
                          for root, o in self.writer_leases.items()}
            return {"ok": True, "pid": os.getpid(), "broker_generation": self.generation,
                    "lanes": lanes, "writer_leases": leases}
        if op == "shutdown":
            with self.table_lock:
                busy = any(l.inflight or (l.engine and l.engine.alive()) for l in self.lanes.values())
            if (busy or self.install_running()) and not request.get("force"):
                raise Denied("BUSY", "Conversations still have live Chromatic workers.")
            self.stopping.set()
            return {"ok": True}
        if op == "doctor":
            arguments = {"tasks": ["authoring", "projectBuild", "cBuild", "play", "desktop"]}
            if request.get("probe"):
                arguments["probes"] = ["cli-version", "gbdk-version", "emulator-import"]
            engine = self.new_engine("chromatic-studio-doctor")
            try:
                result = engine.call_tool("toolchain_doctor", arguments, timeout=180)
            finally:
                engine.close()
            return {"ok": True, "result": result}
        if op == "activity":
            # What the desktop panel draws for one chat. Memory only: no engine call, no worker start.
            lane, matched = self.view_lane(request.get("profile"), request.get("ids"))
            if lane is None:
                return {"ok": True, "lane": None, "matched": None}
            return {"ok": True, "matched": matched,
                    "lane": {"project_root": lane.selected_root,
                             "project_name": Path(lane.selected_root).name if lane.selected_root else None,
                             "alive": bool(lane.engine and lane.engine.alive()),
                             "busy": lane.inflight > 0, "current_tool": lane.current_tool,
                             "preview_url": lane.preview_url},
                    "events": list(lane.activity)[-int(request.get("limit") or 40):],
                    "frame": lane.last_frame, "build": lane.last_build}
        if op == "lane_status":
            # Read-only lookup for the desktop page: by conversation id, or by any runtime
            # session id that conversation has used. Never starts a worker.
            profile, session_id = request.get("profile"), request.get("session_id")
            lane = None
            with self.table_lock:
                for candidate in self.lanes.values():
                    if candidate.owner[0] == profile and session_id and (
                            candidate.owner[1] == session_id or session_id in candidate.sessions_seen):
                        lane = candidate
                        break
            if lane is None:
                return {"ok": True, "lane": None}
            info = self.lane_info(lane)
            info["alive"] = bool(lane.engine and lane.engine.alive())
            info["emulator_active"] = None
            if info["alive"] and lane.inflight == 0:
                try:
                    status = lane.engine.call_tool("session_status", {}, timeout=15)
                    info["emulator_active"] = (status.get("structuredContent") or {}).get("emulatorActive")
                except EngineError:
                    pass
            return {"ok": True, "lane": info}
        owner = self.owner_of(request)
        lane = self.lane_for(owner, create=False)
        if lane is None:
            raise Denied("NO_LANE", "This conversation has no Chromatic worker.")
        if (request.get("origin") or {}).get("delegated"):
            raise Denied("PARENT_ONLY", "Only the owning conversation may change leases or lanes.")
        if op == "grant_lease":
            lane.child_leases[str(request["task_id"])] = request.get("mode", "write")
        elif op == "revoke_lease":
            lane.child_leases.pop(str(request["task_id"]), None)
        elif op == "release_project":
            self._release_root(lane)
        elif op == "close_lane":
            if lane.inflight and not request.get("force"):
                raise Denied("BUSY", "Operations are in flight for this conversation.")
            self._release_root(lane)
            self.close_lane_engine(lane, "closed by owner")
            with self.table_lock:
                self.lanes.pop(owner, None)
        else:
            raise Denied("UNKNOWN_OP", str(op))
        self.trace(event=op, owner_key=lane.key)
        return {"ok": True, "writer": self.holds_writer(lane)}

    # -- housekeeping -------------------------------------------------------------------
    def housekeeping(self) -> None:
        """Stop workers that are provably idle. Never touches live play or in-flight work. An engine
        preview counts as in use for four idle periods: the user plays in the Studio's own player, which
        reads the exported files, so a preview nobody has called for that long only holds the worker
        (and the project's recording lock, which blocks every other chat's emulator on that game)."""
        now = time.monotonic()
        with self.table_lock:
            candidates = [l for l in self.lanes.values()
                          if l.engine and l.engine.alive() and l.inflight == 0
                          and now - l.last_used >= (self.lane_idle * 4 if l.live_surface else self.lane_idle)]
        for lane in candidates:
            try:
                status = lane.engine.call_tool("session_status", {}, timeout=15)
                if (status.get("structuredContent") or {}).get("emulatorActive"):
                    continue
            except EngineError:
                pass
            self.close_lane_if_idle(lane)
        with self.table_lock:
            dead = [o for o, l in self.lanes.items() if (l.engine is None or not l.engine.alive())
                    and l.inflight == 0 and now - l.last_used >= self.lane_idle * 4]
            for owner in dead:
                self._release_root(self.lanes[owner])
                del self.lanes[owner]
            any_live = any(l.engine and l.engine.alive() for l in self.lanes.values())
        if not any_live and not self.install_running() and self.connections == 0 \
                and now - self.last_activity >= self.broker_idle:
            self.trace(event="broker_idle_exit")
            self.stopping.set()

    def close_all(self) -> None:
        with self.table_lock:
            lanes = list(self.lanes.values())
        for lane in lanes:
            if lane.engine:
                lane.engine.close()
        if self.install_engine is not None:   # an install cut short by a stopping broker
            self.install_engine.close()


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        broker: Broker = self.server.broker  # type: ignore[attr-defined]
        creds = self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        peer_pid, uid, _gid = struct.unpack("3i", creds)
        authenticated = False
        with broker.connections_lock:
            broker.connections += 1
        try:
            for raw in self.rfile:
                request = None
                broker.last_activity = time.monotonic()
                try:
                    request = json.loads(raw)
                    if uid != os.getuid():
                        raise Denied("FORBIDDEN", "Peer is not the broker's user.")
                    if not authenticated:
                        if request.get("op") != "hello" or request.get("protocol") != paths.PROTOCOL or \
                                not secrets.compare_digest(str(request.get("token", "")), broker.token):
                            raise Denied("UNAUTHENTICATED", "Handshake required.")
                        authenticated = True
                        response = {"ok": True, "protocol": paths.PROTOCOL, "broker_generation": broker.generation,
                                    "pid": os.getpid(), "code_fingerprint": paths.code_fingerprint(),
                                    "plugin_root": str(paths.PLUGIN_ROOT), "engine": broker.engine_check}
                    elif request.get("op") == "call":
                        request["_client_pid"] = peer_pid  # kernel-reported, for the trace only
                        response = broker.call(request)
                    else:
                        response = broker.control(request)
                except Denied as denial:
                    broker.trace(event="denied", code=denial.code,
                                 tool=request.get("tool") if isinstance(request, dict) else None)
                    response = {"ok": False, "dispatched": False,
                                "denied": {"code": denial.code, "message": str(denial)}}
                except Exception as error:  # surface, never hide
                    broker.trace(event="broker_error", error=f"{type(error).__name__}: {error}"[:300])
                    response = {"ok": False, "dispatched": None, "error": f"{type(error).__name__}: {error}"}
                self.wfile.write((json.dumps(response, separators=(",", ":")) + "\n").encode())
                self.wfile.flush()
                if not authenticated or broker.stopping.is_set():
                    break
        except (BrokenPipeError, ConnectionResetError):
            pass  # the client went away; the engine may still finish its work
        finally:
            with broker.connections_lock:
                broker.connections -= 1
            broker.last_activity = time.monotonic()


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--node", required=True)
    args = parser.parse_args()
    state_dir = Path(args.state_dir)
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)

    lock_handle = open(state_dir / "broker.lock", "a+")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("election lost: another broker holds this state directory", file=sys.stderr)
        return 3  # before any worker, socket or token is touched

    broker = Broker(state_dir, args.node)
    socket_path = state_dir / "broker.sock"
    socket_path.unlink(missing_ok=True)  # safe: we hold the election lock
    old_umask = os.umask(0o177)
    try:
        server = Server(str(socket_path), Handler)
        token_path = state_dir / "broker.token"
        token_path.unlink(missing_ok=True)
        token_path.write_text(broker.token)
    finally:
        os.umask(old_umask)
    server.broker = broker  # type: ignore[attr-defined]
    broker.trace(event="broker_started", pid=os.getpid(), engine_verified=broker.engine_check.get("verified"))
    signal.signal(signal.SIGTERM, lambda *_: broker.stopping.set())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        ticks = 0
        while not broker.stopping.wait(0.25):
            ticks += 1
            if ticks % 120 == 0:
                broker.housekeeping()
    finally:
        server.shutdown()
        broker.close_all()
        socket_path.unlink(missing_ok=True)
        (state_dir / "broker.token").unlink(missing_ok=True)
        broker.trace(event="broker_stopped", pid=os.getpid())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
