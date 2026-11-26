"""The factory reset's backend half (`reset_rpcs.py`): what each part of hermretro's data holds (`plan`), and
deleting one part (`clear`). The studio chats are deleted with Hermes's own `hermes sessions delete`; the studio
profile is Hermes's, so the page deletes it through Hermes itself. The caller holds the broker stopped
(`broker_stop.broker_stopped`) for every part but the settings, so nothing runs from the folders meanwhile.

``data`` is this profile's plugin data folder (``host._data_dir()``: build history, kept image versions, saved
frames), ``homes`` the profile folders whose hermretro settings go back to their defaults."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

from ..hermes import api as hermes_api
from ..library import Registry
from ..system import paths
from . import provision, studio_profile

PARTS = ("games", "history", "chats", "settings", "toolchain", "logs")

# What a game's folder keeps besides its source: everything an emulator or device capture wrote.
CAPTURES = "captures"
# The broker's own logs in its run folder (its socket, token and lock stay).
LOGS = ("broker.stderr.log", "trace.jsonl", "trace.jsonl.1")
SETTINGS_KEY = f"plugins.entries.{paths.PLUGIN_ID}.settings"


def _bytes(*places: Path) -> int:
    return sum(provision.folder_bytes(place) for place in places if place.exists() or place.is_symlink())


def _remove(place: Path) -> None:
    """Delete a file, a link (never followed) or a folder tree; nothing when it is not there."""
    if place.is_symlink() or place.is_file():
        place.unlink(missing_ok=True)
    elif place.is_dir():
        provision.remove_tree(place)


def _children(folder: Path) -> list[Path]:
    return list(folder.iterdir()) if folder.is_dir() and not folder.is_symlink() else []


def _game_roots() -> list[Path]:
    """The library's games' folders; none when the library cannot be read."""
    try:
        games = Registry(paths.library_dir()).load()["games"]
    except Exception:  # noqa: BLE001 - an unreadable library has no games to list
        return []
    return [
        Path(entry["projectRoot"])
        for entry in games.values()
        if isinstance(entry, dict) and isinstance(entry.get("projectRoot"), str)
    ]


def _own_games() -> list[Path]:
    """The library's games in hermretro's games folder: the ones a reset deletes (a game opened from a folder of
    the user's own leaves the library, never the disk)."""
    games = paths.games_dir().resolve()
    return [root for root in _game_roots() if root.resolve().is_relative_to(games) and root.resolve() != games]


def _log_files() -> list[Path]:
    run = paths.default_runtime_dir()
    return [run / name for name in LOGS]


def _capture_folders(data: Path) -> list[Path]:
    return [data / "frames", paths.library_dir() / CAPTURES, *(root / CAPTURES for root in _game_roots())]


def _chat_ids() -> list[str] | None:
    """The studio profile's chats (a chat's delegates go with it), read-only from its session database; None when
    there is no studio profile or its database cannot be read."""
    database = studio_profile.studio_dir() / "state.db"
    if not database.is_file():
        return None
    try:
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1.0)) as db:
            return [row[0] for row in db.execute("SELECT id FROM sessions WHERE parent_session_id IS NULL")]
    except sqlite3.Error:
        return None


def _delete_chats() -> dict:
    """Delete every studio chat the way ``hermes sessions delete`` does (its transcripts and media with it)."""
    ids = _chat_ids()
    if ids is None:
        return {"ok": True, "removed_bytes": 0}
    last = None
    for session in ids:
        try:
            studio_profile.run_hermes(studio_profile.studio_dir(), "sessions", "delete", session, "--yes")
        except studio_profile.StudioProfileError as error:
            last = str(error)
    left = _chat_ids() or []
    if left:
        return {"ok": False, "code": "CHATS_LEFT", "error": f"{len(left)} studio chats could not be deleted ({last})."}
    return {"ok": True, "removed_bytes": 0}


def plan(data: Path) -> dict:
    """Each part with what it holds now: ``bytes``, and ``count`` for the games; ``custom`` when its folder is one the
    user configured, so the reset leaves it alone."""
    games = paths.games_dir()
    return {
        "ok": True,
        "parts": {
            "games": {
                "bytes": _bytes(games, paths.library_dir(), data / "asset-versions"),
                "count": len(_game_roots()),
            },
            "history": {"bytes": _bytes(data / "snapshots")},
            "chats": {"count": len(_chat_ids() or [])},
            "settings": {},
            "toolchain": {
                "bytes": _bytes(paths.DEPS_ROOT),
                "custom": bool(os.environ.get("HERMRETRO_DEPS_ROOT") or os.environ.get("GB_STUDIO_SETUP_ROOT")),
            },
            "logs": {"bytes": _bytes(*_log_files(), *_capture_folders(data))},
        },
    }


def _places(part: str, data: Path) -> list[Path] | None:
    """What deleting ``part`` removes; None for a part there is not."""
    if part == "history":
        return [data / "snapshots"]
    if part == "logs":
        return [*_log_files(), *_capture_folders(data)]
    if part == "games":
        games = paths.games_dir()
        # A games folder the user configured holds more than hermretro's games: only those leave it.
        own = (
            _children(games)
            if os.environ.get("HERMRETRO_GAMES_DIR") is None
            else [*_own_games(), games / ".hermretro-installs"]
        )
        return [*own, *_children(paths.library_dir()), data / "asset-versions", data / "asset-version-locks"]
    return None


def clear(part: str, data: Path, homes: list[Path]) -> dict:
    """Delete one part. Answers ``{ok: true, removed_bytes}``; the toolchain answers as Setup's removal does."""
    if part == "toolchain":
        return provision.remove_downloads()
    if part == "chats":
        return _delete_chats()
    if part == "settings":
        for home in homes:
            entry = ((hermes_api.read_profile_config(home).get("plugins") or {}).get("entries") or {}).get(
                paths.PLUGIN_ID
            )
            if isinstance(entry, dict) and entry.get("settings"):
                hermes_api.write_profile_config_key(home, SETTINGS_KEY, {})
        return {"ok": True, "removed_bytes": 0}
    places = _places(part, data)
    if places is None:
        return {"ok": False, "code": "UNKNOWN_PART", "error": f"There is no part {part!r} to reset."}
    removed = _bytes(*places)
    for place in places:
        _remove(place)
    return {"ok": True, "removed_bytes": removed}
