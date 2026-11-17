"""What assets does when other features act (backend/system/events.py)."""

from __future__ import annotations

from ..system.events import on
from . import versions


@on("library.build_reported")
def keep_reported_images(assets=(), **_payload):
    """The build card shows each image as it is now, even after a later turn rewrites it."""
    versions._keep_paths(assets)
