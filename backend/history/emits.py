"""History's events, one function each: call it where the thing happens (declared in the front door's EVENTS).

Other features react from their own listeners.py with @on("<event>") (backend/system/events.py).
"""

from __future__ import annotations

from ..system.events import emit


def build_kept(*, game, root) -> None:
    """Tell other features that history.build_kept happened (a successful build of library game ``game`` was
    kept as a snapshot of ``root``, its project folder)."""
    emit("history.build_kept", game=game, root=root)
