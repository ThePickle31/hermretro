"""What history does when other features act (backend/system/events.py)."""

from __future__ import annotations

import os

from ..system.events import on
from .rpcs import _snapshots_dir
from .snapshots import game_dir


@on("library.game_moved")
def follow_moved_game(old=None, new=None, **_payload):
    """An installed game's edited copy moved to a folder of its own keeps its build history: the snapshots kept
    under its old library id move to its new one (unless the new id has some already)."""
    if not (isinstance(old, str) and isinstance(new, str)) or old == new:
        return
    before, after = game_dir(_snapshots_dir(), old), game_dir(_snapshots_dir(), new)
    if before.is_dir() and not os.path.lexists(after):
        os.rename(before, after)
