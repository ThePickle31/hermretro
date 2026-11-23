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
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

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
PROJECT_SUFFIX = ".gbsproj"
_CHUNK = 1024 * 1024


class SnapshotError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _temporary(name: str) -> bool:
    return name.endswith(TEMP_SUFFIXES) or name.startswith(".~")


def walk(root: Path, *, stored: bool = False, other_games: set[str] | None = None) -> dict[str, Path]:
    """Scan the whole tree up to the file cap, propagating I/O errors. A live project has exclusions, while stored
    files must all be accounted for by the snapshot manifest."""
    found: dict[str, Path] = {}
    stack = [(Path(root), "")]
    while stack:
        folder, prefix = stack.pop()
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
            if other_games is not None:
                other_games.add(prefix[:-1])
            continue
        for entry, mode in entries:
            relative = f"{prefix}{entry.name}"
            if stat.S_ISDIR(mode):
                if stored or prefix or entry.name not in EXCLUDED_TOP:
                    stack.append((Path(entry.path), relative + "/"))
            elif stat.S_ISREG(mode):
                if stored or not _temporary(entry.name):
                    found[relative] = Path(entry.path)
            elif stored:
                raise OSError(f"Unexpected entry in the snapshot: {relative}")
            if len(found) > MAX_FILES:
                return found
    return found


def _file_digest(path: Path, limit: int, writer=None) -> tuple[int, str]:
    """Read a regular file without following a final symlink, optionally copying it in the same pass."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb", opener=lambda name, flags: os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK)) as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise OSError(f"{path} is no longer a regular file")
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            size += len(chunk)
            if size > limit:
                raise OSError(f"{path} became larger during the snapshot operation")
            digest.update(chunk)
            if writer is not None:
                writer.write(chunk)
    return size, digest.hexdigest()


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


def _history(meta: dict, key: str) -> list:
    values = meta.get(key)
    return values if isinstance(values, list) else []


def public(meta: dict, identifier: str) -> dict:
    answer = {
        "id": identifier,
        "at": meta.get("at"),
        "builds": _history(meta, "builds"),
        "files": meta.get("files"),
        "bytes": meta.get("bytes"),
        "reason": meta.get("reason"),
    }
    if refs := _history(meta, "buildRefs"):
        answer["buildRefs"] = refs
    if meta.get("from"):
        answer["from"] = meta["from"]
    return answer


def list_snapshots(base: Path, game: str) -> list[dict]:
    """Every snapshot of one game, newest first (without fingerprints)."""
    folder = game_dir(base, game)
    listed = []
    for identifier in _ids(folder):
        meta = _read_meta(folder / identifier)
        if meta is not None:
            listed.append(public(meta, identifier))
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


def _measure(files: dict[str, Path]) -> tuple[int, dict[str, tuple[int, str]]]:
    digests = {}
    total = 0
    for relative, path in files.items():
        size = path.lstat().st_size
        total += size
        if total > MAX_BYTES:
            return total, {}
        measured = _file_digest(path, size)
        if measured[0] != size:
            raise OSError(f"{path} changed during the snapshot operation")
        digests[relative] = measured
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


def _record_build(meta: dict, at: int, build_ref: str | None) -> None:
    # Older builds only have occurrence times. Keeping the new references separate prevents a legacy lookup
    # from picking the files of an unrelated new build whose time happens to fall in its turn.
    if build_ref:
        refs = _history(meta, "buildRefs")
        if build_ref not in refs:
            meta["buildRefs"] = [*refs, build_ref]
    else:
        meta["builds"] = [*_history(meta, "builds"), at][-200:]


def take(
    base: Path,
    game: str,
    root: Path,
    reason: str = "build",
    *,
    build_ref: str | None = None,
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
        return _take_locked(folder, game, root, walk(root), reason, now_ms, keep, build_ref=build_ref)


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
    other_games: set[str] | None = None,
) -> dict:
    if len(files) > MAX_FILES:
        return {"skipped": f"more than {MAX_FILES} files"}
    total, digests = _measure(files)
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
                _check_tree(root, files, other_games)
                if reason == "build":
                    _record_build(meta, at, build_ref)
                    _write_json(folder / newest / META, meta)
                return {"id": newest, "created": False}
    occurrence = at
    while os.path.lexists(folder / str(at)) or os.path.lexists(folder / f"{at}.part"):
        at += 1
    partial = folder / f"{at}.part"
    try:
        (partial / FILES).mkdir(parents=True)
        for relative, source in files.items():
            target = partial / FILES / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            expected = digests[relative]
            with target.open("wb") as writer:
                if _file_digest(source, expected[0], writer) != expected:
                    raise OSError(f"{relative} changed during the snapshot operation")
        _check_tree(root, files, other_games)
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
            _record_build(meta, occurrence, build_ref)
        _write_json(partial / META, meta)
        os.replace(partial, folder / str(at))
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    _prune(folder, keep, protect={str(at), from_id})
    return {"id": str(at), "created": True}


def _check_tree(root: Path, files: dict[str, Path], other_games: set[str] | None) -> None:
    seen_games = set() if other_games is not None else None
    if walk(root, other_games=seen_games).keys() != files.keys() or seen_games != other_games:
        raise OSError("The project files changed during the snapshot operation")


def _safe_parent(root: Path, relative: str) -> Path | None:
    """The folder ``relative`` goes into, created as needed, or None when any part of the way is a
    symlink or a file (never written through)."""
    current = root
    for part in relative.split("/")[:-1]:
        current = current / part
        if os.path.islink(current):
            return None
        if current.exists():
            if not current.is_dir():
                return None
        else:
            current.mkdir()
    return current


def _below_other_game(relative: str, other_games: set[str]) -> bool:
    parent, _, _ = relative.rpartition("/")
    while parent:
        if parent in other_games:
            return True
        parent, _, _ = parent.rpartition("/")
    return False


def _restore_files(
    root: Path,
    wanted: dict[str, Path],
    digests: dict[str, tuple[int, str]],
    current: dict[str, Path],
    other_games: set[str],
) -> tuple[int, int, list[str]]:
    removed = changed = 0
    problems = []
    for relative in sorted(current.keys() - wanted.keys()):
        try:
            current[relative].unlink()
            removed += 1
        except OSError as error:
            problems.append(f"{relative}: {error.strerror or error}")
            continue
        parent = current[relative].parent
        while parent != root:
            try:
                parent.rmdir()  # only succeeds while empty
            except OSError:
                break
            parent = parent.parent
    for relative, source in sorted(wanted.items()):
        if "/" in relative and relative.split("/", 1)[0] in EXCLUDED_TOP:
            continue  # older snapshots can contain files that are now excluded
        if _below_other_game(relative, other_games):
            problems.append(f"{relative}: now part of another game")
            continue
        expected = digests[relative]
        here = current.get(relative)
        if here is not None:
            try:
                if here.lstat().st_size == expected[0] and _file_digest(here, expected[0]) == expected:
                    continue
            except OSError:
                pass  # try replacing a file we could not read
        partial = None
        try:
            parent = _safe_parent(root, relative)
            if parent is None:
                problems.append(f"{relative}: a link or file is in the way")
                continue
            target = parent / relative.rsplit("/", 1)[-1]
            if target.is_symlink():
                problems.append(f"{relative}: a link is in the way")
                continue
            # A fresh sibling gives the restored file a new modification time, so it counts as changed.
            handle, partial = tempfile.mkstemp(dir=parent, prefix=f".{target.name}.", suffix=".hr-restore")
            with os.fdopen(handle, "wb") as writer:
                if _file_digest(source, expected[0], writer) != expected:
                    raise OSError("the saved file changed during the restore")
            os.replace(partial, target)
            changed += 1
        except OSError as error:
            problems.append(f"{relative}: {error.strerror or error}")
            if partial is not None:
                try:
                    os.unlink(partial)
                except OSError:
                    pass
    return changed, removed, problems


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
    root = Path(os.path.realpath(root))
    if not root.is_dir():
        raise SnapshotError("NO_GAME", f"{root} is not a folder.")
    folder = game_dir(base, game)
    with _locked(folder):
        meta, wanted, digests = _read_snapshot(folder / identifier, game)
        if (build_ref is not None and build_ref not in _history(meta, "buildRefs")) or (
            build_at is not None and _history(meta, "builds").count(build_at) != 1
        ):
            raise SnapshotError("MISSING", "That snapshot no longer matches the selected build.")
        other_games: set[str] = set()
        try:
            current = walk(root, other_games=other_games)
            backup = _take_locked(
                folder, game, root, current, "before-restore", now_ms, KEEP, from_id=identifier, other_games=other_games
            )
        except OSError as error:
            raise SnapshotError("BACKUP_FAILED", f"The current project could not be backed up ({error}).") from error
        if backup.get("skipped"):
            raise SnapshotError("TOO_LARGE", "The current project could not be backed up (" + backup["skipped"] + ").")
        changed, removed, problems = _restore_files(root, wanted, digests, current, other_games)
    answer = {"restored": identifier, "backup": backup["id"], "changed": changed, "removed": removed}
    if problems:
        answer["problems"] = problems[:20]
    return answer
