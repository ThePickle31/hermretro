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
from .skins import default_skin, page_skins

__all__ = [
    "DEMO",
    "DEMO_ID",
    "PlayerError",
    "capture_root",
    "default_skin",
    "demo_build",
    "demo_captures_root",
    "game_build",
    "get_server",
    "is_demo",
    "list_captures",
    "page_skins",
    "save_capture",
]

EVENTS: dict[str, str] = {}
