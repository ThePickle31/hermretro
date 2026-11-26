"""The games library: the user's games (games.json), each game's card (game.json + cover.png), the Build
binding between a game and its conversation, the Games/Build/Emulator page RPCs and the plugin's game tools.

Front door: what other features may use. Standard library only (the broker imports it): rpcs.py, tools.py
and hooks.py are never imported from here.
"""

from .game_card import cover_path, folder_lock
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
from .freshness import plays_game_rom, source_digest
from .ownership import editable, engine_path
from .pipeline import after_build
from .install_build import allowed as build_allowed
from .install_build import record_test_build
from .play import is_installed, no_shell_rom, plays_in_shell, rom_only_record, shell_rom, verified
from .project import ROM_STEM, built_rom_sha256, canonical_rom
from .release import installed as install_record
from .release import installed_rom

__all__ = [
    "PNG_MAGIC",
    "ROM_STEM",
    "SELECTORS",
    "Registry",
    "after_build",
    "build_allowed",
    "built_rom_sha256",
    "canonical_rom",
    "cover_path",
    "editable",
    "engine_path",
    "file_sha256",
    "folder_lock",
    "game_id",
    "has_web_export",
    "install_record",
    "installed_rom",
    "is_installed",
    "no_shell_rom",
    "plays_game_rom",
    "plays_in_shell",
    "project_file",
    "read_json",
    "record_test_build",
    "rom_only_record",
    "shell_rom",
    "source_digest",
    "valid_id",
    "verified",
    "web_dir",
    "web_rom",
]

# What the library tells other features (backend/system/events.py); payloads are keyword arguments.
EVENTS = {
    "library.build_reported": (
        "chromatic_build_report accepted a build card; game=<library id, str; None without a project>, "
        "assets=[the absolute image paths it shows, list of str]"
    ),
    "library.game_moved": (
        "An installed game's edited copy became a game of its own in a new folder (an update's keep_both): its "
        "library entry moved; old=<the library id it had, str>, new=<its library id now, str>, old_root=<the folder it was "
        "in, str>, new_root=<its folder now, str>"
    ),
    "library.game_presented": (
        "chromatic_present_game showed a game beside the chat; game=<library id, str>, root=<the project folder, str>"
    ),
}
