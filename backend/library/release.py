"""What a publish of a game holds and what it records, for publishing it (the game alone, or with its source),
updating it and installing it elsewhere. Standard library only; nothing here reaches the network.

A publish goes: ``publish_ready.readiness`` (may it be published?), ``prepare_release`` (the version, the changelog entry and the
README, before the files are committed), ``files`` (exactly what to commit), then after a successful push
``record_publish``. ``unpublished_changes`` compares the folder with what was published. An install records where
it came from with ``record_install``; a remix is ``layout.new_identity`` on the copy.

Records, in ``.hermretro/`` (never published):
    publish.json  {repo, commit, version, source, payload, t}  the last publish; ``payload`` is ``payload_digest``
    install.json  {source: {canonical, url, ref, subdir}, commit, mode, rom: {path, sha256}, fingerprint, installedAt,
                  sourceDigest?, buildConsent?, testBuild?}  where an installed game came from (installs.py); a game
                  with its source also has the digest of the source as installed and, once the user allowed it and
                  it was built here, ``install_build``'s records
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import time
from pathlib import Path

from . import game_card, layout, licence
from .freshness import source_digest
from .layout import INSTALL_FILE, PUBLISH_FILE
from .project import GAME_FILES, file_sha256, project_file

VERSION_PARTS = ("major", "minor", "patch")
# What GB Studio leaves beside a file it saves (``writeFileWithBackup``: the old copy and the one being written).
SAVE_LEFTOVERS = (".bak", ".new")
# installed_digest's version; an install record names it (one made before names none: version 2).
FINGERPRINT_VERSION = 3
INSTALL_MODES = ("game", "game+source")


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
                    if not name.startswith(".") and not name.endswith(SAVE_LEFTOVERS) and _regular(path):
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
def record_install(root: Path, *, source: dict, commit: str, mode: str, rom: dict) -> dict:
    """Record where an installed game came from (``installs.py``): ``source`` is ``Source.record()`` (``{canonical,
    url, ref, subdir}``, no credentials), ``commit`` the commit installed, ``mode`` ``game`` or ``game+source``,
    ``rom`` the ROM that was checked (``{path, sha256}``, ``path`` relative to the game) and ``fingerprint`` the
    ``installed_digest`` of the files as installed (``fingerprintVersion``), which tells an untouched install from one
    edited since."""
    if mode not in INSTALL_MODES:
        raise ValueError(f"Not an install mode: {mode!r}.")
    record = {
        "source": dict(source),
        "commit": commit,
        "mode": mode,
        "rom": {"path": rom["path"], "sha256": rom["sha256"]},
        "fingerprint": installed_digest(root, mode=mode),
        "fingerprintVersion": FINGERPRINT_VERSION,
        "installedAt": time.time(),
    }
    if mode == "game+source":  # what a build of it reads, as its author published it (install_build)
        record["sourceDigest"] = source_digest(root)
    layout.write_state(root, INSTALL_FILE, record)
    return record


def installed(root: Path) -> dict | None:
    """Where an installed game came from (``record_install``), or None for a game made here."""
    record = layout.state(root, INSTALL_FILE)
    if not isinstance(record.get("source"), dict) or record.get("mode") not in INSTALL_MODES:
        return None
    return record


def installed_digest(
    root: Path, *, mode: str, version: int = FINGERPRINT_VERSION, card_sha256: str | None = None
) -> str:
    """What a user's edit of an installed game changes: its game files (but the README, ``.gitignore`` and
    ``LICENSE`` hermretro writes itself, which a newer hermretro may rewrite, and the fields of ``game.json`` it
    records as it lays out and builds the game), every file of its project and source folders, hidden ones
    too, and for a game alone its ROM. A game with its source rebuilds its ROM from that source, so the ROM and every
    other build output are left out: a build never counts as an edit. A game alone that gains a project counts.
    ``version`` 2 is the digest install records made before hermretro wrote ``LICENSE`` and those fields: the whole
    ``game.json`` (``card_sha256`` in its place when given) and any ``LICENSE``."""
    root = Path(root)
    found = [name for name in GAME_FILES if _regular(root / name)]
    found = [name for name in found if not (name in ("README.md", ".gitignore") and layout.replaceable(root / name))]
    if version >= 3 and licence.LICENSE_FILE in found and layout.licence_owned(root, root / licence.LICENSE_FILE):
        found.remove(licence.LICENSE_FILE)  # the LICENSE hermretro wrote from the card
    if mode == "game":
        rom = installed_rom_path(root) or layout.game_rom(root)
        found += [rom] if _regular(root / rom) else []
    found += [path.name for path in root.glob("*.gbsproj") if _regular(path)]
    for folder in layout.SOURCE_FOLDERS:
        if (root / folder).is_symlink():
            continue
        for directory, folders, names in os.walk(root / folder):
            folders.sort()
            found += [
                Path(directory, name).relative_to(root).as_posix() for name in names if _regular(Path(directory, name))
            ]
    digest = hashlib.sha256(f"hermretro\0installed\0v{version}\0".encode())
    for relative in sorted(found):
        managed = version >= 3 and relative == game_card.CARD_FILE
        if managed:
            content = _card_digest(root)
        elif relative == game_card.CARD_FILE and card_sha256 is not None:
            content = card_sha256
        else:
            content = file_sha256(root / relative)
        digest.update(relative.encode() + b"\0" + content.encode() + b"\0")
    return digest.hexdigest()


def _card_digest(root: Path) -> str:
    """``game.json`` as the user wrote it: the fields hermretro itself writes as it lays out and builds the game
    (``layout.MANAGED_FIELDS``) are left out, so a build is never an edit."""
    card = game_card.load(root)
    if not card:
        return file_sha256(Path(root) / game_card.CARD_FILE)
    kept = {key: value for key, value in card.items() if key not in layout.MANAGED_FIELDS}
    return hashlib.sha256(json.dumps(kept, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def local_edits(root: Path) -> bool | None:
    """Whether an installed game's files changed since it was installed; None for a game that was not installed."""
    record = installed(root)
    if record is None:
        return None
    version = record.get("fingerprintVersion", 2)
    if version == FINGERPRINT_VERSION:
        return installed_digest(root, mode=record["mode"]) != record.get("fingerprint")
    if version != 2 or not _matches_v2(root, record):
        return True
    _upgrade_fingerprint(root, record)  # an untouched install recorded by an older hermretro
    return False


def _matches_v2(root: Path, record: dict) -> bool:
    """Whether an install recorded by an older hermretro is untouched: its version 2 digest, of ``game.json`` as it is
    or as it was before this hermretro added the fields it now writes (``layout.MANAGED_FIELDS``, written by
    ``game_card``, so dropping them gives back the bytes it wrote)."""
    card = game_card.load(root)
    added = [key for key in layout.MANAGED_FIELDS if key in card]
    candidates = [None]
    for size in range(1, len(added) + 1):
        for dropped in itertools.combinations(added, size):
            kept = {key: value for key, value in card.items() if key not in dropped}
            candidates.append(hashlib.sha256(game_card.card_text(kept).encode()).hexdigest())
    return any(
        installed_digest(root, mode=record["mode"], version=2, card_sha256=sha) == record.get("fingerprint")
        for sha in candidates
    )


@game_card.locked
def _upgrade_fingerprint(root: Path, record: dict) -> None:
    upgraded = {
        **record,
        "fingerprint": installed_digest(root, mode=record["mode"]),
        "fingerprintVersion": FINGERPRINT_VERSION,
    }
    layout.write_state(root, INSTALL_FILE, upgraded)


def installed_rom_path(root: Path) -> str | None:
    """The ROM an install checked, relative to the game (``build/game.gb[c]``); None for a game made here."""
    rom = layout.state(root, INSTALL_FILE).get("rom")
    path = rom.get("path") if isinstance(rom, dict) else None
    return path if path in layout.GAME_ROMS else None


def installed_rom(root: Path) -> dict | None:
    """For a game installed without its source, the ROM it plays: ``{romPath, sha256, source, commit}`` (``romPath``
    absolute, ``sha256`` the one checked against its author's ``romSha256``) while that file is still those bytes;
    None for a game made here, one with its source (it plays what it builds) or a ROM changed since."""
    record = installed(root)
    if record is None or record["mode"] != "game":
        return None
    relative, sha256 = installed_rom_path(root), (record.get("rom") or {}).get("sha256")
    path = Path(root) / relative if relative else None
    if path is None or not _regular(path) or file_sha256(path) != sha256:
        return None
    return {
        "romPath": str(path),
        "sha256": sha256,
        "source": record["source"].get("canonical"),
        "commit": record.get("commit"),
    }
