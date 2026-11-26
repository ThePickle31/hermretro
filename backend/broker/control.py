"""The broker's control operations (everything but `call`): the desktop page's toolchain install,
stats, shutdown (lifecycle.py), doctor, the page's activity and lane lookups, leases and lanes, and housekeeping.

Stdlib only and no Hermes imports: the broker runs as `python -m backend.broker`.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from .engine import EngineError
from .install import InstallMixin
from .lane import Denied


class ControlMixin(InstallMixin):
    """The Broker's control op and housekeeping methods (the install's are in install.py)."""

    # -- control operations ---------------------------------------------------------
    def control(self, request: dict) -> dict:
        op = request.get("op")
        if op == "install_start":
            if "admit_until" in request:
                install = self.start_install(admit_until=request.get("admit_until") or 0)
            else:
                install = self.start_install(admit_before=request.get("admit_before") or 0)
            return {"ok": True, "install": install}
        if op in ("hold_game", "release_game"):
            return self.game_hold(request)
        if op == "test_build":
            return self.test_build(request)
        if op == "install_status":
            return {"ok": True, "install": self.install_status()}
        if op == "install_cancel":
            return {"ok": True, "install": self.cancel_install(request.get("run_id"))}
        if op == "stats":
            with self.table_lock:
                lanes = [
                    {
                        **self.lane_info(l),
                        "alive": bool(l.engine and l.engine.alive()),
                        "inflight": l.inflight,
                        "child_leases": dict(l.child_leases),
                    }
                    for l in self.lanes.values()
                ]
                leases = {
                    root: hashlib.sha256("\0".join(o).encode()).hexdigest()[:16]
                    for root, o in self.writer_leases.items()
                }
            return {
                "ok": True,
                "pid": os.getpid(),
                "broker_generation": self.generation,
                "retiring": self.retiring,
                "lanes": lanes,
                "writer_leases": leases,
            }
        if op == "shutdown":
            # A client of newer code asks with `replace` (retire); Remove downloaded tools and other copies do not.
            return self.retire() if request.get("replace") else self.shutdown(bool(request.get("force")))
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
            return {
                "ok": True,
                "matched": matched,
                "lane": {
                    "project_root": lane.selected_root,
                    "project_name": Path(lane.selected_root).name if lane.selected_root else None,
                    "alive": bool(lane.engine and lane.engine.alive()),
                    "busy": lane.inflight > 0,
                    "current_tool": lane.current_tool,
                    "preview_url": lane.preview_url,
                },
                "events": list(lane.activity)[-int(request.get("limit") or 40) :],
                "frame": lane.last_frame,
                "build": lane.last_build,
            }
        if op == "lane_status":
            # Read-only lookup for the desktop page: by conversation id, or by any runtime
            # session id that conversation has used. Never starts a worker.
            profile, session_id = request.get("profile"), request.get("session_id")
            lane = None
            with self.table_lock:
                for candidate in self.lanes.values():
                    if (
                        candidate.owner[0] == profile
                        and session_id
                        and (candidate.owner[1] == session_id or session_id in candidate.sessions_seen)
                    ):
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
            candidates = [
                l
                for l in self.lanes.values()
                if l.engine
                and l.engine.alive()
                and l.inflight == 0
                and now - l.last_used >= (self.lane_idle * 4 if l.live_surface else self.lane_idle)
            ]
        for lane in candidates:
            try:
                status = lane.engine.call_tool("session_status", {}, timeout=15)
                if (status.get("structuredContent") or {}).get("emulatorActive"):
                    continue
            except EngineError:
                pass
            self.close_lane_if_idle(lane)
        with self.table_lock:
            dead = [
                o
                for o, l in self.lanes.items()
                if (l.engine is None or not l.engine.alive())
                and l.inflight == 0
                and now - l.last_used >= self.lane_idle * 4
            ]
            for owner in dead:
                self._release_root(self.lanes[owner])
                del self.lanes[owner]
            any_live = any(l.engine and l.engine.alive() for l in self.lanes.values())
        if (
            not any_live
            and not self.install_busy()
            and self.connections == 0
            and now - self.last_activity >= self.broker_idle
        ):
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
        self.close_install_worker()  # an install cut short by a stopping broker
