"""Whether a game's playable web copy is the current game: the engine's own export, playing the game's ROM, made
from the sources as they stand. Standard library only."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .project import (
    GAME_FILES,
    NOT_SOURCE,
    _game_rom,
    _legacy_rom,
    _json,
    file_sha256,
    has_web_export,
    project_file,
    project_settings,
    timestamp,
    web_dir,
    web_rom,
)

# How many source files sources_newer_than looks at before it stops and calls the ROM current. Its own bound, not the
# snapshot cap (backend/history/snapshots.py MAX_FILES, which skips the copy): the two only happen to share a number.
MAX_SOURCE_FILES = 20000
# File times of a build and the web export made right after it can differ by a little.
FRESH_SLACK_SECONDS = 2.0
# The record the engine writes into each web export it makes (engine/modretro-chromatic/dist/web-build.js).
WEB_MANIFEST = ".codex-web-build.json"


def web_export_time(root: Path) -> float | None:
    """When the playable web copy was written: its ROM's file time (else its ``index.html``)."""
    if not has_web_export(root):
        return None
    target = web_rom(root) or (web_dir(root) / "index.html")
    try:
        return target.stat().st_mtime
    except OSError:
        return None


def engine_made_export(root: Path) -> bool:
    """Whether ``build/web`` is the engine's own export, unchanged: its ``.codex-web-build.json`` lists the
    ROM and ``index.html`` it wrote, with their hashes, and both files still match. A copy assembled or edited
    by hand has no such record, or one whose hashes no longer match."""
    web = web_dir(root)
    manifest = _json(web / WEB_MANIFEST)
    files = manifest.get("files")
    rom = web_rom(root)
    if not isinstance(files, list) or rom is None or manifest.get("indexPath") != "index.html":
        return False
    if manifest.get("romPath") != rom.relative_to(web).as_posix():
        return False
    hashes = {
        item["path"]: item.get("sha256")
        for item in files
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    for relative in ("index.html", manifest["romPath"]):
        try:
            # The bytes as they are now, never a cached digest: a swapped file can keep its size and time.
            current = hashlib.sha256((web / relative).read_bytes()).hexdigest()
        except OSError:
            return False
        if current != hashes.get(relative):
            return False
    return True


def _plays_rom(root: Path, rom: Path) -> bool:
    """Whether the web export's ROM is byte for byte ``rom``: the engine writes the ROM the last build made into
    every export of the same sources (``engine/CHANGES.md``). A project with batteryless saves on always counts:
    GB Studio compiles its web copy without them, so the bytes differ on purpose."""
    if project_settings(root).get("batterylessEnabled") is True:
        return True
    played = web_rom(root)
    try:
        return played is not None and file_sha256(played) == file_sha256(rom)
    except OSError:
        return False


def plays_game_rom(root: Path) -> bool:
    """Whether the playable copy plays the game's ROM byte for byte (true before the game has its own ROM, and for
    a batteryless project)."""
    game = _game_rom(Path(root))
    return game is None or _plays_rom(Path(root), game[0])


# What a GB Studio web export is made from (the engine's own source fingerprint covers the same).
EXPORT_SOURCES = ("project", "assets", "plugins")


def source_digest(root: Path) -> str | None:
    """A digest of what the playable copy is made from: the ``.gbsproj`` and every file under ``project/``,
    ``assets/`` and ``plugins/``, by path and content. A deleted or renamed file changes it too; the card, the
    plans and the README do not. None for a project that is not GB Studio's, or past ``MAX_SOURCE_FILES``."""
    descriptor = project_file(root)
    if descriptor is None:
        return None
    digest = hashlib.sha256(b"hermretro\0export-sources\0v1\0")
    seen = 0
    files = [descriptor]
    for folder in EXPORT_SOURCES:
        for directory, folders, names in os.walk(root / folder):
            folders.sort()
            files += [Path(directory, name) for name in sorted(names)]
    for path in files:
        seen += 1
        if seen > MAX_SOURCE_FILES:
            return None
        try:
            if path.is_symlink() or not path.is_file():
                continue
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + file_sha256(path).encode() + b"\0")
        except OSError:
            continue
    return digest.hexdigest()


# What to do about a stale playable copy, by why it is stale.
_REBUILD = (
    "Run chromatic_rom_build for this project (with the 'Keep the playable copy current' setting on it also "
    "makes the playable copy; with it off, call chromatic_web_preview after it), then call "
    "chromatic_present_game again."
)
_MISMATCH = (
    "Run chromatic_rom_build for this project (with the 'Keep the playable copy current' setting off, call "
    "chromatic_web_preview after it), then call chromatic_present_game again. If it still says the copy plays "
    "another build, tell the user the playable copy could not be made from this build; do not build again."
)
_REMAKE = (
    "Call chromatic_web_preview to make the playable copy from the current build, then call chromatic_present_game "
    "again. If chromatic_web_preview fails, tell the user what it said instead of building again."
)


def export_freshness(
    root: Path, last_build: dict | None = None, last_web_export: dict | None = None
) -> tuple[bool, str | None, str | None]:
    """Whether the web copy shows the latest build: ``(fresh, why, next step)``. Fresh means it exists, the engine
    made it (``engine_made_export``), it is not older than the last ROM build, and no game source changed after it.
    When the library recorded the build, its time counts (the native ROM file otherwise), and the copy's time is
    the later of its files and the last successful web export the broker recorded (the engine reuses an unchanged
    export without rewriting it). A failed build after the copy also counts as stale: the user would be shown an
    older game than the one being worked on."""
    last = last_build if isinstance(last_build, dict) else None
    recorded = timestamp(last.get("t")) if last else 0.0
    game_rom = _game_rom(root)
    newest = game_rom or _legacy_rom(root)  # a game last built before it had its own ROM
    rom_time = newest[1] if newest else None
    # When hermretro's own successful build is the newest ROM, only its playable copy is missing: building the
    # same thing again would loop, so the copy is made from it. A newer ROM nobody recorded needs a real build.
    remake = bool(last and last.get("ok")) and recorded + FRESH_SLACK_SECONDS >= (rom_time or 0.0)
    recover = _REMAKE if remake else _REBUILD
    exported = web_export_time(root)
    if exported is None:
        return False, "This game has no playable web copy yet.", recover
    if not engine_made_export(root):
        return (
            False,
            "The playable copy in build/web was not made by hermretro's build, or was changed after it, so it may "
            "not be this game as its sources stand.",
            "Never make, copy or edit files in build/ yourself. " + recover,
        )
    if game_rom is not None and not _plays_rom(root, game_rom[0]):  # never true of a batteryless project
        return (
            False,
            f"The playable copy does not play this game's ROM ({game_rom[0].relative_to(root).as_posix()}), so it is "
            "another build.",
            _MISMATCH,
        )
    if isinstance(last_web_export, dict):
        exported = max(exported, timestamp(last_web_export.get("t")))
    built = None if last else rom_time  # a recorded build's time counts, else the newest ROM file's
    if last and last.get("ok") is False and recorded > exported + FRESH_SLACK_SECONDS:
        return (
            False,
            "The last chromatic_rom_build of this game failed, so the playable copy is an older build.",
            "Fix what the build reported first. " + _REBUILD,
        )
    latest = max([moment for moment in (built, recorded if last and last.get("ok") else None) if moment] or [0.0])
    if latest > exported + FRESH_SLACK_SECONDS:
        return False, "The playable web copy is older than the last ROM build.", recover
    recorded_sources = last_web_export.get("sources") if isinstance(last_web_export, dict) else None
    if isinstance(recorded_sources, str):
        changed = source_digest(root) != recorded_sources
    else:  # an export recorded before the library kept its sources' digest
        changed = sources_newer_than(root, exported)
    if changed:
        return False, "Game files changed after the playable copy was made, so it is not the current game.", _REBUILD
    return True, None, None


def sources_newer_than(root: Path, moment: float) -> bool:
    """Whether any game source file under the project changed after ``moment`` (a ROM's mtime)."""
    seen = 0
    top = os.fspath(root)
    for directory, folders, files in os.walk(root):
        folders[:] = [f for f in folders if not f.startswith(".") and f not in NOT_SOURCE]
        for name in files:
            # The game card, README, changelog and licence describe the game; they are not game source.
            if name.startswith(".") or (directory == top and name in GAME_FILES):
                continue
            seen += 1
            if seen > MAX_SOURCE_FILES:
                return False
            try:
                if os.stat(os.path.join(directory, name)).st_mtime > moment + 1.0:
                    return True
            except OSError:
                continue
    return False
