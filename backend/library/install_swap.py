"""Putting an updated installed game in place of the old one, so that nothing the user has is ever lost. Standard
library only.

``replace`` moves the old folder aside (into the update's staging folder, on the same disk), carries the user's own
files into the new one (``carry``), moves the new one into place and registers it. ``keep_both`` instead moves the old
folder to a new name and makes it a game of its own (a remix: ``layout.new_identity``, keeping its edited changelog),
which keeps the library entry (its chat, session and builds) and, through ``library.game_moved``, its build history;
the new version at the old place starts with a fresh entry.

The old folder is deleted only once the new one is in place and registered. A step that fails puts everything back
(the carried files, then the old folder); when even that fails, the old folder is moved to
``<games>/.hermretro-installs/recovered/`` and the error names where it is (``RECOVERY_NEEDED``). The caller holds the
game id's install lock (``installs``) and the game folder's lock; every rename here happens while the games folder's
lock is held too, so no other install claims the game's name while it is vacant.
"""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import threading
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from ..system.events import emit
from . import game_card, layout, licence, play

# The games folder's own record folder: the install locks, and old copies kept after a failed update.
STATE = ".hermretro-installs"
MAX_FOLDER_CHARS = 60
_held = threading.local()
# Records an update never carries: each belongs to the files it was made for (the LICENSE hermretro wrote, too).
RECORDS = (layout.IDENTITY_FILE, layout.INSTALL_FILE, layout.PUBLISH_FILE, layout.LICENCE_FILE, play.KEPT_ROM_FILE)
# build/ entries an update never carries: the game's ROM comes with the update and web/ is made again from it.
_FRESH_BUILD = frozenset({*(name.rsplit("/", 1)[1] for name in layout.GAME_ROMS), "web"})


class SwapError(Exception):
    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def replace(root: Path, new: Path, staging: Path, games_lock, registry) -> dict:
    """Put ``new`` in place of the installed game ``root``, carrying the user's files. ``{kept}``: the user's files
    that had a name the update now uses, kept beside it as ``<name> (yours)``."""
    previous = staging / "previous"
    moved, kept = [], []
    with games_lock():
        os.rename(root, previous)
        try:
            carry(previous, new, moved, kept)
            os.rename(new, root)
        except Exception as error:
            _undo(moved)
            _restore(previous, root, error)
    try:
        registry.forget_builds(str(root))
        registry.upsert(str(root))
    except Exception as error:
        _keep(previous, root.parent, error, "The update is in place, but the library could not record it.")
    shutil.rmtree(previous, ignore_errors=True)
    return {"kept": kept}


def keep_both(root: Path, new: Path, remix_name, games_lock, registry) -> dict:
    """Move the edited game ``root`` to a new folder (``remix_name()``, chosen while the games folder is locked) as a
    game of its own and put ``new`` in its place."""
    with games_lock():
        remix = remix_name()
        os.rename(root, remix)
        saved = _records(remix)
        kept = play.rom_only_record(remix)  # a game without its source: the remix still plays its checked ROM
        try:
            layout.new_identity(remix, fresh_changelog=False)
            os.rename(new, root)
            if kept is not None:
                play.keep_rom(remix, kept)
        except Exception as error:
            _put_back(saved)
            _restore(remix, root, error)
    try:
        moved = registry.move(str(root), str(remix))
        registry.upsert(str(root))
    except Exception as error:
        raise SwapError(
            "REGISTER_FAILED",
            f"Both games are in place ({root} and your edited copy {remix}), but the library could not record them.",
            remix=str(remix),
        ) from error
    if moved:
        emit("library.game_moved", old=moved[0], new=moved[1], old_root=str(root), new_root=str(remix))
    return {"remix": str(remix)}


def carry(old: Path, new: Path, moved: list, kept: list) -> None:
    """Move what the user has in the old folder and the update does not bring into the new one: the local folders
    and files (``docs/``, ``captures/``, ``save-states/``, ``scratch/``, anything else), ``build/``'s other files and the
    record folder (its lock file is the one held while updating). Folders are merged; where the update now has a
    file of the same name (letter case and Unicode spelling aside), the user's is kept beside it as
    ``<name> (yours)``. Every move is appended to ``moved`` as ``(new path, old path)``; ``kept`` gets the renamed."""
    for name in sorted(os.listdir(old)):
        here = old / name
        if name == layout.STATE_DIR and _folder(here):
            (new / name).mkdir(exist_ok=True)
            for record in sorted(os.listdir(here)):
                if record == game_card.LOCK_FILE:
                    _move(here / record, new / name / record, moved, replace=True)
                elif record not in RECORDS:
                    _merge(here / record, new / name, moved, kept)
        elif name == "build" and _folder(here):
            (new / name).mkdir(exist_ok=True)
            for item in sorted(os.listdir(here)):
                if item not in _FRESH_BUILD:
                    _merge(here / item, new / name, moved, kept)
        elif layout.kind_of(old, name) == "local":
            _merge(here, new, moved, kept)


def _merge(path: Path, into: Path, moved: list, kept: list) -> None:
    existing = _same_name(into, path.name)
    if existing is None:
        _move(path, into / path.name, moved)
    elif _folder(path) and _folder(existing):
        for item in sorted(os.listdir(path)):
            _merge(path / item, existing, moved, kept)
    else:
        target = _free(into, path)
        _move(path, target, moved)
        kept.append(str(target))


def _same_name(folder: Path, name: str) -> Path | None:
    """The entry of ``folder`` that is ``name`` on a Mac's disk (letter case and Unicode spelling aside)."""
    key = unicodedata.normalize("NFC", name).casefold()
    for other in os.listdir(folder):
        if unicodedata.normalize("NFC", other).casefold() == key:
            return folder / other
    return None


def _free(folder: Path, path: Path) -> Path:
    """A name in ``folder`` for the user's ``path`` beside the update's own: ``<name> (yours)``, ``(yours 2)``, …"""
    stem, suffix = (path.stem, path.suffix) if path.is_file() else (path.name, "")
    for number in range(1, 1000):
        candidate = f"{stem} ({'yours' if number == 1 else f'yours {number}'}){suffix}"
        if _same_name(folder, candidate) is None:
            return folder / candidate
    raise OSError(f"No free name for {path.name} in {folder}.")


def _move(source: Path, target: Path, moved: list, *, replace: bool = False) -> None:
    (os.replace if replace else os.rename)(source, target)
    moved.append((target, source))


def _undo(moved: list) -> None:
    for there, here in reversed(moved):
        try:
            os.rename(there, here)
        except OSError:
            pass


def _restore(aside: Path, root: Path, error: Exception) -> None:
    """Put the old folder back where it was after a failed step; when that fails too, keep it safe and say where."""
    try:
        os.rename(aside, root)
    except OSError:
        _keep(aside, root.parent, error, "The update failed and the game could not be put back.")
    raise SwapError("SWAP_FAILED", f"The update could not be put in place ({error}); nothing was changed.") from error


def _keep(folder: Path, games: Path, error: Exception, sentence: str):
    place = games / STATE / "recovered" / f"{folder.name}-{int(time.time())}"
    place.parent.mkdir(parents=True, exist_ok=True)
    os.rename(folder, place)
    raise SwapError("RECOVERY_NEEDED", f"{sentence} Your previous copy is kept at {place}.", kept=str(place)) from error


def _records(root: Path) -> dict:
    """The files ``new_identity`` rewrites (its ``ensure`` can write ``LICENSE``), as they are now (None for one that is
    missing)."""
    files = [
        root / game_card.CARD_FILE,
        root / "CHANGELOG.md",
        root / licence.LICENSE_FILE,
        *(root / layout.STATE_DIR / name for name in RECORDS),
    ]
    return {path: (path.read_bytes() if path.is_file() else None) for path in files}


def _put_back(saved: dict) -> None:
    for path, data in saved.items():
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(data)


def _folder(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink()


# -- the games folder ------------------------------------------------------------------------------


@contextmanager
def id_lock(games: Path, identifier: str):
    """One install or update of a game id at a time on this machine (a file lock in the games folder's own record
    folder, outside every game folder, so it holds while a game folder is renamed). Taken again by the same thread,
    it is already held."""
    held = _held.__dict__.setdefault("ids", set())
    key = (os.path.realpath(games), identifier)
    if key in held:
        yield
        return
    folder = Path(games) / STATE
    folder.mkdir(exist_ok=True)
    with open(folder / f"{identifier}.lock", "a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        held.add(key)
        try:
            yield
        finally:
            held.discard(key)
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def games_lock(games: Path):
    """Choosing a game folder's name and moving folders in and out of the games folder happen one at a time."""
    folder = Path(games) / STATE
    folder.mkdir(exist_ok=True)
    with open(folder / "games.lock", "a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def unique_folder(games: Path, title: str) -> Path:
    """A folder in ``games`` named after the game that does not exist yet (``Name``, ``Name 2``, …), letter case
    aside (a Mac's disk)."""
    name = (
        re.sub(r"[/\\:\x00-\x1f\x7f]", " ", title or "").strip().strip(".").strip()[:MAX_FOLDER_CHARS].strip() or "Game"
    )
    taken = {entry.casefold() for entry in os.listdir(games)}
    for number in range(1, 1000):
        candidate = name if number == 1 else f"{name} {number}"
        if candidate.casefold() not in taken:
            return games / candidate
    raise SwapError("NO_FOLDER", f"There are too many games named {name}.")
