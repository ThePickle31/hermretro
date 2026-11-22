"""Project snapshots for the Build page's build history (Restore per build).

After each successful ``chromatic_rom_build`` of a library game, the project's own files are copied to
``<base>/<game id>/<ms>/files/`` with ``<ms>/snapshot.json`` beside them. A build that changed nothing
adds its time to the newest snapshot's ``builds`` list instead of a new copy. Restoring first keeps the
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


def _holds_project(entries) -> bool:
    """Whether a folder's entries include a game project file (``*.gbsproj`` in any case, a file or a link to one), as
    the engine finds a project."""
    return any(
        entry.name.lower().endswith(PROJECT_SUFFIX) and (entry.is_file() or entry.is_symlink()) for entry in entries
    )


def _other_game(root: Path, relative: str, seen: dict[str, bool]) -> bool:
    """Whether ``relative`` (a file's path under ``root``) lies in a folder below ``root`` that is another game's
    project (holds a ``.gbsproj``). ``seen`` remembers each folder's answer across calls."""
    parts = relative.split("/")[:-1]
    for index in range(1, len(parts) + 1):
        folder = "/".join(parts[:index])
        if folder not in seen:
            try:
                seen[folder] = _holds_project(list(os.scandir(root / folder)))
            except OSError:
                seen[folder] = False
        if seen[folder]:
            return True
    return False


def walk(root: Path, *, exclude_top: bool = True) -> dict[str, Path]:
    """Every regular file under ``root`` by its relative posix path. Symlinks (files or folders) are
    skipped and never followed; so are the excluded top-level folders, temporary files and every folder below
    ``root`` that is another game's project (holds a ``.gbsproj``)."""
    found: dict[str, Path] = {}
    stack = [(Path(root), "")]
    while stack:
        folder, prefix = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        if prefix and _holds_project(entries):
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            relative = f"{prefix}{entry.name}"
            try:
                if entry.is_dir(follow_symlinks=False):
                    if not (exclude_top and not prefix and entry.name in EXCLUDED_TOP):
                        stack.append((Path(entry.path), relative + "/"))
                elif entry.is_file(follow_symlinks=False) and not _temporary(entry.name):
                    found[relative] = Path(entry.path)
            except OSError:
                continue
            if len(found) > MAX_FILES:
                return found
    return found


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        names = [
            entry.name for entry in os.scandir(folder) if entry.name.isdigit() and entry.is_dir(follow_symlinks=False)
        ]
    except OSError:
        return []
    return sorted(names, key=int, reverse=True)


def public(meta: dict, identifier: str) -> dict:
    answer = {
        "id": identifier,
        "at": meta.get("at"),
        "builds": list(meta.get("builds") or []),
        "files": meta.get("files"),
        "bytes": meta.get("bytes"),
        "reason": meta.get("reason"),
    }
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
    for identifier in _ids(folder)[keep:]:
        if identifier not in protect:
            shutil.rmtree(folder / identifier, ignore_errors=True)
    now = time.time()
    try:
        for entry in os.scandir(folder):
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
        size = path.stat().st_size
        total += size
        if total > MAX_BYTES:
            return total, {}
        digests[relative] = (size, _sha256(path))
    return total, digests


def take(
    base: Path,
    game: str,
    root: Path,
    reason: str = "build",
    *,
    from_id: str | None = None,
    now_ms: int | None = None,
    keep: int = KEEP,
    protect=(),
) -> dict:
    """Snapshot ``root`` for ``game``. Answers ``{id, created}`` (``created`` False when the newest
    snapshot already holds exactly these files; a build is then added to its ``builds``), or
    ``{skipped}`` with the reason when the project is too large to keep."""
    if reason not in REASONS:
        raise ValueError(f"unknown snapshot reason {reason!r}")
    root = Path(os.path.realpath(root))
    if not root.is_dir():
        raise SnapshotError("MISSING", f"{root} is not a folder.")
    folder = game_dir(base, game)
    at = int(now_ms if now_ms is not None else time.time() * 1000)
    with _locked(folder):
        files = walk(root)
        if len(files) > MAX_FILES:
            return {"skipped": f"more than {MAX_FILES} files"}
        total, digests = _measure(files)
        if total > MAX_BYTES:
            return {"skipped": f"larger than {MAX_BYTES // (1024 * 1024)} MB"}
        fingerprint = _fingerprint(digests)
        newest = _ids(folder)[:1]
        if newest:
            meta = _read_meta(folder / newest[0])
            if meta is not None and meta.get("fingerprint") == fingerprint:
                if reason == "build":
                    builds = [value for value in meta.get("builds") or [] if isinstance(value, int)]
                    meta["builds"] = (builds + [at])[-200:]
                    _write_json(folder / newest[0] / META, meta)
                return {"id": newest[0], "created": False}
        while (folder / str(at)).exists() or (folder / f"{at}.part").exists():
            at += 1
        partial = folder / f"{at}.part"
        stored: dict[str, tuple[int, str]] = {}
        try:
            for relative, source in files.items():
                target = partial / FILES / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                with open(source, "rb") as reader, open(target, "wb") as writer:
                    for chunk in iter(lambda: reader.read(_CHUNK), b""):
                        digest.update(chunk)
                        size += len(chunk)
                        writer.write(chunk)
                stored[relative] = (size, digest.hexdigest())
            meta = {
                "at": at,
                "game": game,
                "root": str(root),
                "files": len(stored),
                "bytes": sum(size for size, _sha in stored.values()),
                "reason": reason,
                "fingerprint": _fingerprint(stored),
                "builds": [at] if reason == "build" else [],
            }
            if from_id:
                meta["from"] = str(from_id)
            _write_json(partial / META, meta)
            os.replace(partial, folder / str(at))
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise
        _prune(folder, keep, protect={str(at), *protect})
        return {"id": str(at), "created": True}


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


def restore(base: Path, game: str, root: Path, identifier: str, *, now_ms: int | None = None) -> dict:
    """Make ``root``'s files match snapshot ``identifier``, after keeping the current files as a
    ``before-restore`` snapshot. Answers ``{restored, backup, changed, removed}`` (+ ``problems``)."""
    identifier = str(identifier or "")
    folder = game_dir(base, game)
    source = folder / identifier
    if not identifier.isdigit() or not (source / META).is_file() or not (source / FILES).is_dir():
        raise SnapshotError("MISSING", "That build is no longer kept.")
    root = Path(os.path.realpath(root))
    if not root.is_dir():
        raise SnapshotError("NO_GAME", f"{root} is not a folder.")
    backup = take(base, game, root, "before-restore", from_id=identifier, now_ms=now_ms, protect={identifier})
    if backup.get("skipped"):
        raise SnapshotError(
            "TOO_LARGE",
            "The project could not be backed up first (" + backup["skipped"] + "), so nothing was restored.",
        )
    if not (source / META).is_file():
        raise SnapshotError("MISSING", "That build is no longer kept.")
    with _locked(folder):
        wanted = walk(source / FILES, exclude_top=False)
        current = walk(root)
        removed = changed = 0
        problems = []
        games: dict[str, bool] = {}
        for relative in sorted(set(current) - set(wanted)):
            try:
                os.unlink(current[relative])
                removed += 1
            except OSError as error:
                problems.append(f"{relative}: {error.strerror or error}")
                continue
            parent = current[relative].parent
            while parent != root and root in parent.parents:
                try:
                    parent.rmdir()  # only succeeds while empty
                except OSError:
                    break
                parent = parent.parent
        for relative in sorted(wanted):
            if relative.split("/", 1)[0] in EXCLUDED_TOP or _other_game(root, relative, games):
                continue  # a folder that is now another game's project is that game's to keep
            here = current.get(relative)
            if here is not None and here.is_file() and not here.is_symlink():
                try:
                    if here.stat().st_size == wanted[relative].stat().st_size and _sha256(here) == _sha256(
                        wanted[relative]
                    ):
                        continue
                except OSError:
                    pass
            partial = None
            try:
                parent = _safe_parent(root, relative)
                if parent is None:
                    problems.append(f"{relative}: a link or file is in the way")
                    continue
                target = parent / relative.rsplit("/", 1)[-1]
                if os.path.islink(target):
                    problems.append(f"{relative}: a link is in the way")
                    continue
                # A new temporary file of its own (never one already there, which could be a link elsewhere), and
                # a plain copy: the restored file gets a new modification time, so the game counts as changed
                # since its last build and the page asks for a rebuild.
                handle, partial = tempfile.mkstemp(dir=parent, prefix=f".{target.name}.", suffix=".hr-restore")
                with os.fdopen(handle, "wb") as writer, open(wanted[relative], "rb") as reader:
                    shutil.copyfileobj(reader, writer, _CHUNK)
                os.replace(partial, target)
                changed += 1
            except OSError as error:
                problems.append(f"{relative}: {error.strerror or error}")
                if partial is not None:
                    try:
                        os.unlink(partial)
                    except OSError:
                        pass
    answer = {"restored": identifier, "backup": backup["id"], "changed": changed, "removed": removed}
    if problems:
        answer["problems"] = problems[:20]
    return answer
