"""The desktop page's toolchain install, run by the broker with no chat: the engine's own toolchain_prepare in a
throwaway worker, cancelled through MCP's own cancellation, given up only when nothing changes, and recorded in a
journal (backend/setup/recovery.py) that a reload or a new broker reads.

Stdlib only and no Hermes imports: the broker runs as `python -m backend.broker`.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from .. import setup
from ..system import paths
from .engine import EngineCancelled, EngineError
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
    text = " ".join(
        str(block.get("text", ""))
        for block in result.get("content") or []
        if isinstance(block, dict) and block.get("type") == "text"
    )
    return text or "The game tools could not be prepared."


# How long a cancelled install gets to let go of the engine's setup lock before its worker is closed.
CANCEL_SETTLE = 120.0
# The install gives up only after this long with no visible change in the toolchain folder or the engine's log
# (compiling GB Studio writes little for minutes at a time), and in any case after INSTALL_CAP.
STALL_AFTER = 30 * 60.0
INSTALL_CAP = 4 * 3600.0
SETTLE_QUIET = 3.0  # seconds without the lock before a cancel counts as settled (past a plan that had not locked yet)
WATCH_EVERY = 5.0  # seconds between looks at the toolchain folder while the install runs


def _alive(engine) -> bool:
    alive = getattr(engine, "alive", None)
    return bool(alive()) if callable(alive) else False


class _Cancel(threading.Event):
    """An install's cancel request, with the reason the engine is told."""

    reason = "Cancelled by the user."


class InstallMixin:
    """The Broker's toolchain install for the desktop page: start, cancel, status."""

    def install_running(self) -> bool:
        with self.install_lock:
            return self.install.get("state") == "running"

    def start_install(self) -> dict:
        """Prepare the game toolchain for the desktop page, without a chat. Runs the engine's own
        toolchain_prepare in a throwaway worker on a background thread; install_status reports it."""
        with self.install_lock:
            if self.install.get("state") == "running":
                return dict(self.install)
            if self.install_engine is not None and _alive(self.install_engine):
                raise Denied(
                    "WORKER_STILL_RUNNING",
                    "The previous installer did not stop. Quit and reopen Hermes before trying again.",
                )
            space = setup.free_space(paths.setup_root())
            if not space["enough"]:
                raise Denied(
                    "NO_SPACE",
                    f"Not enough free disk space: the game tools need about {space['needed_bytes'] // 1_000_000:,} MB "
                    f"and {space['free_bytes'] // 1_000_000:,} MB is free where they go ({paths.setup_root()}). "
                    "Free some space, then try again.",
                )
            if not self.prepare_lock.acquire(blocking=False):
                raise Denied(
                    "OPERATION_IN_PROGRESS",
                    "Another setup operation is already running on this machine (probably in a chat). "
                    "Wait for it to finish; this page moves on when the tools are verified.",
                )
            try:
                self.install_cancel = _Cancel()
                self.install = {
                    "state": "running",
                    "started_at": time.time(),
                    "finished_at": None,
                    "error": None,
                    "code": None,
                    "hint": None,
                    "seeded": None,
                    "baseline_bytes": setup.download_bytes(paths.setup_root()),
                    "broker": getattr(self, "generation", None),
                }
                snapshot = dict(self.install)
                setup.write_journal(snapshot)
                threading.Thread(target=self._run_install, name="hermretro-install", daemon=True).start()
            except BaseException as error:
                # Never leave the setup lock held, or a "running" install nobody runs.
                self.prepare_lock.release()
                self.install = {
                    "state": "failed",
                    "started_at": None,
                    "finished_at": time.time(),
                    "code": "INSTALL_ERROR",
                    "error": f"{type(error).__name__}: {error}"[:800],
                }
                setup.write_journal(self.install)
                raise
        self.trace(event="install_started")
        return snapshot

    def cancel_install(self) -> dict:
        """Ask the running install to stop through the engine's own MCP cancellation. The install thread then
        waits for the engine to release its setup lock before it closes the worker and reports ``cancelled``."""
        with self.install_lock:
            if self.install.get("state") != "running":
                return dict(self.install)
            if not self.install.get("cancel_requested_at"):
                self.install["cancel_requested_at"] = time.time()
                setup.write_journal(self.install)
            cancel = getattr(self, "install_cancel", None)
        if cancel is not None:
            cancel.set()
        self.trace(event="install_cancel_requested")
        return self.install_status()

    def _call_prepare(self, engine, root: Path, cancel: threading.Event) -> dict:
        """toolchain_prepare, cancellable, given up only when nothing has changed for STALL_AFTER."""
        outcome: dict = {}
        done = threading.Event()

        def call():
            try:
                outcome["result"] = engine.call_tool(
                    "toolchain_prepare", {"components": ["build", "emulator"]}, timeout=INSTALL_CAP, cancel=cancel
                )
            except BaseException as error:  # handed to the waiting thread below
                outcome["error"] = error
            finally:
                done.set()

        threading.Thread(target=call, name="hermretro-install-call", daemon=True).start()
        mark, changed = None, time.monotonic()
        while not done.wait(WATCH_EVERY):
            now_mark = (setup.download_bytes(root), setup.activity_mark(root), getattr(engine, "output_lines", 0))
            if now_mark != mark:
                mark, changed = now_mark, time.monotonic()
                with self.install_lock:
                    self.install["quiet_since"] = time.time()
            elif time.monotonic() - changed >= STALL_AFTER and not cancel.is_set():
                cancel.reason = f"Nothing changed for {round(STALL_AFTER / 60)} minutes; hermretro stopped the install."
                with self.install_lock:
                    self.install["stalled"] = True
                cancel.set()
        if "error" in outcome:
            raise outcome["error"]
        return outcome["result"]

    def _settle_after_cancel(self, engine, root: Path, started: float) -> bool:
        """Wait (bounded) for the engine's setup run to let go of the toolchain folder after a cancel."""
        deadline = time.monotonic() + CANCEL_SETTLE
        quiet_since = None
        while time.monotonic() < deadline and _alive(engine):
            if setup.settled(root, started):
                quiet_since = quiet_since or time.monotonic()
                if time.monotonic() - quiet_since >= SETTLE_QUIET:
                    return True
            else:
                quiet_since = None
            time.sleep(0.25)
        return setup.settled(root, started)

    def _run_install(self) -> None:
        engine = None
        root = paths.setup_root()
        cancel = getattr(self, "install_cancel", None) or _Cancel()
        started = None
        outcome: dict = {"state": "failed", "error": None, "code": None, "hint": None}
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
                    self.install["baseline_bytes"] = setup.download_bytes(root)
                started = self.install.get("started_at")
            if cancel.is_set():
                raise EngineCancelled(cancel.reason)
            engine = self.new_engine("chromatic-studio-install")
            self.install_engine = engine  # close_all stops it if the broker stops mid-install
            result = self._call_prepare(engine, root, cancel)
            structured = result.get("structuredContent")
            structured = structured if isinstance(structured, dict) else {}
            if result.get("isError") or structured.get("success") is not True:
                outcome.update(
                    code=str(structured.get("stage") or "PREPARE_FAILED").upper(),
                    error=_prepare_failure(result, structured)[:800],
                )
            else:
                outcome = {"state": "done", "error": None, "code": None, "hint": None}
        except EngineCancelled as stopped:
            released = engine is None or self._settle_after_cancel(engine, root, started)
            if self.install.get("stalled"):
                outcome.update(code="STALLED", error=str(stopped)[:800])
                outcome["hint"] = "Finished parts are kept. Try again; if it stops at the same place, ask Hermes."
            else:
                outcome.update(state="cancelled", code="CANCELLED", error="The install was cancelled.")
                outcome["hint"] = "Finished parts are kept. Install again whenever you like."
            if not released:
                outcome["release_unconfirmed"] = True
        except Denied as denial:
            outcome.update(code=denial.code, error=str(denial))
        except EngineError as error:
            outcome.update(code="ENGINE_ERROR", error=str(error)[:800])
        except Exception as error:  # surface, never hide
            outcome.update(code="INSTALL_ERROR", error=f"{type(error).__name__}: {error}"[:800])
        finally:
            if engine is not None:
                try:
                    engine.close()
                except Exception as error:
                    outcome.update(
                        state="failed", code="WORKER_CLOSE_ERROR", error=f"Could not close the installer: {error}"[:800]
                    )
            still_running = engine is not None and _alive(engine)
            if outcome["state"] != "done":
                if not outcome.get("hint"):
                    outcome["code"], outcome["hint"] = setup.explain(outcome.get("code"), outcome.get("error"), root)
                if still_running:
                    outcome.update(code="WORKER_STILL_RUNNING", state="failed")
                    outcome["hint"] = "The engine worker did not exit. Quit and reopen Hermes before trying again."
                elif outcome["code"] != "SETUP_LOCKED" and setup.lock_path(root).exists():
                    # The engine keeps its lock when it cannot prove its own processes ended: never removed here.
                    outcome.update(code="SETUP_LOCK_KEPT", state="failed")
                    outcome["hint"] = (
                        f"The engine kept its setup lock at {setup.lock_path(root)} because it could not confirm "
                        "its processes ended. Quit and reopen Hermes; if the folder is still there and nothing is "
                        "installing, move it aside, then try again."
                    )
            outcome.pop("release_unconfirmed", None)
            with self.install_lock:
                self.install_engine = engine if still_running else None
                self.install.update(outcome, finished_at=time.time())
                setup.write_journal(self.install)
                self.prepare_lock.release()
            self.last_activity = time.monotonic()
            self.trace(event="install_finished", state=outcome["state"], code=outcome.get("code"))

    def install_status(self) -> dict:
        root = paths.setup_root()
        with self.install_lock:
            state = dict(self.install)
            elsewhere = state.get("state") != "running" and self.prepare_lock.locked()
        if state.get("state") == "idle":
            state = setup.recovered_install(root, getattr(self, "generation", None)) or state
        answer = setup.install_progress(state, root)
        answer["elsewhere"] = elsewhere
        now = time.time()
        if state.get("state") == "running" and state.get("started_at"):
            answer["elapsed_seconds"] = round(now - state["started_at"], 1)
            answer["quiet_seconds"] = round(now - (state.get("quiet_since") or state["started_at"]), 1)
        answer["cancelling"] = state.get("state") == "running" and bool(state.get("cancel_requested_at"))
        return answer
