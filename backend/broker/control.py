"""The broker's control operations (everything but `call`): the desktop page's toolchain install,
stats, shutdown, doctor, the page's activity and lane lookups, leases and lanes, and housekeeping.

Stdlib only and no Hermes imports: the broker runs as `python -m backend.broker`.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from pathlib import Path

from .. import setup
from ..system import paths
from .engine import EngineError
from .lane import Denied


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


class ControlMixin:
    """The Broker's install, control op and housekeeping methods."""

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
                                "baseline_bytes": setup.directory_bytes(paths.setup_root())}
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
                seeded = setup.seed_toolchain_cache()
            except Exception as error:  # reuse is an optimisation; never let it block setup
                seeded = {"seeded": False, "reason": f"{type(error).__name__}: {error}"}
            self.trace(event="toolchain_cache_seed", **seeded)
            with self.install_lock:
                self.install["seeded"] = bool(seeded.get("seeded"))
                if seeded.get("seeded"):
                    # The copied cache is not a download: count only what arrives after it.
                    self.install["baseline_bytes"] = setup.directory_bytes(paths.setup_root())
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
        return setup.install_progress(state, paths.setup_root())

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

    def own_process_groups(self) -> set[int]:
        """Process groups of this broker's live engine workers (each worker is its own session)."""
        with self.table_lock:
            engines = [lane.engine for lane in self.lanes.values() if lane.engine is not None]
        if self.install_engine is not None:
            engines.append(self.install_engine)
        return {engine.pid for engine in engines if engine.pid and engine.alive()}

    def close_all(self) -> None:
        with self.table_lock:
            lanes = list(self.lanes.values())
        for lane in lanes:
            if lane.engine:
                lane.engine.close()
        if self.install_engine is not None:   # an install cut short by a stopping broker
            self.install_engine.close()
