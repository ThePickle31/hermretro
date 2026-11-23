"""The desktop page's toolchain install, run by the broker with no chat: the engine's own toolchain_prepare in a
throwaway worker, cancelled through MCP's own cancellation, given up only when nothing changes, and recorded in a
journal (backend/setup/recovery.py) that a reload or a new broker reads.

Stdlib only and no Hermes imports: the broker runs as `python -m backend.broker`.
"""

from __future__ import annotations

import math
import secrets
import threading
import time
from pathlib import Path

from .. import setup
from ..system import paths
from .engine import EngineCancelled, EngineError
from .lane import Denied


def _prepare_failure(result: dict, structured: dict) -> str:
    """One readable reason a toolchain_prepare call did not finish: the first failed component's
    error, else the preflight's root issue, else the engine's message or thrown error, else its text."""
    run = structured.get("result")
    for component in (run.get("components") or []) if isinstance(run, dict) else []:
        if isinstance(component, dict) and component.get("status") in ("failed", "blocked"):
            error = component.get("error")
            message = error.get("message") if isinstance(error, dict) else error or component.get("reason")
            if message:
                return f"{component.get('id')}: {message}"
    plan = structured.get("plan")
    if isinstance(plan, dict) and isinstance(plan.get("rootIssue"), str) and plan["rootIssue"]:
        return plan["rootIssue"]
    for name in ("message", "error"):
        if isinstance(structured.get(name), str) and structured[name]:
            return structured[name]
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


def _still_running(engine) -> bool:
    """The worker, or anything it started in its own session, has not exited."""
    if _alive(engine):
        return True
    group = getattr(engine, "_group_exists", None)
    try:
        return bool(group()) if callable(group) and getattr(engine, "_proc", None) is not None else False
    except OSError:
        return True


class _Cancel(threading.Event):
    """An install's cancel request, with the reason the engine is told."""

    reason = "Cancelled by the user."


class InstallMixin:
    """The Broker's toolchain install for the desktop page: start, cancel, status."""

    def install_running(self) -> bool:
        with self.install_lock:
            return self.install.get("state") == "running"

    def install_worker_left(self) -> bool:
        """An installer worker whose exit is not confirmed: the one this broker kept after closing it failed, or
        one an earlier broker recorded in the journal. Shutdown, idle retirement, a new install and a chat's
        toolchain_prepare all wait for it. Takes no lock (callers may hold install_lock)."""
        engine = getattr(self, "install_engine", None)
        if engine is not None:
            if _still_running(engine):
                return True
            self.install_engine = None  # its exit is confirmed now: the journal stops naming it
            setup.write_journal({key: value for key, value in self.install.items() if key != "worker_pgid"})
            return False
        return setup.worker_left(setup.read_journal())

    def install_busy(self) -> bool:
        return self.install_running() or self.install_worker_left()

    def close_install_worker(self) -> None:
        """The stopping broker's last try at the installer worker; an exit it cannot confirm is recorded."""
        engine = self.install_engine
        if engine is None:
            return
        try:
            engine.close()
        except Exception as error:
            self.trace(event="install_worker_close_failed", error=f"{type(error).__name__}: {error}"[:200])
        if _still_running(engine):
            with self.install_lock:
                self._record_left_worker(engine)

    def _check_install_admission(self, admit_before: float | None) -> None:
        if admit_before is not None and (
            type(admit_before) not in (int, float)
            or not math.isfinite(admit_before)
            or time.time() * 1000 >= admit_before
        ):
            raise Denied("START_EXPIRED", "The install start expired. Check the install status and try again.")
        if self.stopping.is_set():
            raise Denied("BROKER_STOPPING", "The background process is stopping. Try again.")

    def start_install(self, *, admit_before: float | None = None) -> dict:
        """Prepare the game toolchain for the desktop page, without a chat. Runs the engine's own
        toolchain_prepare in a throwaway worker on a background thread; install_status reports it."""
        with self.install_lock:
            self._check_install_admission(admit_before)
            if self.install.get("state") == "running":
                return dict(self.install)
            if self.install_worker_left():
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
            baseline_bytes = setup.download_bytes(paths.setup_root())
            # Check again after filesystem work, under the same lock that protects the status snapshot.
            self._check_install_admission(admit_before)
            if not self.prepare_lock.acquire(blocking=False):
                raise Denied(
                    "OPERATION_IN_PROGRESS",
                    "Another setup operation is already running on this machine (probably in a chat). "
                    "Wait for it to finish; this page moves on when the tools are verified.",
                )
            try:
                cancel = self.install_cancel = _Cancel()
                self.install = {
                    "state": "running",
                    # Names this run: a cancel meant for an earlier run never stops a retry started since.
                    "run_id": secrets.token_hex(8),
                    "started_at": time.time(),
                    "finished_at": None,
                    "error": None,
                    "code": None,
                    "hint": None,
                    "seeded": None,
                    "baseline_bytes": baseline_bytes,
                    "broker": getattr(self, "generation", None),
                }
                snapshot = dict(self.install)
                setup.write_journal(snapshot)
                threading.Thread(
                    target=self._run_install, args=(cancel,), name="hermretro-install", daemon=True
                ).start()
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

    def cancel_install(self, run_id: str | None) -> dict:
        """Ask the running install named ``run_id`` to stop through the engine's own MCP cancellation. The install
        thread then waits (bounded) for the engine to release its setup lock before it closes the worker. A cancel
        for another run (one that finished, while a retry runs now) changes nothing and returns the status."""
        with self.install_lock:
            current = self.install.get("state") == "running" and bool(run_id) and run_id == self.install.get("run_id")
            cancel = getattr(self, "install_cancel", None) if current else None
            if current and not self.install.get("cancel_requested_at"):
                self.install["cancel_requested_at"] = time.time()
                setup.write_journal(self.install)
            if cancel is not None:
                cancel.set()
        self.trace(event="install_cancel_requested" if current else "install_cancel_stale")
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

    def _record_left_worker(self, engine) -> None:
        """Journal the worker whose exit is unconfirmed, so a new broker and Remove downloaded tools wait for it.
        Called with install_lock held."""
        pgid = getattr(engine, "pid", None)
        setup.write_journal({**self.install, **({"worker_pgid": pgid} if isinstance(pgid, int) else {})})

    def _run_install(self, cancel: threading.Event | None = None) -> None:
        engine = None
        root = paths.setup_root()
        cancel = cancel or _Cancel()
        # A lock already there was never this run's: another installer's, or one an earlier run left.
        lock_before = setup.lock_path(root).exists()
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
                # Classified from the engine's structured fields before the message is shortened for display.
                found = setup.classify(result, root)
                outcome.update(
                    code=found["code"]
                    or str(structured.get("stage") or structured.get("code") or "PREPARE_FAILED").upper(),
                    error=_prepare_failure(result, structured)[:800],
                    hint=found["hint"],
                    foreign_lock=found["foreign_lock"],
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
            still_running = engine is not None and _still_running(engine)
            foreign = bool(outcome.pop("foreign_lock", False))
            if outcome["state"] != "done":
                if not outcome.get("hint"):
                    outcome["code"], outcome["hint"] = setup.explain(outcome.get("code"), outcome.get("error"), root)
                if still_running:
                    outcome.update(code="WORKER_STILL_RUNNING", state="failed")
                    outcome["hint"] = "The engine worker did not exit. Quit and reopen Hermes before trying again."
                elif setup.lock_path(root).exists():
                    taken = setup.lock_started(root)
                    # Never this run's: the engine's plan or apply said another setup owns it, it was there before
                    # this run started, or its recorded owner took it before this run did.
                    foreign = (
                        foreign
                        or outcome["code"] == "SETUP_LOCKED"
                        or lock_before
                        or (taken is not None and started is not None and taken < started - 2)
                    )
                    if foreign:
                        outcome.update(code="SETUP_LOCKED", state="failed", hint=setup.foreign_lock_hint(root))
                    else:
                        # This run's engine kept its lock (it cannot prove its own processes ended): never removed.
                        outcome.update(code="SETUP_LOCK_KEPT", state="failed")
                        outcome["hint"] = (
                            f"The engine kept its setup lock at {setup.lock_path(root)} because it could not "
                            "confirm its processes ended. Quit and reopen Hermes; if the folder is still there and "
                            "nothing is installing, move it aside, then try again."
                        )
            outcome.pop("release_unconfirmed", None)
            with self.install_lock:
                self.install_engine = engine if still_running else None
                self.install.update(outcome, finished_at=time.time())
                if still_running:
                    self._record_left_worker(engine)
                else:
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
