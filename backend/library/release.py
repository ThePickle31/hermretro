"""What a publish of a game holds and what it records, for publishing it (the game alone, or with its source),
updating it and installing it elsewhere. Standard library only; nothing here reaches the network.

A publish goes: ``readiness`` (may it be published?), ``prepare_release`` (the version, the changelog entry and the
README, before the files are committed), ``files`` (exactly what to commit), then after a successful push
``record_publish``. ``unpublished_changes`` compares the folder with what was published. An install records where
it came from with ``record_install``; a remix is ``layout.new_identity`` on the copy.

Records, in ``.hermretro/`` (never published):
    publish.json  {repo, commit, version, source, payload, t}  the last publish; ``payload`` is ``payload_digest``
    install.json  {repo, commit, source, t}                    where an installed game came from
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from . import game_card, layout
from .freshness import sources_newer_than
from .layout import INSTALL_FILE, PUBLISH_FILE
from .project import GAME_FILES, file_sha256, project_file

VERSION_PARTS = ("major", "minor", "patch")


# -- what a publish holds -----------------------------------------------------------------


def files(root: Path, *, source: bool) -> list[str]:
    """Every file a publish holds, relative and sorted: the game files that exist and the game's ROM, and with
    ``source`` the ``.gbsproj`` and every file under the source folders. Symbolic links, hidden files and anything
    reached through a linked folder are never included."""
    root = Path(root)
    found = [name for name in GAME_FILES if _regular(root / name)]
    rom = layout.game_rom(root)
    if _regular(root / rom) and not (root / "build").is_symlink():
        found.append(rom)
    if source:
        descriptor = project_file(root)
        if descriptor is not None and _regular(descriptor):
            found.append(descriptor.name)
        for folder in layout.SOURCE_FOLDERS:
            if (root / folder).is_symlink():
                continue
            for directory, folders, names in os.walk(root / folder):
                folders[:] = sorted(name for name in folders if not name.startswith("."))
                for name in names:
                    path = Path(directory, name)
                    if not name.startswith(".") and _regular(path):
                        found.append(path.relative_to(root).as_posix())
    return sorted(found)


def _regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def payload_digest(root: Path, *, source: bool) -> str:
    """A digest of exactly what a publish holds: every file of ``files`` by path and content."""
    digest = hashlib.sha256(b"hermretro\0publish\0v1\0")
    for relative in files(root, source=source):
        digest.update(relative.encode() + b"\0" + file_sha256(Path(root) / relative).encode() + b"\0")
    return digest.hexdigest()


def readiness(root: Path, *, source: bool) -> dict:
    """``{ok, problems}``: whether the game may be published as it stands. Its layout has no problem, its card is
    complete, its ROM exists and was built after every source change, and a publish with the source has the
    project. Each problem is ``{code, path, message}``."""
    root = Path(root)
    problems = list(layout.check(root)["problems"])
    card = game_card.status(root, strict=True)
    if not card["complete"]:
        problems.append(_finding("CARD", game_card.CARD_FILE, "The game card is missing " + ", ".join(card["missing"])))
    rom = root / layout.game_rom(root)
    if not _regular(rom):
        problems.append(_finding("NO_ROM", layout.game_rom(root), "The game has not been built."))
    elif project_file(root) is not None and sources_newer_than(root, rom.stat().st_mtime):
        problems.append(_finding("ROM_OLD", layout.game_rom(root), "The game changed after its last build."))
    if source and project_file(root) is None:
        problems.append(_finding("NO_SOURCE", "", "The game has no source to publish."))
    return {"ok": not problems, "problems": problems}


def _finding(code: str, path: str, message: str) -> dict:
    return {"code": code, "path": path, "message": message}


# -- versions and the changelog -----------------------------------------------------------


def next_version(version: str, part: str = "patch") -> str:
    """The version after ``version`` (``layout.FIRST_VERSION`` when it is not one); ``part`` is ``major``,
    ``minor`` or ``patch``."""
    if part not in VERSION_PARTS:
        raise ValueError(f"Not a version part: {part!r}.")
    match = layout.VERSION_PATTERN.match(version or "")
    if not match:
        return layout.FIRST_VERSION
    major, minor, patch = (int(number) for number in match.groups())
    return {"major": f"{major + 1}.0.0", "minor": f"{major}.{minor + 1}.0", "patch": f"{major}.{minor}.{patch + 1}"}[
        part
    ]


@game_card.locked
def prepare_release(root: Path, version: str, notes: str = "") -> None:
    """Make the folder say ``version`` before it is committed: the card's ``gameVersion``, a ``CHANGELOG.md``
    entry (once, however often it is called) and the README."""
    root = Path(root)
    if not layout.VERSION_PATTERN.match(version):
        raise ValueError(f"Not a version: {version!r}.")
    if game_card.load(root):
        game_card.set_fields(root, {"gameVersion": version})
    try:
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        changelog = layout.CHANGELOG_HEAD
    if f"\n## {version} (" not in changelog:
        head, _, rest = changelog.partition("\n")
        entry = f"\n## {version} ({time.strftime('%Y-%m-%d')})\n" + (f"\n{notes.strip()}\n" if notes.strip() else "")
        layout.write_text(root / "CHANGELOG.md", head + "\n" + entry + rest)
    layout.ensure(root)


# -- what was published and installed ------------------------------------------------------


@game_card.locked
def record_publish(root: Path, *, repo: str, commit: str, version: str, source: bool) -> dict:
    """Record a successful publish (after the push): where, which commit, which version, with or without the
    source, and the digest of what it held. Returns the record."""
    if not layout.VERSION_PATTERN.match(version):
        raise ValueError(f"Not a version: {version!r}.")
    record = {
        "repo": repo,
        "commit": commit,
        "version": version,
        "source": bool(source),
        "payload": payload_digest(root, source=bool(source)),
        "t": time.time(),
    }
    layout.write_state(root, PUBLISH_FILE, record)
    return record


def published(root: Path) -> dict | None:
    """The last publish (``record_publish``), or None when the game was never published."""
    return layout.state(root, PUBLISH_FILE) or None


def unpublished_changes(root: Path) -> bool | None:
    """Whether anything the last publish held changed since: the same files, with or without the source as it
    was. None when the game was never published."""
    record = published(root)
    if record is None:
        return None
    return payload_digest(root, source=record.get("source") is True) != record.get("payload")


@game_card.locked
def record_install(root: Path, *, repo: str, commit: str, source: bool) -> dict:
    """Record where an installed game came from; ``installed`` reads it (an update compares ``commit``)."""
    record = {"repo": repo, "commit": commit, "source": bool(source), "t": time.time()}
    layout.write_state(root, INSTALL_FILE, record)
    return record


def installed(root: Path) -> dict | None:
    """Where an installed game came from (``record_install``), or None for a game made here."""
    return layout.state(root, INSTALL_FILE) or None
