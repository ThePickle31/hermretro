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
from ..player import DEMO_ID
from ..system import paths
from . import provision, studio_profile

PARTS = ("games", "history", "chats", "settings", "toolchain", "logs")

# What a game's folder keeps besides its source: everything an emulator or device capture wrote.
CAPTURES = "captures"
# The broker's own logs in its run folder (its socket, token and lock stay).
LOGS = ("broker.stderr.log", "broker.stderr.log.1", "trace.jsonl", "trace.jsonl.1")
# What the library folder holds of the games (a folder the user configured may hold more). Its captures/ (the demo
# cartridge's) belong to Logs & captures.
LIBRARY = ("games.json", "games.lock", "thumbs")
# Where Hermes keeps the plugin's settings: `settings`, and `config` (the older place it still reads a setting from).
SETTINGS_KEYS = ("settings", "config")


def _bytes(*places: Path) -> int:
    return sum(provision.folder_bytes(place) for place in places if place.exists() or place.is_symlink())


def _remove(place: Path) -> None:
    """Delete a file, a link (never followed) or a folder tree; nothing when it is not there. What cannot be deleted
    stays, and the caller says so."""
    try:
        if place.is_symlink() or place.is_file():
            place.unlink(missing_ok=True)
        elif place.is_dir():
            provision.remove_tree(place)
    except OSError:
        pass


def _real_folder(folder: Path) -> Path | None:
    """``folder`` when it is a folder of its own; None when a link stands in for it (never followed)."""
    return None if folder.is_symlink() else folder


def _children(folder: Path) -> list[Path]:
    return list(folder.iterdir()) if folder.is_dir() and not folder.is_symlink() else []


def _in_library(*names: str) -> list[Path]:
    library = _real_folder(paths.library_dir())
    return [library / name for name in names] if library else []


class Refused(Exception):
    """A part the reset will not delete as things stand: ``code`` and the message say why."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _game_roots(strict: bool = False) -> list[Path]:
    """The library's games' folders. Only from the library's own file: a library folder or ``games.json`` that is a
    link (someone else's library) lists none. Unreadable, it lists none, or with ``strict`` raises Refused."""
    library = _real_folder(paths.library_dir())
    try:
        if library is None or (library / "games.json").is_symlink():
            raise ValueError("the library is a link to another")
        games = Registry(library).load()["games"]
    except Exception as error:  # noqa: BLE001 - an unreadable library has no games to list
        if strict:
            raise Refused("LIBRARY_UNREADABLE", f"The game library could not be read ({error}).") from error
        return []
    return [
        Path(entry["projectRoot"])
        for entry in games.values()
        if isinstance(entry, dict) and isinstance(entry.get("projectRoot"), str)
    ]


def _own_games(strict: bool = False) -> list[Path]:
    """The library's games in hermretro's games folder: the ones a reset deletes, with their captures (a game opened
    from a folder of the user's own leaves the library, never the disk). Only a folder recorded at its real path: one
    a link now stands in for is left alone."""
    if _real_folder(paths.games_dir()) is None:
        return []
    games = paths.games_dir().resolve()
    return [
        root for root in _game_roots(strict) if root.resolve() == root and root.is_relative_to(games) and root != games
    ]


def _log_files() -> list[Path]:
    run = paths.default_runtime_dir()
    return [run / name for name in LOGS]


def _capture_folders(data: Path) -> list[Path]:
    # The library's captures/ holds the demo cartridge's (player.demo_captures_root), and only that folder is ours.
    demo = [folder / DEMO_ID for folder in _in_library(CAPTURES) if _real_folder(folder)]
    return [data / "frames", *demo, *(root / CAPTURES for root in _own_games())]


def _chat_ids() -> list[str]:
    """The studio profile's chats (a chat's delegates go with it), read-only from its session database; none when
    there is no studio profile. Raises sqlite3.Error when the database cannot be read, or is a link (another
    profile's store: never its chats)."""
    database = studio_profile.studio_dir() / "state.db"
    if database.is_symlink():
        raise sqlite3.DatabaseError("its session database is a link to another")
    if not database.is_file():
        return []
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1.0)) as db:
        return [row[0] for row in db.execute("SELECT id FROM sessions WHERE parent_session_id IS NULL")]


def _chat_count() -> int:
    """The studio chats as Hermes lists them: each conversation and each fork of one (marked `_branched_from`), never
    a delegate or a compacted conversation's next part. Raises sqlite3.Error as _chat_ids does."""
    database = studio_profile.studio_dir() / "state.db"
    if database.is_symlink():
        raise sqlite3.DatabaseError("its session database is a link to another")
    if not database.is_file():
        return 0
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1.0)) as db:
        query = "SELECT COUNT(*) FROM sessions WHERE parent_session_id IS NULL OR model_config LIKE '%_branched_from%'"
        return db.execute(query).fetchone()[0]


def _delete_chats() -> dict:
    """Delete every studio chat the way ``hermes sessions delete`` does (its transcripts and media with it). Only in
    the profile this plugin made: a profile of the user's own with the same name is never touched."""
    if not studio_profile.studio_is_ours():
        return {
            "ok": False,
            "code": "NOT_OURS",
            "error": "The hermretro profile is not one hermretro made.",
        }
    try:
        last = None
        deleted, previous = 0, None
        # In rounds: a deleted chat's forks become chats of their own, deleted in the next one, until a round changes
        # nothing.
        while True:
            ids = _chat_ids()
            if not ids or ids == previous:
                break
            previous = ids
            for session in ids:
                try:
                    studio_profile.run_hermes(
                        studio_profile.studio_dir(),
                        "sessions",
                        "delete",
                        session,
                        "--yes",
                    )
                    deleted += 1
                except studio_profile.StudioProfileError as error:
                    last = str(error)
        left = _chat_ids()
    except sqlite3.Error as error:
        return {
            "ok": False,
            "code": "CHATS_UNREADABLE",
            "error": f"The studio chats could not be read ({error}).",
        }
    if left:
        return {
            "ok": False,
            "code": "CHATS_LEFT",
            "error": f"{len(left)} studio chats could not be deleted ({last}).",
            "partly": deleted > 0,
        }
    return {"ok": True, "removed_bytes": 0}


def _profile_holds_data() -> bool:
    """Whether deleting the studio profile would take more than it says: hermretro's own folders or a library game
    configured or made inside it (its workspace, say)."""
    studio = studio_profile.studio_dir().resolve()
    folders = (
        paths.hermretro_home(),
        paths.games_dir(),
        paths.library_dir(),
        paths.DEPS_ROOT,
        paths.setup_root(),
        *_game_roots(),
    )
    return any(folder.resolve().is_relative_to(studio) for folder in folders)


def plan(data: Path) -> dict:
    """Each part with what deleting it removes now: ``bytes``, and ``count`` for the games and chats (null when the
    chats cannot be read); ``custom`` when the toolchain is in a folder the user configured, which the reset leaves
    alone."""
    try:
        chats = _chat_count() if studio_profile.studio_is_ours() else 0
    except sqlite3.Error:
        chats = None
    custom = bool(os.environ.get("HERMRETRO_DEPS_ROOT") or os.environ.get("GB_STUDIO_SETUP_ROOT"))
    return {
        "ok": True,
        "parts": {
            "games": {
                "bytes": _bytes(*_places("games", data)),
                "count": len(_game_roots()),
            },
            "history": {"bytes": _bytes(*_places("history", data))},
            "chats": {"count": chats},
            # Whether the hermretro profile is the one this plugin made: only then may its chats or itself go. `holds`:
            # hermretro's own folders are inside it (configured there), so deleting it would take them too.
            "profile": {
                "ours": studio_profile.studio_is_ours(),
                "holds": _profile_holds_data(),
            },
            "settings": {},
            "toolchain": {
                "bytes": 0 if custom else _bytes(paths.DEPS_ROOT),
                "custom": custom,
            },
            "logs": {"bytes": _bytes(*_places("logs", data))},
        },
    }


def _stages(part: str, data: Path) -> list[list[Path]] | None:
    """What deleting ``part`` removes, in stages: a stage goes only once the one before it is gone entirely, so the
    library (which lists the games) outlives any game folder that could not be deleted. None for a part there is not."""
    if part == "history":
        # Every kept version: of builds (snapshots) and of the games' images. Both live in this profile's plugin data,
        # so deleting the studio profile takes them too.
        return [[data / "snapshots", data / "asset-versions", data / "asset-version-locks"]]
    if part == "logs":
        return [[*_log_files(), *_capture_folders(data)]]
    if part == "games":
        games = _real_folder(paths.games_dir())
        # A games folder the user configured holds more than hermretro's games: only those leave it.
        if games is None:
            own = []
        elif os.environ.get("HERMRETRO_GAMES_DIR") is None:
            own = _children(games)
        else:
            own = [*_own_games(strict=True), games / ".hermretro-installs"]
        return [own, _in_library(*LIBRARY)]
    return None


def _places(part: str, data: Path) -> list[Path]:
    """Every place of every stage, for the plan's sizes (none when the part would be refused)."""
    try:
        return [place for stage in _stages(part, data) or [] for place in stage]
    except Refused:
        return []


def clear(part: str, data: Path, homes: list[Path]) -> dict:
    """Delete one part. Answers ``{ok: true, removed_bytes}``; the toolchain answers as Setup's removal does."""
    if part == "toolchain":
        removed = provision.remove_downloads()
        return {
            **removed,
            "partly": not removed.get("ok") and removed.get("removed_bytes", 0) > 0,
        }
    if part == "chats":
        return _delete_chats()
    if part == "settings":
        linked, cleared = [], False
        for home in homes:
            entry = ((hermes_api.read_profile_config(home).get("plugins") or {}).get("entries") or {}).get(
                paths.PLUGIN_ID
            )
            # Never through a link: Hermes would write its target, maybe another profile's config. Said, since the
            # settings there stay as they are.
            if (home / "config.yaml").is_symlink():
                if isinstance(entry, dict) and any(entry.get(key) for key in SETTINGS_KEYS):
                    linked.append(home.name)
                continue
            for key in SETTINGS_KEYS:
                if isinstance(entry, dict) and entry.get(key):
                    hermes_api.write_profile_config_key(home, f"plugins.entries.{paths.PLUGIN_ID}.{key}", {})
                    cleared = True
        if linked:
            return {
                "ok": False,
                "code": "CONFIG_LINKED",
                "error": f"The {', '.join(linked)} profile's config.yaml is a link, so its hermretro settings were left.",
                "removed_bytes": 0,
                "partly": cleared,
            }
        return {"ok": True, "removed_bytes": 0}
    try:
        stages = _stages(part, data)
    except Refused as refused:
        return {"ok": False, "code": refused.code, "error": str(refused)}
    if stages is None:
        return {
            "ok": False,
            "code": "UNKNOWN_PART",
            "error": f"There is no part {part!r} to reset.",
        }
    removed = 0
    for stage in stages:
        before = _bytes(*stage)
        for place in stage:
            _remove(place)
        # A file the system refused to delete (read-only, in use) is said, never counted as gone.
        left = [place for place in stage if place.exists() or place.is_symlink()]
        removed += before - _bytes(*left)
        if left:
            return {
                "ok": False,
                "code": "PARTLY_REMOVED",
                "error": f"{len(left)} of its files or folders could not be deleted, such as {left[0]}.",
                "removed_bytes": removed,
                "partly": removed > 0 or len(left) < len(stage),
            }
    return {"ok": True, "removed_bytes": removed}
