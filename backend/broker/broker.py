"""The one authority for hermretro on this machine.

A single elected process per user. Model tools, desktop RPC and every other
caller are clients on a user-only Unix socket, so there is exactly one place
that owns engine workers, project writer coordination and hardware admission.

Each trusted owner (Hermes profile + durable conversation) gets a private,
lazily started engine worker. The engine binds a worker to one project root,
so a lane is "conversation -> its project worker".

Stdlib only and no Hermes imports: this runs as `python -m backend.broker`. The lane work lives in
lane.py, control operations and housekeeping in control.py, the socket server and main() in server.py.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path

from .. import library, setup
from ..system import paths
from . import leases
from .control import ControlMixin
from .lane import DEFAULT_CALL_TIMEOUT, Denied, Lane, LaneMixin, canonical_hash
from .engine import EngineError

HARDWARE = frozenset({"device", "setup", "flash", "play", "device_capture"})
PREPARE = frozenset({"toolchain_prepare"})
SELECTORS = frozenset({"project_select", "project_create", "project_create_blank"})
PARENT_ONLY = frozenset({"emulator_close", "web_preview_close"}) | SELECTORS | PREPARE | HARDWARE


def selects_project(tool: str, arguments: dict) -> bool:
    """Whether a successful call changed which project the worker has selected. The create tools
    return the new project's root either way, but only select it when asked to."""
    return tool == "project_select" or (tool in SELECTORS and arguments.get("select") is True)


RUNTIME_PREFIXES = ("emulator_", "web_preview")


def _env_seconds(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def game_rom_arguments(root: str, arguments: dict) -> dict:
    """A project build writes the game's one ROM (``library.canonical_rom``): its ``outputPath`` is set here, and
    one naming any other file is refused, so ``build/`` never collects ROMs nobody knows to be the game."""
    rom = library.canonical_rom(Path(root))
    asked = arguments.get("outputPath")
    if asked is not None and (not isinstance(asked, str) or Path(root, asked).resolve() != Path(root, rom).resolve()):
        raise Denied(
            "ROM_PATH",
            f"Every build of a hermretro game writes its one ROM, {rom}. Call chromatic_rom_build again without "
            "outputPath.",
        )
    return {**arguments, "outputPath": rom}


class Broker(LaneMixin, ControlMixin):
    def __init__(self, state_dir: Path, node: str):
        self.state_dir = state_dir
        self.node = node
        pinned = json.loads(paths.PINNED_TOOLS.read_text())["tools"]
        self.pinned_hash = canonical_hash(pinned)
        self.tools = {t["name"]: t for t in pinned}
        self.read_only = {n for n, t in self.tools.items() if t.get("annotations", {}).get("readOnlyHint")}
        self.generation = secrets.token_hex(8)
        self.token = secrets.token_hex(32)
        # The build this process runs, read once at start: the handshake must name the code loaded here, not
        # the files on disk now. Read at each hello, a broker that `hermes plugins update` rewrote underneath
        # claimed the new build's fingerprint, so the new client kept it (old code) instead of replacing it.
        try:
            self.code_fingerprint: str | None = paths.code_fingerprint()
        except OSError:  # files already moving under it: any client replaces it
            self.code_fingerprint = None
        self.engine_check = paths.verify_engine()
        self.games = library.Registry(paths.library_dir_for(state_dir))
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
            raise Denied(
                "IDENTITY_REQUIRED",
                "No trusted conversation identity came with this call. Call Chromatic tools "
                "directly from the conversation, not from inside execute_code.",
            )
        values = []
        for label in ("profile", "conversation_id"):
            value = owner.get(label)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise Denied(
                    "IDENTITY_REQUIRED",
                    f"Trusted owner field '{label}' is missing. Call Chromatic tools directly "
                    "from the conversation, not from inside execute_code.",
                )
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
        if tool not in library.SELECTORS and tool not in ("rom_build", "web_preview"):
            return
        try:
            self.games.observe(
                tool,
                arguments,
                structured,
                failed,
                lane_root=lane.selected_root,
                conversation_id=lane.owner[1],
                sessions_seen=lane.sessions_seen,
                profile=lane.owner[0],
            )
        except Exception as error:
            self.trace(event="library_record_failed", tool=tool, error=f"{type(error).__name__}: {error}"[:200])

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
        if kind == "prepare" and self.install_worker_left():
            raise Denied(
                "WORKER_STILL_RUNNING",
                "The page's last toolchain installer did not confirm it stopped. Quit and reopen Hermes, then "
                "check the tools again; do not start another setup until then.",
            )
        if kind == "hardware" and not policy.get("hardware_enabled"):
            raise Denied(
                "HARDWARE_DISABLED",
                "Chromatic hardware tools are turned off. The user can turn them on in "
                "Settings > Plugins > hermretro (hardware_enabled). Do not retry until they do.",
            )
        lane = self.lane_for(owner, create=not delegated)
        if lane is None:
            raise Denied("NO_PARENT_LANE", "A delegated subagent cannot start Chromatic work for a conversation.")
        if delegated:
            task_id = origin.get("task_id") or origin.get("session_id")
            if tool in PARENT_ONLY:
                raise Denied(
                    "PARENT_ONLY", f"A delegated subagent may not call {tool}. Do this from the main conversation."
                )
            if kind != "read" and lane.child_leases.get(str(task_id)) != "write":
                raise Denied(
                    "LEASE_REQUIRED",
                    "Delegated subagents can inspect a Chromatic project but not "
                    "change it or drive its emulator. Do this from the main conversation.",
                )
        session_id = origin.get("session_id")
        if isinstance(session_id, str) and session_id and not delegated and session_id not in lane.sessions_seen:
            lane.sessions_seen.append(session_id)
            del lane.sessions_seen[:-16]
        if tool in SELECTORS:
            # `continueInThisChat` is hermretro's own argument (the user confirmed working on a game outside
            # its conversation); the engine never sees it.
            arguments = dict(arguments)
            continue_here = arguments.pop("continueInThisChat", None) is True
            self.guard_selection(owner, lane, tool, arguments, continue_here)

        with self.table_lock:
            lane.last_used = time.monotonic()  # before the engine is fetched: see close_lane_if_idle
        engine = self.ensure_engine(lane)
        if not delegated and kind in ("read", "project-write", "runtime"):
            self.select_bound_game(lane, engine)
        if tool == "rom_build" and "sourcePath" not in arguments and lane.selected_root:
            arguments = game_rom_arguments(lane.selected_root, arguments)
        writes = kind == "project-write"
        if writes:
            self.acquire_writer(lane)
        guard = self.hardware_lock if kind == "hardware" else self.prepare_lock if kind == "prepare" else None
        if guard is not None and not guard.acquire(blocking=False):
            raise Denied(
                "OPERATION_IN_PROGRESS",
                "Another hardware or setup operation is already running on this machine. Wait for it "
                "to finish and check its original status; do not start a replacement.",
            )
        base = dict(
            owner_key=lane.key,
            tool=tool,
            kind=kind,
            engine_pid=engine.pid,
            engine_generation=lane.generation,
            delegated=delegated,
            client_pid=request.get("_client_pid"),
        )
        if kind == "prepare":
            # First install: start from another install's verified download cache when there is one.
            try:
                seeded = setup.seed_toolchain_cache()
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
                result = engine.call_tool(
                    tool, arguments, timeout=float(request.get("timeout") or DEFAULT_CALL_TIMEOUT)
                )
                if leases.is_lease_conflict(result) and lane.selected_root:
                    # The engine refused before starting anything. If the lease's owner is provably
                    # gone (killed without releasing it), clear it and run the call once more.
                    reclaimed = leases.reclaim_stale(lane.selected_root, self.own_process_groups())
                    self.trace(event="stale_lease_check", **reclaimed, **base)
                    if reclaimed.get("cleared"):
                        result = engine.call_tool(
                            tool, arguments, timeout=float(request.get("timeout") or DEFAULT_CALL_TIMEOUT)
                        )
                        written = time.strftime("%Y-%m-%d %H:%M", time.localtime(reclaimed["written"]))
                        cleared = (
                            f"An emulator lease left on this game by process {reclaimed['pid']} "
                            f"(written {written}), which no longer exists, was cleared automatically."
                        )
                        lane.pending_notice = f"{lane.pending_notice} {cleared}" if lane.pending_notice else cleared
            except EngineError as error:
                self.trace(event="outcome_unknown", error=str(error)[:300], **base)
                return {
                    "ok": False,
                    "dispatched": True,
                    "outcome": "unknown",
                    "error": str(error),
                    "engine_alive": engine.alive(),
                }
            if kind == "select" and not result.get("isError"):
                try:
                    self._sync_selection(lane)
                except Exception as error:
                    # The selection itself succeeded. Do not report it as failed, and do not leave
                    # this conversation writing without a lease: take the root from the result.
                    self.trace(event="selection_sync_failed", error=str(error)[:200], **base)
                    selected = result.get("structuredContent")
                    if selects_project(tool, arguments) and isinstance(selected, dict) and selected.get("projectRoot"):
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
        if (
            tool == "rom_build"
            and policy.get("live_player")
            and not delegated
            and "sourcePath" not in arguments
            and not result.get("isError")
            and (result.get("structuredContent") or {}).get("success") is not False
        ):
            player = self.refresh_player(lane, engine)
        images = sum(1 for block in result.get("content", []) if block.get("type") == "image")
        self.trace(
            event="completed",
            seconds=round(time.time() - started, 3),
            is_error=bool(result.get("isError")),
            image_blocks=images,
            **base,
        )
        notice, lane.pending_notice = lane.pending_notice, None
        answer = {"ok": True, "dispatched": True, "result": result, "notice": notice, "lane": self.lane_info(lane)}
        if player is not None:
            answer["player"] = player
        return answer

    def lane_info(self, lane: Lane) -> dict:
        return {
            "owner_key": lane.key,
            "engine_pid": lane.engine.pid if lane.engine else None,
            "engine_generation": lane.generation,
            "selected_root": lane.selected_root,
            "writer": self.holds_writer(lane),
            "sessions_seen": list(lane.sessions_seen),
        }
