"""The broker's life: what it admits, and how it stops (a plain shutdown, or retiring for a client of newer code).

One state, decided under ``table_lock``: serving; retiring (a client of newer code asked it to make way: it admits
nothing new and stops once nothing it must finish runs); stopping (``stopping`` is set and main() closes the workers).
A request that runs work is admitted (``admit``) and counted in ``running`` until its answer has been written or its
client is gone (``answered``), so a stop never cuts off a reply. What a conversation is to be told about a worker
closed under it stays in the run folder (``Notices``) until a call has carried it there.

Stdlib only and no Hermes imports: the broker runs as `python -m backend.broker`.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ..system import paths
from .engine import EngineError
from .lane import Denied, Lane

# The requests that run work: a tool call, the page's install start, the doctor's throwaway worker.
WORK_OPS = frozenset({"call", "install_start", "doctor", "test_build"})

# What a conversation is told on its first call to the next broker when this one retired while its worker was idle.
UPDATE_NOTICE = (
    "hermretro was updated, so this conversation's game worker was restarted: any running emulator, browser preview "
    "and held buttons were reset, and the project may need selecting again. Start what you need again."
)

# A retiring broker looks again this often at what it waits for. Engine work whose outcome is unknown, a recording a
# call started and a preview a person still records or saves in are waited for at most RETIRE_PATIENCE: a hung worker
# must not hold every chat's tools back for ever.
RETIRE_RECHECK = 2.0
RETIRE_PATIENCE = 15 * 60.0
PREVIEW_CLOSE_TIMEOUT = 45.0  # the engine gives a closing preview up to 30 s to save its recording, input and states


def combine(*texts: str | None) -> str | None:
    """Notices joined, each once."""
    kept: list[str] = []
    for text in texts:
        if text and not any(text in other for other in kept):
            kept.append(text)
    return " ".join(kept) or None


class Notices:
    """What conversations are to be told on their next call ({lane key: notice}), kept in the run folder
    (``notices.json``) across broker generations until a call's answer has carried each one."""

    LIMIT = 256  # the newest: a conversation that never calls again does not keep its notice for ever

    def __init__(self, state_dir: Path):
        self.path = Path(state_dir) / "notices.json"
        self.lock = threading.Lock()
        self.kept = self._read()

    def _read(self) -> dict[str, str]:
        try:
            notices = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        if not isinstance(notices, dict):
            return {}
        return {key: text for key, text in notices.items() if isinstance(text, str)}

    def get(self, key: str) -> str | None:
        with self.lock:
            return self.kept.get(key)

    def keep(self, notices: dict[str, str]) -> None:
        """Keep these whole notices, each replacing what its conversation had."""
        with self.lock:
            for key, text in notices.items():
                self.kept.pop(key, None)
                self.kept[key] = text
            for key in list(self.kept)[: -self.LIMIT]:
                del self.kept[key]
            self._write()

    def given(self, key: str, carried: str) -> None:
        """An answer carrying ``carried`` reached the conversation: what was kept for it has been told."""
        with self.lock:
            if key in self.kept and self.kept[key] in carried:
                del self.kept[key]
                self._write()

    def _write(self) -> None:
        if self.kept:
            paths.write_json_atomic(self.path, self.kept)
        else:
            self.path.unlink(missing_ok=True)


class LifecycleMixin:
    """The Broker's admission, plain shutdown and retirement."""

    # -- admission -------------------------------------------------------------------
    def admit(self, request: dict) -> bool:
        """Count a request that runs work until ``answered``, or refuse it: a retiring broker admits none (a worker it
        started would run the engine now on disk against the tool contracts this broker loaded), nor a stopping one.
        Returns whether the request was counted."""
        if request.get("op") not in WORK_OPS:
            return False
        with self.table_lock:
            if self.retiring:
                raise Denied("RESTARTING", self.restart_message() + " Nothing ran; call it again in a moment.")
            if self.stopping.is_set():
                raise Denied("BROKER_STOPPING", "The background process is stopping. Try again.")
            self.running += 1
        return True

    def answered(self, response: dict, delivered: bool) -> None:
        """An admitted request's answer was written (``delivered``), or its client went away before."""
        notice, key = response.get("notice"), (response.get("lane") or {}).get("owner_key")
        if notice and key and delivered:
            try:
                self.notices.given(key, notice)
            except OSError as error:
                self.trace(event="notices_not_written", error=f"{type(error).__name__}: {error}"[:200])
        with self.table_lock:
            if notice and key and not delivered:  # told on the conversation's next call instead
                lane = next((lane for lane in self.lanes.values() if lane.key == key), None)
                if lane is not None:
                    lane.pending_notice = combine(notice, lane.pending_notice)
            self.running -= 1
            self.settled.notify_all()

    # -- stopping ----------------------------------------------------------------------
    def shutdown(self, force: bool) -> dict:
        """A plain stop (Setup's Remove downloaded tools, another copy of the plugin): refused while any work runs or a
        worker lives, unless forced. An installer whose exit is unconfirmed counts as busy too. Decided under the
        admission lock, so nothing is admitted once it agreed."""
        with self.table_lock:
            busy = self.running or any(l.inflight or (l.engine and l.engine.alive()) for l in self.lanes.values())
            if not force and (busy or self.install_busy()):
                raise Denied("BUSY", "Conversations still have live Chromatic workers.")
            self.stopping.set()
        return {"ok": True}

    def retire(self) -> dict:
        """Make way for a client of newer code: an update, reload or Repair changed the plugin under this broker.

        Idle workers do not keep it: they close with it, and each of their conversations is told on its first call to
        the next broker (UPDATE_NOTICE). Until it stops it admits nothing new, and it waits for the work it must
        finish (``_retirement_waits``) on a thread of its own; the client waits for the next broker meanwhile."""
        with self.table_lock:
            if self.stopping.is_set():
                return {"ok": True}
            if not self.retiring:
                self.retiring, self.retire_started = True, time.monotonic()
                if self._retirement_waits() == (None, []):
                    self._stop_retired()
                    return {"ok": True}
                self.trace(event="broker_retiring", running=self.running)
                threading.Thread(target=self._retire, name="hermretro-retire", daemon=True).start()
        raise Denied("RETIRING", self.restart_message())

    def _retirement_waits(self) -> tuple[str | None, list[Lane]]:
        """What a retiring broker waits for (under table_lock): its running work and the page's install, then engine
        work whose outcome is unknown and recordings calls started, as (reason, []); else (None, the lanes whose
        browser preview closes itself first: the engine saves its recording, input and states, and refuses while a
        person records or saves in it)."""
        if self.running:
            return "running", []
        if self.install_busy():
            return "install", []
        now = time.monotonic()
        if now - self.retire_started >= RETIRE_PATIENCE:
            return None, []
        live = [lane for lane in self.lanes.values() if lane.engine is not None and lane.engine.alive()]
        if any(lane.engine.unconfirmed() for lane in live):
            return "unconfirmed", []
        if any(lane.recording_until > now for lane in live):
            return "recording", []
        return None, [lane for lane in live if lane.preview_url]

    def _retire(self) -> None:
        """The retiring broker's wait, then its stop."""
        refused: set[str] = set()
        while not self.stopping.is_set():
            with self.table_lock:
                waiting, previews = self._retirement_waits()
                if waiting is not None:
                    self.settled.wait(RETIRE_RECHECK)
                    continue
                if not previews:
                    self._stop_retired()
                    return
            # Outside the lock: nothing is admitted while retiring, so no call uses these workers meanwhile.
            for lane in previews:
                error = self._close_preview(lane)
                if error is not None and lane.key not in refused:
                    refused.add(lane.key)
                    self.trace(event="preview_in_use", owner_key=lane.key, error=error[:200])
            if any(lane.preview_url for lane in previews):
                self.stopping.wait(RETIRE_RECHECK)

    def _close_preview(self, lane: Lane) -> str | None:
        """Ask a lane's engine to close its browser preview the way web_preview_close does; why not, or None."""
        try:
            result = lane.engine.call_tool("web_preview_close", {}, timeout=PREVIEW_CLOSE_TIMEOUT)
        except EngineError as error:
            return str(error)
        structured = result.get("structuredContent")
        structured = structured if isinstance(structured, dict) else {}
        if result.get("isError") or structured.get("closed") is False:
            return str(structured.get("error") or "The preview did not close.")
        lane.note_surface("web_preview_close", {})
        lane.preview_url = None
        return None

    def _stop_retired(self) -> None:
        """Stop now (under table_lock, with nothing left to wait for), keeping each conversation's notice for the next
        broker: what it has not been told yet, and that its worker closes with this broker."""
        notices, workers = {}, 0
        for lane in self.lanes.values():
            alive = lane.engine is not None and lane.engine.alive()
            workers += alive
            notice = combine(lane.pending_notice, UPDATE_NOTICE if alive else None)
            if notice:
                notices[lane.key] = notice
        if notices:
            try:
                self.notices.keep(notices)
            except OSError as error:
                self.trace(event="notices_not_written", error=f"{type(error).__name__}: {error}"[:200])
        self.stopping.set()
        self.trace(event="broker_retired", workers=workers)

    def restart_message(self) -> str:
        with self.table_lock:
            tools = sorted(
                {f"chromatic_{l.current_tool}" for l in self.lanes.values() if l.inflight and l.current_tool}
            )
        if tools:
            work = "the " + ", ".join(tools) + " call running now finishes"
        elif self.install_busy():
            work = "the toolchain install running now finishes"
        else:
            work = "the work running now finishes"
        return f"hermretro was updated, and its game tools restart as soon as {work}."
