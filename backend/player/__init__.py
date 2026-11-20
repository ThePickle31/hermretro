"""The browser player server the page and the present tool show games in (ModRetro's real web player on a
loopback port, one server per gateway process). Standard library only.

Front door: what other features may use.
"""

from .server import (
    DEMO,
    DEMO_ID,
    PlayerError,
    capture_root,
    demo_build,
    demo_captures_root,
    game_build,
    get_server,
    is_demo,
    list_captures,
    save_capture,
)

__all__ = [
    "DEMO",
    "DEMO_ID",
    "PlayerError",
    "capture_root",
    "demo_build",
    "demo_captures_root",
    "game_build",
    "get_server",
    "is_demo",
    "list_captures",
    "save_capture",
]

EVENTS: dict[str, str] = {}
