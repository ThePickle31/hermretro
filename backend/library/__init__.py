"""The games library: the user's games (games.json), each game's card (game.json + cover.png), the Build
binding between a game and its conversation, the Games/Build/Emulator page RPCs and the plugin's game tools.

Front door: what other features may use. Standard library only (the broker imports it): rpcs.py, tools.py
and hooks.py are never imported from here.
"""

from .game_card import cover_path
from .games import (
    PNG_MAGIC,
    SELECTORS,
    Registry,
    file_sha256,
    game_id,
    has_web_export,
    project_file,
    valid_id,
    web_dir,
    web_rom,
)
from .games import _json as read_json
from .project import canonical_rom

__all__ = [
    "PNG_MAGIC",
    "SELECTORS",
    "Registry",
    "canonical_rom",
    "cover_path",
    "file_sha256",
    "game_id",
    "has_web_export",
    "project_file",
    "read_json",
    "valid_id",
    "web_dir",
    "web_rom",
]

# What the library tells other features (backend/system/events.py); payloads are keyword arguments.
EVENTS = {
    "library.build_reported": (
        "chromatic_build_report accepted a build card; game=<library id, str; None without a project>, "
        "assets=[the absolute image paths it shows, list of str]"
    ),
    "library.game_presented": (
        "chromatic_present_game showed a game beside the chat; game=<library id, str>, root=<the project folder, str>"
    ),
}
