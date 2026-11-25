"""Installing a game from a link, and updating it: Hermes's install from git, for games. Standard library only; the
network is reached only through ``install_source`` (git).

    inspect(link)                 read the game at its branch's tip, without installing: what it is and the exact commit
    install(link, commit)         install exactly that commit (refused when the branch moved since)
    check_update(root)            whether the source's branch moved past the installed commit (read only)
    update(root, choice=...)      install the newest commit over the game, keeping the user's own files

Every fetch is a shallow clone into a hidden ``.install-*`` folder beside the games (the same file system, so the game
moves into place with one rename). The folder is checked (``install_check``) before anything reaches the library; git's
own ``.git`` is removed, ``layout.ensure`` gives the game its layout and ``release.record_install`` its record
(``.hermretro/install.json``). One game id is installed once per machine: the same game from the same source is an
update, from another source it is refused. An update of a game the user edited since it was installed changes nothing
until the user chooses: ``keep_mine``, ``take_theirs``, or ``keep_both`` (the edited copy becomes a remix, a game of
its own: ``layout.new_identity``).
"""

from __future__ import annotations

import base64
import fcntl
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..system import paths
from . import game_card, install_check, layout, release
from .games import Registry
from .install_source import Source, SourceError, clone, is_commit, remote_commit, resolve, within

CHOICES = ("keep_mine", "take_theirs", "keep_both")
MAX_README_CHARS = 64 * 1024
MAX_FOLDER_CHARS = 60
# What an update never carries from the old folder into the new one: the game's own files come from the update, and
# build/web is made again from them.
_NOT_CARRIED_FROM_BUILD = frozenset({*(name.rsplit("/", 1)[1] for name in layout.GAME_ROMS), "web"})


class InstallError(Exception):
    """An install or update that did not happen: ``code``, a sentence for the user, and ``details`` (``problems``,
    the games that already have the id, …). Nothing was changed."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        return {"ok": False, "code": self.code, "error": self.message, **self.details}


def inspect(link: str, *, registry: Registry | None = None) -> dict:
    """What the link holds now, read from a clone in a temporary folder outside the games: ``{ok, source, commit,
    title, id, version, format, mode, rom, cover, readme, problems, warnings, needsPluginConsent, alreadyInstalled}``.
    ``commit`` is what ``install`` must be given. Reads the card, cover and README as data only."""
    source = _resolve(link)
    with tempfile.TemporaryDirectory(prefix="hermretro-inspect-") as workspace:
        folder, commit = _fetch(source, Path(workspace))
        report = install_check.check(folder)
        card = report["card"]
        identifier = card.get("id") if isinstance(card.get("id"), str) else None
        return {
            "ok": report["ok"],
            "source": source.canonical,
            "commit": commit,
            "title": card.get("title") if isinstance(card.get("title"), str) else None,
            "id": identifier,
            "version": card.get("gameVersion"),
            "format": card.get("format", 1),
            "mode": report["mode"],
            "rom": report["rom"],
            "cover": _cover_url(folder),
            "readme": _readme(folder),
            "problems": report["problems"],
            "warnings": report["warnings"],
            "needsPluginConsent": report["needsPluginConsent"],
            "alreadyInstalled": _holders(_registry(registry), identifier, source) if identifier else [],
        }


def install(
    link: str,
    commit: str,
    *,
    registry: Registry | None = None,
    games_dir: Path | None = None,
    allow_plugins: bool = False,
) -> dict:
    """Install the game the link holds at ``commit`` (from ``inspect``) into the games folder and the library.
    ``{ok, root, title, mode, commit, testBuildDue}``; an install of a game already installed from the same source
    answers what ``update`` does. Raises ``InstallError`` and changes nothing when it cannot install."""
    source = _resolve(link)
    if not is_commit(commit):
        raise InstallError("BAD_COMMIT", "Install the exact commit inspect read (40 hex digits).")
    registry = _registry(registry)
    games = Path(games_dir) if games_dir else paths.games_dir(create=True)
    games.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".install-", dir=games))
    try:
        folder, head = _fetch(source, staging, commit)
        report = _checked(folder, allow_plugins)
        identifier = report["card"]["id"]
        with _games_lock(games):
            holders = _holders(registry, identifier, source)
            same = [holder for holder in holders if holder["sameSource"]]
            if not holders:
                game = _finish(staging, folder, source, head, report["mode"])
                root = _place(game, games, report["card"]["title"])
                registry.upsert(str(root))
                return _done(root, report["mode"], head, changed=True)
        if not same:
            raise InstallError(
                "ALREADY_HAVE",
                "You already have this game from another source. Remix it to keep both.",
                alreadyInstalled=holders,
            )
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return update(same[0]["root"], commit=commit, registry=registry, allow_plugins=allow_plugins)


def check_update(root: Path) -> dict:
    """``{available, commit, remoteCommit}``: whether the installed game's branch is at another commit now. Reads
    the remote (``git ls-remote``) and changes nothing."""
    record = _record(Path(root))
    remote = _guard(lambda: remote_commit(_source(record)))
    return {"available": remote != record.get("commit"), "commit": record.get("commit"), "remoteCommit": remote}


def update(
    root: Path,
    *,
    choice: str | None = None,
    commit: str | None = None,
    registry: Registry | None = None,
    allow_plugins: bool = False,
) -> dict:
    """Install the newest commit of the game's source (or exactly ``commit``) over the installed game, keeping the
    files the user added (``docs/``, ``captures/``, ``save-states/``, …) and its record folder. When the user edited
    the game since it was installed, nothing changes until ``choice`` says what to do (``{needsChoice: True}``).
    ``{ok, root, mode, commit, changed, testBuildDue, remix?}``."""
    root = Path(root)
    if choice is not None and choice not in CHOICES:
        raise InstallError("BAD_CHOICE", f"Choose one of {', '.join(CHOICES)}.")
    if commit is not None and not is_commit(commit):
        raise InstallError("BAD_COMMIT", "Update to an exact commit (40 hex digits).")
    registry = _registry(registry)
    _record(root)  # before the lock, which would make the record folder of a folder that is no game
    remix = None
    with game_card.folder_lock(root):
        record = _record(root)
        edited = release.local_edits(root) is True
        if edited and choice is None:
            return {"ok": False, "needsChoice": True, "root": str(root), "choices": list(CHOICES)}
        if edited and choice == "keep_mine":
            return _done(root, record["mode"], record.get("commit"), changed=False)
        staging = Path(tempfile.mkdtemp(prefix=".install-", dir=root.parent))
        try:
            source = _source(record)
            folder, head = _fetch(source, staging, commit)
            if head == record.get("commit") and not edited:
                return _done(root, record["mode"], head, changed=False)
            report = _checked(folder, allow_plugins)
            if report["card"]["id"] != layout.game_identity(root):
                raise InstallError(
                    "ANOTHER_GAME", "The source now holds a different game; it was not installed over this one."
                )
            game = _finish(staging, folder, source, head, report["mode"])
            if edited and choice == "keep_both":
                with _games_lock(root.parent):
                    remix = _unique(root.parent, f"{report['card']['title']} (edited)")
                    os.rename(root, remix)
                aside, moved = remix, []
            else:
                aside = staging / "previous"
                os.rename(root, aside)
                moved = []
            try:
                if remix is None:
                    _carry(aside, game, moved)
                os.rename(game, root)
            except OSError:
                for there, here in reversed(moved):  # the user's files go back where they were
                    os.replace(there, here)
                os.rename(aside, root)
                raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    if remix is not None:
        layout.new_identity(remix)
        registry.upsert(str(remix))
    registry.upsert(str(root))
    return {**_done(root, report["mode"], head, changed=True), **({"remix": str(remix)} if remix else {})}


# -- the steps -------------------------------------------------------------------------------------


def _resolve(link: str) -> Source:
    return _guard(lambda: resolve(link))


def _guard(step):
    try:
        return step()
    except SourceError as error:
        raise InstallError(error.code, error.message) from error


def _fetch(source: Source, workspace: Path, commit: str | None = None) -> tuple[Path, str]:
    """Clone ``source`` into ``workspace/clone``; the game folder in it and the commit checked out. A ``commit`` the
    branch is no longer at is refused (``SOURCE_MOVED``): what installs is what was reviewed."""
    checkout = workspace / "clone"
    head = _guard(lambda: clone(source, checkout))
    if commit is not None and head != commit:
        raise InstallError(
            "SOURCE_MOVED", "The game changed since it was read; read it again to see the new version.", commit=head
        )
    return _guard(lambda: within(checkout, source.subdir)), head


def _checked(folder: Path, allow_plugins: bool) -> dict:
    report = install_check.check(folder)
    if not report["ok"]:
        raise InstallError("NOT_INSTALLABLE", "This game cannot be installed.", problems=report["problems"])
    if report["needsPluginConsent"] and not allow_plugins:
        raise InstallError(
            "PLUGINS",
            "This game's source has GB Studio plugins: code that runs on this computer when the game is built.",
            needsPluginConsent=True,
        )
    return report


def _finish(staging: Path, folder: Path, source: Source, commit: str, mode: str) -> Path:
    """The fetched folder as an installed game, still in staging: no ``.git``, the game's own folder (out of a
    subfolder of the repository), its layout and its install record."""
    shutil.rmtree(staging / "clone" / ".git", ignore_errors=False)
    game = staging / "game"
    os.rename(folder, game)
    # The record folder is this machine's: one that came with the game (a forged id or install record) is dropped.
    shutil.rmtree(game / layout.STATE_DIR, ignore_errors=True)
    layout.ensure(game)
    release.record_install(game, source={"canonical": source.canonical, **source.record()}, commit=commit, mode=mode)
    return game


def _place(game: Path, games: Path, title: str) -> Path:
    target = _unique(games, title)
    os.rename(game, target)
    return target


def _unique(games: Path, title: str) -> Path:
    """A folder in ``games`` named after the game that does not exist yet (``Name``, ``Name 2``, …)."""
    name = (
        re.sub(r"[/\\:\x00-\x1f\x7f]", " ", title or "").strip().strip(".").strip()[:MAX_FOLDER_CHARS].strip() or "Game"
    )
    for number in range(1, 1000):
        candidate = games / (name if number == 1 else f"{name} {number}")
        if not os.path.lexists(candidate):
            return candidate
    raise InstallError("NO_FOLDER", f"There are too many games named {name}.")


def _carry(old: Path, new: Path, moved: list) -> None:
    """Move what the user has in the old folder that the update does not hold into the new one: local folders and
    files (``docs/``, ``captures/``, ``save-states/``, …), ``build/``'s other files and the record folder (whose lock
    file is the one held while updating). Each move is appended to ``moved`` as ``(new path, old path)``."""

    def move(here: Path, there: Path) -> None:
        os.replace(here, there)
        moved.append((there, here))

    for name in os.listdir(old):
        here, there = old / name, new / name
        if name == layout.STATE_DIR and here.is_dir() and not here.is_symlink():
            there.mkdir(exist_ok=True)
            for record in os.listdir(here):
                if record != layout.INSTALL_FILE and (record == game_card.LOCK_FILE or not (there / record).exists()):
                    move(here / record, there / record)
        elif name == "build" and here.is_dir() and not here.is_symlink():
            there.mkdir(exist_ok=True)
            for item in os.listdir(here):
                if item not in _NOT_CARRIED_FROM_BUILD and not os.path.lexists(there / item):
                    move(here / item, there / item)
        elif layout.kind_of(old, name) == "local" and not os.path.lexists(there):
            move(here, there)


def _done(root: Path, mode: str, commit: str | None, *, changed: bool) -> dict:
    return {
        "ok": True,
        "root": str(root),
        "title": game_card.load(root).get("title"),
        "mode": mode,
        "commit": commit,
        "changed": changed,
        # A game with its source is built once on this computer, so its ROM is known to come from that source.
        "testBuildDue": changed and mode == "game+source",
    }


# -- the library ------------------------------------------------------------------------------------


def _registry(registry: Registry | None) -> Registry:
    return registry if registry is not None else Registry(paths.library_dir())


def _record(root: Path) -> dict:
    record = release.installed(root)
    if record is None:
        raise InstallError("NOT_INSTALLED", "This game was made here, not installed from a link.")
    return record


def _source(record: dict) -> Source:
    source = record["source"]
    return Source(source.get("url") or "", source.get("ref"), source.get("subdir"))


def _holders(registry: Registry, identifier: str, source: Source) -> list[dict]:
    """The library's games with this game id: ``{root, title, sameSource}`` (installed from the same source)."""
    found = []
    for entry in registry.load()["games"].values():
        stored = entry.get("projectRoot") if isinstance(entry, dict) else None
        if not isinstance(stored, str) or not os.path.isdir(stored):
            continue
        root = Path(stored)
        if identifier not in (layout.game_identity(root), game_card.load(root).get("id")):
            continue
        record = release.installed(root)
        same = record is not None and record["source"].get("canonical") == source.canonical
        found.append({"root": str(root), "title": game_card.load(root).get("title"), "sameSource": same})
    return found


@contextmanager
def _games_lock(games: Path):
    """One install at a time in a games folder: the id check and the move into place happen together."""
    with open(Path(games) / ".install.lock", "a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _cover_url(folder: Path) -> str | None:
    cover = folder / game_card.COVER_FILE
    if cover.is_symlink() or not cover.is_file() or cover.stat().st_size > game_card.MAX_COVER_BYTES:
        return None
    return "data:image/png;base64," + base64.b64encode(cover.read_bytes()).decode()


def _readme(folder: Path) -> str | None:
    readme = folder / "README.md"
    if readme.is_symlink() or not readme.is_file():
        return None
    with readme.open(encoding="utf-8", errors="replace") as handle:
        return handle.read(MAX_README_CHARS)
