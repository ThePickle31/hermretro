"""Project snapshots for the Build page's build history (Restore per build).

After each successful ``chromatic_rom_build`` of a library game, the project's own files are copied to
``<base>/<game id>/<ms>/files/`` with ``<ms>/snapshot.json`` beside them. A build that changed nothing
adds its build reference to the newest snapshot instead of making a new copy. Restoring first keeps the
current files as a ``before-restore`` snapshot, then makes the project's files match the chosen one.

Pure functions over paths: no Hermes, broker or registry imports, so everything here is unit-testable.
Generated and personal folders are never copied, compared, deleted or restored (``EXCLUDED_TOP``), nor is a
folder inside the project that holds a ``.gbsproj`` of its own (another game's project: restoring this game must
never change that one), and symbolic links are skipped everywhere (never followed, copied or removed).
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import time
from contextlib import contextmanager
from itertools import islice
from pathlib import Path

from .build_refs import build_history, public_snapshot, record_build
from .restore_files import (
    PROJECT_SUFFIX,
    Digest,
    DirectoryId,
    LiveTree,
    _restore_files,
    directory_id,
    file_digest,
    file_stamp,
)

# Top-level folders that are build output, tool state or the user's own captures, never game source.
# captures/ and save-states/ are kept out too: restoring an older build must not delete screenshots,
# recordings or saved states the user made since.
EXCLUDED_TOP = frozenset({"build", "artifacts", ".git", "node_modules", "captures", "save-states"})
TEMP_SUFFIXES = (".part", ".tmp", ".swp", "~", ".hr-restore")
MAX_BYTES = 64 * 1024 * 1024
MAX_FILES = 20000
KEEP = 30
STALE_PART_SECONDS = 600
META = "snapshot.json"
FILES = "files"
REASONS = ("build", "before-restore")


class SnapshotError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _temporary(name: str) -> bool:
    return name.endswith(TEMP_SUFFIXES) or name.startswith(".~")


def walk(root: Path, *, stored: bool = False, live: LiveTree | None = None) -> dict[str, Path]:
    """Scan the whole tree up to the file cap, propagating I/O errors. A live project has exclusions, while stored
    files must all be accounted for by the snapshot manifest."""
    found: dict[str, Path] = {}
    stack = [(Path(root), "")]
    while stack:
        folder, prefix = stack.pop()
        identity = directory_id(folder.lstat()) if live is not None else None
        with os.scandir(folder) as scan:
            entries = [(entry, entry.stat(follow_symlinks=False).st_mode) for entry in scan]
        if (
            not stored
            and prefix
            and any(
                entry.name.lower().endswith(PROJECT_SUFFIX) and (stat.S_ISREG(mode) or stat.S_ISLNK(mode))
                for entry, mode in entries
            )
        ):
            if live is not None:
                live.other_games.add(identity)
            continue
        if live is not None:
            live.directories[prefix.rstrip("/")] = identity
        for entry, mode in entries:
            relative = f"{prefix}{entry.name}"
            if stat.S_ISDIR(mode):
                if stored or prefix or entry.name not in EXCLUDED_TOP:
                    stack.append((Path(entry.path), relative + "/"))
                elif live is not None:
                    live.excluded.add(directory_id(entry.stat(follow_symlinks=False)))
            elif stat.S_ISREG(mode):
                if stored or not _temporary(entry.name):
                    found[relative] = Path(entry.path)
            elif stored:
                raise OSError(f"Unexpected entry in the snapshot: {relative}")
            if len(found) > MAX_FILES:
                return found
    return found


def _fingerprint(digests: dict[str, tuple[int, str]]) -> str:
    """One hash over every file's relative path, size and SHA-256, in path order."""
    digest = hashlib.sha256()
    for relative in sorted(digests):
        size, sha = digests[relative]
        digest.update(f"{relative}\0{size}\0{sha}\n".encode("utf-8", "surrogateescape"))
    return digest.hexdigest()


def game_dir(base: Path, game: str) -> Path:
    return Path(base) / game


def _write_json(path: Path, value: dict) -> None:
    partial = path.with_name(path.name + ".part")
    partial.write_text(json.dumps(value, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(partial, path)


def _read_meta(folder: Path) -> dict | None:
    try:
        value = json.loads((folder / META).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


@contextmanager
def _locked(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / ".lock", "a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _ids(folder: Path) -> list[str]:
    """Finished snapshot ids of one game, newest first."""
    try:
        with os.scandir(folder) as entries:
            names = [
                entry.name for entry in entries if _snapshot_id(entry.name) and entry.is_dir(follow_symlinks=False)
            ]
    except FileNotFoundError:
        return []
    return sorted(names, key=int, reverse=True)


def _snapshot_id(value: str) -> bool:
    return value.isascii() and value.isdigit()


def list_snapshots(base: Path, game: str, *, stored: str | None = None) -> list[dict]:
    """Every snapshot of one game, newest first (without fingerprints)."""
    folder = game_dir(base, game)
    listed = []
    for identifier in _ids(folder):
        meta = _read_meta(folder / identifier)
        if meta is not None:
            listed.append(public_snapshot(meta, identifier, stored))
    return listed


def _prune(folder: Path, keep: int, protect=()) -> None:
    now = time.time()
    try:
        for identifier in _ids(folder)[keep:]:
            if identifier not in protect:
                shutil.rmtree(folder / identifier, ignore_errors=True)
        with os.scandir(folder) as entries:
            for entry in entries:
                if (
                    entry.name.endswith(".part")
                    and entry.is_dir(follow_symlinks=False)
                    and now - entry.stat(follow_symlinks=False).st_mtime > STALE_PART_SECONDS
                ):
                    shutil.rmtree(entry.path, ignore_errors=True)
    except OSError:
        pass


def _measure(files: dict[str, Path], live: LiveTree | None = None) -> tuple[int, dict[str, tuple[int, str]]]:
    digests = {}
    total = 0
    for relative, path in files.items():
        info = path.lstat()
        size = info.st_size
        total += size
        if total > MAX_BYTES:
            return total, {}
        stamp = file_stamp(info)
        measured = file_digest(path, size, expected_stamp=stamp)
        if measured[0] != size:
            raise OSError(f"{path} changed during the snapshot operation")
        digests[relative] = measured
        if live is not None:
            live.files[relative] = (stamp, measured)
    return total, digests


def _read_snapshot(source: Path, game: str) -> tuple[dict, dict[str, Path], dict[str, tuple[int, str]]]:
    try:
        try:
            mode = source.lstat().st_mode
        except FileNotFoundError:
            raise SnapshotError("MISSING", "That build is no longer kept.") from None
        files_dir = source / FILES
        if not stat.S_ISDIR(mode) or not stat.S_ISDIR(files_dir.lstat().st_mode):
            raise OSError("The snapshot is not a directory")
        if not stat.S_ISREG((source / META).lstat().st_mode):
            raise OSError("The snapshot metadata is not a regular file")
        meta = _read_meta(source)
        if meta is None or meta.get("game") != game or meta.get("reason") not in REASONS:
            raise OSError("The snapshot metadata is invalid")
        files = walk(files_dir, stored=True)
        if len(files) > MAX_FILES or type(meta.get("files")) is not int or meta["files"] != len(files):
            raise OSError("The snapshot file count does not match")
        total, digests = _measure(files)
        if total > MAX_BYTES or meta.get("bytes") != total or meta.get("fingerprint") != _fingerprint(digests):
            raise OSError("The snapshot contents do not match")
        return meta, files, digests
    except OSError as error:
        raise SnapshotError(
            "INVALID_SNAPSHOT", "The saved build's files are incomplete, damaged or unreadable."
        ) from error


def take(
    base: Path,
    game: str,
    root: Path,
    reason: str = "build",
    *,
    build_ref: str | None = None,
    build_call: tuple[str, str] | None = None,
    now_ms: int | None = None,
    keep: int = KEEP,
) -> dict:
    """Snapshot the project under its history lock. Answers ``{id, created}`` or ``{skipped}`` at the size cap."""
    if reason not in REASONS:
        raise ValueError(f"unknown snapshot reason {reason!r}")
    root = Path(os.path.realpath(root))
    if not root.is_dir():
        raise SnapshotError("MISSING", f"{root} is not a folder.")
    folder = game_dir(base, game)
    with _locked(folder):
        return _take_locked(
            folder, game, root, walk(root), reason, now_ms, keep, build_ref=build_ref, build_call=build_call
        )


def _take_locked(
    folder: Path,
    game: str,
    root: Path,
    files: dict[str, Path],
    reason: str,
    now_ms: int | None,
    keep: int,
    *,
    from_id: str | None = None,
    build_ref: str | None = None,
    build_call: tuple[str, str] | None = None,
    live: LiveTree | None = None,
) -> dict:
    if len(files) > MAX_FILES:
        return {"skipped": f"more than {MAX_FILES} files"}
    total, digests = _measure(files, live)
    if total > MAX_BYTES:
        return {"skipped": f"larger than {MAX_BYTES // (1024 * 1024)} MB"}
    fingerprint = _fingerprint(digests)
    at = int(now_ms if now_ms is not None else time.time() * 1000)
    newest = next(iter(_ids(folder)), None)
    if newest is not None:
        meta = _read_meta(folder / newest)
        if meta is not None and meta.get("fingerprint") == fingerprint:
            try:
                _read_snapshot(folder / newest, game)
            except SnapshotError:
                pass  # a damaged snapshot is never reused as a build or backup
            else:
                _check_tree(root, files, live)
                if reason == "build":
                    record_build(meta, at, build_ref, build_call)
                elif from_id:
                    meta["backup"] = {"at": at, "from": from_id}
                if reason == "build" or from_id:
                    _write_json(folder / newest / META, meta)
                return {"id": newest, "created": False}
    occurrence = at
    while os.path.lexists(folder / str(at)) or os.path.lexists(folder / f"{at}.part"):
        at += 1
    partial = folder / f"{at}.part"
    partial.mkdir(mode=0o700)
    try:
        stage_id = directory_id(partial.lstat())
        (partial / FILES).mkdir()
        files_id = directory_id((partial / FILES).lstat())
        for relative, source in files.items():
            target = partial / FILES / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            expected = digests[relative]
            with target.open("xb") as writer:
                stamp = live.files[relative][0] if live is not None else None
                if file_digest(source, expected[0], writer, expected_stamp=stamp) != expected:
                    raise OSError(f"{relative} changed during the snapshot operation")
        meta = {
            "at": at,
            "game": game,
            "root": str(root),
            "files": len(files),
            "bytes": total,
            "reason": reason,
            "fingerprint": fingerprint,
            "builds": [],
        }
        if from_id:
            meta["from"] = from_id
        if reason == "build":
            record_build(meta, occurrence, build_ref, build_call)
        _write_json(partial / META, meta)
        staged = walk(partial / FILES, stored=True)
        # Compare the names enumerated on the destination filesystem. Looking up each source name
        # separately could succeed through a case-insensitive alias to a different destination entry.
        if staged.keys() != files.keys() or _measure(staged)[1] != digests:
            raise OSError("The staged snapshot does not match the project files")
        _check_tree(root, files, live)
        if directory_id(partial.lstat()) != stage_id or directory_id((partial / FILES).lstat()) != files_id:
            raise OSError("The staged snapshot folder changed")
        os.replace(partial, folder / str(at))
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    _prune(folder, keep, protect={str(at), from_id})
    return {"id": str(at), "created": True}


def _check_tree(root: Path, files: dict[str, Path], live: LiveTree | None) -> None:
    seen = LiveTree() if live is not None else None
    if live is not None and Path(os.path.realpath(root, strict=True)) != root:
        raise OSError("The registered project folder was redirected")
    if walk(root, live=seen).keys() != files.keys() or (
        live is not None
        and (
            seen.excluded != live.excluded
            or seen.other_games != live.other_games
            or seen.directories != live.directories
        )
    ):
        raise OSError("The project files changed during the snapshot operation")


def _verify_restore(root: Path, root_id: DirectoryId, expected: dict[str, Digest]) -> list[str]:
    """Check the live project after writing, including paths neither restore pass touched."""
    seen = LiveTree()
    try:
        files = walk(root, live=seen)
        if seen.directories[""] != root_id:
            raise OSError("The registered project folder changed")
        if len(files) > MAX_FILES:
            raise OSError("The project exceeds the snapshot file limit")
        problems = [
            *(f"{name}: unexpected file" for name in sorted(files.keys() - expected.keys())),
            *(f"{name}: missing after restore" for name in sorted(expected.keys() - files.keys())),
        ][:20]
        if problems:
            return problems

        total, actual = _measure(files)
        if total > MAX_BYTES:
            raise OSError("The project exceeds the snapshot size limit")
        _check_tree(root, files, seen)
    except OSError as error:
        return [f"Could not verify the restored project: {error}"]

    differences = (
        f"{name}: contents differ from the saved snapshot"
        for name in sorted(expected)
        if actual[name] != expected[name]
    )
    return list(islice(differences, 20))


def restore(
    base: Path,
    game: str,
    root: Path,
    identifier: str,
    *,
    build_ref: str | None = None,
    build_at: int | None = None,
    now_ms: int | None = None,
) -> dict:
    """Validate, back up and restore under one history lock. A restore with problems keeps its backup and counts."""
    identifier = str(identifier or "")
    if not _snapshot_id(identifier):
        raise SnapshotError("MISSING", "That build is no longer kept.")
    root = Path(root).absolute()
    folder = game_dir(base, game)
    with _locked(folder):
        try:
            if Path(os.path.realpath(root, strict=True)) != root:
                raise OSError("the registered path now points to another folder")
            root_id = directory_id(root.lstat())
        except OSError as error:
            raise SnapshotError("NO_GAME", f"The registered project folder could not be opened ({error}).") from error
        meta, wanted, digests = _read_snapshot(folder / identifier, game)
        if (build_ref is not None and build_ref not in build_history(meta, "buildRefs")) or (
            build_at is not None and build_history(meta, "builds").count(build_at) != 1
        ):
            raise SnapshotError("MISSING", "That snapshot no longer matches the selected build.")
        live = LiveTree()
        try:
            current = walk(root, live=live)
            if live.directories[""] != root_id:
                raise OSError("The registered project folder changed")
            backup = _take_locked(
                folder, game, root, current, "before-restore", now_ms, KEEP, from_id=identifier, live=live
            )
        except OSError as error:
            raise SnapshotError("BACKUP_FAILED", f"The current project could not be backed up ({error}).") from error
        if backup.get("skipped"):
            raise SnapshotError("TOO_LARGE", "The current project could not be backed up (" + backup["skipped"] + ").")
        # Older snapshots can contain files in a folder that is now excluded.
        wanted = {
            name: path for name, path in wanted.items() if name.partition("/")[0] not in EXCLUDED_TOP or "/" not in name
        }
        digests = {name: digests[name] for name in wanted}
        changed, removed, problems = _restore_files(root, wanted, digests, live)
        if not problems:
            problems = _verify_restore(root, root_id, digests)
    answer = {"restored": identifier, "backup": backup["id"], "changed": changed, "removed": removed}
    if problems:
        answer["problems"] = problems[:20]
    return answer
