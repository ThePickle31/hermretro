"""What assets does when other features act (backend/system/events.py)."""

from __future__ import annotations

from ..system.events import on
from . import moved, versions


@on("library.build_reported")
def keep_reported_images(assets=(), **_payload):
    """The build card shows each image as it is now, even after a later turn rewrites it."""
    versions._keep_paths(assets)


@on("library.game_moved")
def follow_moved_game(old_root=None, new_root=None, **_payload):
    """An installed game's edited copy that became a game of its own keeps its images' kept versions."""
    if isinstance(old_root, str) and isinstance(new_root, str):
        moved.move_game_versions(old_root, new_root)
