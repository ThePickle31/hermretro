"""Installing a game from a link, and updating it: Hermes's install from git, for games. Standard library only; the
network is reached only through ``install_git``.

    inspect(link)                       read the game at its branch's tip without installing it: what it is, and the
                                        exact ``commit`` and ``source`` (branch included) to install
    install(source, commit, workers=)   install exactly that commit (refused when the branch moved since)
    check_update(root)                  whether the branch moved past the installed commit (read only)
    update(root, workers=, choice=)     install the newest commit over the game, keeping the user's own files

Every fetch goes into a hidden ``.install-*`` folder in the games folder (the same disk, so the game moves into place
with one rename): bounded (``install_git.fetch``), its tree checked before checkout, only the files its mode publishes
taken (``install_check.take_payload``) and checked (``install_check.check``). Then ``layout.ensure`` gives the game its
layout and ``release.record_install`` its record. One game id is installed once per machine: the same game from the
same source (the same repository and folder; the branch may differ) is an update, from another source it is refused.

Every install and update of one game id holds that id's lock (``<games>/.hermretro-installs/<id>.lock``) from the id
check to the registration, and an update also holds the game folder's lock (a history restore takes it too) and the
broker's hold on the game (``workers``: ``game_workers.BrokerWorkers``), so no conversation has the game open while
its files are replaced (``GAME_BUSY``). An update of a game the user edited since it was installed changes nothing
until the user chooses: ``keep_mine``, ``take_theirs``, or ``keep_both`` (``install_swap``).
"""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
from pathlib import Path

from ..system import paths
from . import game_card, install_check, install_git, install_swap, layout, release
from .games import Registry
from .install_source import Source, SourceError, resolve, within

CHOICES = ("keep_mine", "take_theirs", "keep_both")
MAX_README_CHARS = 64 * 1024


class InstallError(Exception):
    """An install or update that did not happen: ``code``, a sentence for the user, and ``details`` (``problems``,
    the games that already have the id, …). Nothing was changed, unless ``details`` says where something was kept."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        return {"ok": False, "code": self.code, "error": self.message, **self.details}


def inspect(link, *, registry: Registry | None = None, allow_local: bool = False) -> dict:
    """What the link holds now, read from a fetch in a temporary folder outside the games: ``{ok, source, commit,
    title, id, version, format, mode, rom, cover, readme, problems, warnings, needsPluginConsent, alreadyInstalled}``.
    ``source`` (``{canonical, url, ref, subdir}``) and ``commit`` are what ``install`` is given."""
    source = _settled(link, allow_local)
    with tempfile.TemporaryDirectory(prefix="hermretro-inspect-") as workspace:
        workspace = Path(workspace)
        try:
            game, commit, report = _prepare(source, workspace)
        except InstallError as error:
            if error.code != "NOT_INSTALLABLE":
                raise
            return {"ok": False, "source": source.record(), "commit": error.details.get("commit"), **error.details}
        card = report["card"]
        return {
            "ok": True,
            "source": source.record(),
            "commit": commit,
            "title": card.get("title"),
            "id": card.get("id"),
            "version": card.get("gameVersion"),
            "format": card.get("format", 1),
            "mode": report["mode"],
            "rom": report["rom"],
            "cover": _cover_url(game),
            "readme": _readme(game),
            "problems": [],
            "warnings": report["warnings"],
            "needsPluginConsent": report["needsPluginConsent"],
            "alreadyInstalled": _holders(_registry(registry), card["id"], source),
        }


def install(
    source,
    commit: str,
    *,
    workers,
    registry: Registry | None = None,
    games_dir: Path | None = None,
    allow_plugins: bool = False,
    allow_local: bool = False,
) -> dict:
    """Install the game ``source`` (a link, or ``inspect``'s ``source``) holds at ``commit`` into the games folder and
    the library: ``{ok, root, title, mode, commit, changed, testBuildDue}``. A game already installed from the same
    source is updated instead (``update``'s answer). Raises ``InstallError`` and changes nothing when it cannot."""
    source = _settled(source, allow_local)
    if not install_git.is_commit(commit):
        raise InstallError("BAD_COMMIT", "Install the exact commit inspect read (40 hex digits).")
    registry = _registry(registry)
    games = Path(games_dir) if games_dir else paths.games_dir(create=True)
    games.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".install-", dir=games))
    try:
        game, head, report = _prepare(source, staging, commit)
        _consent(report, allow_plugins)
        identifier = report["card"]["id"]
        with install_swap.id_lock(games, identifier):
            holders = _holders(registry, identifier, source) or _recover_orphan(registry, games, identifier, source)
            if not holders:
                _finish(game, source, head, report)
                with install_swap.games_lock(games):
                    root = _guard_swap(lambda: install_swap.unique_folder(games, report["card"]["title"]))
                    os.rename(game, root)
                registry.upsert(str(root))  # a failure here leaves a folder the next install recovers
                return _done(root, report["mode"], head, changed=True)
            same = [holder for holder in holders if holder["sameSource"]]
            if not same:
                raise InstallError(
                    "ALREADY_HAVE",
                    "You already have this game from another source. Remix it to keep both.",
                    alreadyInstalled=holders,
                )
            return update(
                same[0]["root"],
                source=source,
                commit=commit,
                workers=workers,
                registry=registry,
                allow_plugins=allow_plugins,
                allow_local=allow_local,
            )
    finally:
        _clean(staging)


def check_update(root: Path, *, allow_local: bool = False) -> dict:
    """``{available, commit, remoteCommit}``: whether the installed game's branch is at another commit now. Reads
    the remote (``git ls-remote``, outside any checkout) and changes nothing."""
    record = _record(Path(root))
    source = _guard(lambda: resolve(record["source"], allow_local=allow_local))
    remote = _guard(lambda: install_git.remote_commit(source))
    return {"available": remote != record.get("commit"), "commit": record.get("commit"), "remoteCommit": remote}


def update(
    root: Path,
    *,
    workers,
    choice: str | None = None,
    commit: str | None = None,
    source=None,
    registry: Registry | None = None,
    allow_plugins: bool = False,
    allow_local: bool = False,
) -> dict:
    """Install the newest commit of the game's recorded source (or ``source``, the one the user reviewed, and exactly
    ``commit``) over the installed game. ``{ok, root, mode, commit, changed, testBuildDue, kept?, remix?}``, or
    ``{needsChoice: True}`` with nothing changed while the user edited the game since it was installed."""
    root = Path(root)
    if choice is not None and choice not in CHOICES:
        raise InstallError("BAD_CHOICE", f"Choose one of {', '.join(CHOICES)}.")
    if commit is not None and not install_git.is_commit(commit):
        raise InstallError("BAD_COMMIT", "Update to an exact commit (40 hex digits).")
    _record(root)  # before the locks, which would make the record folder of a folder that is no game
    registry = _registry(registry)
    games = root.parent
    with install_swap.id_lock(games, layout.game_identity(root) or "unknown"), game_card.folder_lock(root):
        record = _record(root)  # as it is now: another update may have run while this one waited
        source = _settled(source if source is not None else record["source"], allow_local)
        edited = release.local_edits(root) is True
        if edited and choice is None:
            return {"ok": False, "needsChoice": True, "root": str(root), "choices": list(CHOICES)}
        if edited and choice == "keep_mine":
            return _done(root, record["mode"], record.get("commit"), changed=False)
        _hold(workers, root)
        staging = Path(tempfile.mkdtemp(prefix=".install-", dir=games))
        try:
            game, head, report = _prepare(source, staging, commit)
            if head == record.get("commit") and not edited and source.record() == record["source"]:
                return _done(root, record["mode"], head, changed=False)
            _consent(report, allow_plugins)
            if report["card"]["id"] != layout.game_identity(root):
                raise InstallError(
                    "ANOTHER_GAME", "The source now holds a different game; it was not installed over this one."
                )
            _finish(game, source, head, report)
            if not edited and release.local_edits(root) is True:  # edited while the update was fetched
                return {"ok": False, "needsChoice": True, "root": str(root), "choices": list(CHOICES)}
            try:
                if edited and choice == "keep_both":
                    title = f"{report['card']['title']} (edited)"
                    swapped = install_swap.keep_both(
                        root,
                        game,
                        lambda: install_swap.unique_folder(games, title),
                        lambda: install_swap.games_lock(games),
                        registry,
                    )
                else:
                    swapped = install_swap.replace(
                        root, game, staging, lambda: install_swap.games_lock(games), registry
                    )
            except install_swap.SwapError as error:
                raise InstallError(error.code, error.message, **error.details) from error
        finally:
            _release(workers, root)
            _clean(staging)
    return {**_done(root, report["mode"], head, changed=True), **swapped}


# -- the steps -------------------------------------------------------------------------------------


def _settled(link, allow_local: bool) -> Source:
    source = _guard(lambda: resolve(link, allow_local=allow_local))
    return _guard(lambda: install_git.settle(source))


def _guard(step):
    try:
        return step()
    except SourceError as error:
        raise InstallError(error.code, error.message) from error


def _prepare(source: Source, workspace: Path, commit: str | None = None) -> tuple[Path, str, dict]:
    """Fetch ``source`` into ``workspace``, check its tree, check out the game and take its payload into
    ``workspace/game``: ``(game, commit, check report)``. A ``commit`` the branch is no longer at is refused
    (``SOURCE_MOVED``): what installs is what was reviewed. An unsafe tree stops everything before checkout."""
    checkout = workspace / "clone"
    head = _guard(lambda: install_git.fetch(source, checkout))
    if commit is not None and head != commit:
        raise InstallError("SOURCE_MOVED", "The game changed since it was read; read it again.", commit=head)
    entries = _guard(lambda: install_git.tree(checkout, source.subdir))
    if not entries:
        raise InstallError(
            "BAD_FOLDER",
            f"The repository has no folder {source.subdir!r}." if source.subdir else "The repository is empty.",
        )
    unsafe = install_git.tree_problems(
        entries, max_files=install_check.MAX_FILES, max_total=install_check.MAX_TOTAL_BYTES
    )
    if unsafe:
        raise InstallError("NOT_INSTALLABLE", "This game cannot be installed.", problems=unsafe, commit=head)
    _guard(lambda: install_git.checkout(checkout, source.subdir))
    folder = _guard(lambda: within(checkout, source.subdir))
    game = workspace / "game"
    mode, problems = install_check.take_payload(folder, game)
    report = install_check.check(game) if not problems else {"problems": problems}
    if problems or not report["ok"]:
        raise InstallError(
            "NOT_INSTALLABLE", "This game cannot be installed.", problems=report["problems"], commit=head
        )
    return game, head, report


def _consent(report: dict, allow_plugins: bool) -> None:
    if report["needsPluginConsent"] and not allow_plugins:
        raise InstallError(
            "PLUGINS",
            "This game's source has GB Studio plugins: code that runs on this computer when the game is built.",
            needsPluginConsent=True,
        )


def _finish(game: Path, source: Source, commit: str, report: dict) -> None:
    """The fetched game as an installed game, still in staging: its layout and its install record."""
    layout.ensure(game)
    rom = {"path": report["rom"]["path"], "sha256": report["rom"]["sha256"]}
    release.record_install(game, source=source.record(), commit=commit, mode=report["mode"], rom=rom)


def _guard_swap(step):
    try:
        return step()
    except install_swap.SwapError as error:
        raise InstallError(error.code, error.message, **error.details) from error


def _hold(workers, root: Path) -> None:
    try:
        workers.hold(root)
    except Exception as error:
        code = getattr(error, "code", "GAME_BUSY")
        raise InstallError(code, getattr(error, "message", str(error))) from error


def _release(workers, root: Path) -> None:
    """Let the broker open the game again; a broker that cannot be reached lets the hold end on its own."""
    try:
        workers.release(root)
    except Exception:  # noqa: BLE001 - the update's own outcome is what the caller needs
        pass


def _clean(staging: Path) -> None:
    """Remove what an install left in its staging folder; an old copy of a game kept there is never removed."""
    for name in ("clone", "game"):
        shutil.rmtree(staging / name, ignore_errors=True)
    try:
        staging.rmdir()
    except OSError:
        pass


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


def _holders(registry: Registry, identifier: str, source: Source) -> list[dict]:
    """The library's games with this game id: ``{root, title, sameSource}``. The same source is the same repository
    and folder in it (``Source.canonical``); the branch may differ."""
    found = []
    for entry in registry.load()["games"].values():
        stored = entry.get("projectRoot") if isinstance(entry, dict) else None
        if isinstance(stored, str) and os.path.isdir(stored) and _same_game(Path(stored), identifier):
            found.append(_holder(Path(stored), source))
    return found


def _recover_orphan(registry: Registry, games: Path, identifier: str, source: Source) -> list[dict]:
    """A game folder an earlier install moved into place but did not register (it stopped in between): registered
    now, and answered as the holder, so the install becomes its update instead of a second copy."""
    for name in sorted(os.listdir(games)):
        folder = games / name
        if name.startswith(".") or not folder.is_dir() or folder.is_symlink() or not _same_game(folder, identifier):
            continue
        if release.installed(folder) is not None:
            registry.upsert(str(folder))
            return [_holder(folder, source)]
    return []


def _same_game(root: Path, identifier: str) -> bool:
    return identifier in (layout.game_identity(root), game_card.load(root).get("id"))


def _holder(root: Path, source: Source) -> dict:
    record = release.installed(root)
    same = record is not None and record["source"].get("canonical") == source.canonical
    return {"root": str(root), "title": game_card.load(root).get("title"), "sameSource": same}


def _cover_url(game: Path) -> str | None:
    cover = game / game_card.COVER_FILE
    if not install_check._regular(cover) or cover.stat().st_size > game_card.MAX_COVER_BYTES:
        return None
    with cover.open("rb") as handle:
        return "data:image/png;base64," + base64.b64encode(handle.read(game_card.MAX_COVER_BYTES)).decode()


def _readme(game: Path) -> str | None:
    readme = game / "README.md"
    if not install_check._regular(readme):
        return None
    with readme.open(encoding="utf-8", errors="replace") as handle:
        return handle.read(MAX_README_CHARS)
