"""Holding a game for an update of its files: while an installed game is replaced by a newer version (the library's
``installs.update``), no conversation may have it open, and none may open it until the hold is released.

Control ops ``hold_game {root}`` and ``release_game {root}``. A hold is refused with ``GAME_BUSY`` while any
conversation's worker has the game selected (or, for a game installed without its source, as its workspace) and is
alive (working on it, or open and idle: its engine still holds the old files), and it forgets the selection of a
worker that is gone, so nothing points at the old folder. A hold lasts at most ``HOLD_SECONDS`` (a gateway that
stopped mid-update does not keep the game shut). Releasing it closes the worker of any conversation that opened the
game meanwhile and forgets its selection, so the next call opens the new files. ``refuse_held`` runs before every
tool call. Stdlib only and no Hermes imports: the broker runs as ``python -m backend.broker``.
"""

from __future__ import annotations

import os
import time

from .lane import Denied

HOLD_SECONDS = 600
BUSY = (
    "This game is being updated to a newer version. Wait for the update to finish, then try again. Nothing was changed."
)


class HoldsMixin:
    """The Broker's game holds (its ``held_roots``: real game folder -> when the hold ends, monotonic)."""

    def game_hold(self, request: dict) -> dict:
        root = request.get("root")
        if not isinstance(root, str) or not os.path.isabs(root):
            raise Denied("INVALID_ARGUMENTS", "hold_game and release_game take the game's absolute folder.")
        root = os.path.realpath(root)
        if request.get("op") == "release_game":
            self._release_hold(root)
        else:
            self._take_hold(root)
        return {"ok": True}

    def _take_hold(self, root: str, *, seconds: float = HOLD_SECONDS) -> None:
        """Hold ``root`` for ``seconds``, or refuse with ``GAME_BUSY``: it is held already (holds are exclusive), or
        a conversation has it open. The worker of a conversation that no longer owns a game it had as its workspace
        (Stop editing) is closed first, once its work has settled, so it does not keep the game busy."""
        self._close_detached(root)
        with self.table_lock:
            held = self._live_holds()
            if root in held:
                raise Denied("GAME_BUSY", BUSY)
            for lane in self.lanes.values():
                if root not in (lane.selected_root, lane.engine_workspace):
                    continue
                if lane.inflight or (lane.engine and lane.engine.alive()):
                    raise Denied(
                        "GAME_BUSY",
                        "This game is open in a conversation. Stop editing it (or wait until that chat is idle and "
                        "its worker has closed), then update it.",
                    )
                self._forget_selection(lane)  # a worker that is gone: its selection would point at the old files
            held[root] = time.monotonic() + seconds
        self.trace(event="game_held", root_name=os.path.basename(root))

    def _close_detached(self, root: str) -> None:
        with self.table_lock:
            detached = [
                lane
                for lane in self.lanes.values()
                if lane.engine_workspace == root and not lane.inflight and self.rom_only_root(lane) != root
            ]
        for lane in detached:  # outside the table lock: closing takes the lane's start lock first
            self.close_lane_engine(lane, "game no longer this conversation's")
            lane.engine_workspace = lane.rom_workspace = None

    def _release_hold(self, root: str) -> None:
        with self.table_lock:
            self._live_holds().pop(root, None)
            stale = [
                lane
                for lane in self.lanes.values()
                if root in (lane.selected_root, lane.engine_workspace) and not lane.inflight
            ]
            for lane in stale:
                self._forget_selection(lane)
        for lane in stale:  # a worker that opened the game while it was held has the old files loaded
            self.close_lane_engine(lane, "game updated")
        self.trace(event="game_released", root_name=os.path.basename(root))

    def _forget_selection(self, lane) -> None:
        self._release_root(lane)
        lane.selected_root = lane.selected_project_path = None

    def refuse_held(self, lane, target: str | None) -> None:
        """Refuse a tool call that would reach a held game: the one this conversation has open, or the one it opens."""
        with self.table_lock:
            held = self._live_holds()
            roots = {lane.selected_root, lane.rom_workspace, os.path.realpath(target) if target else None} - {None}
            if any(root in held for root in roots):
                raise Denied("GAME_BUSY", BUSY)

    def _live_holds(self) -> dict:
        held = self.__dict__.setdefault("held_roots", {})
        now = time.monotonic()
        for root in [root for root, until in held.items() if until <= now]:
            del held[root]
        return held
