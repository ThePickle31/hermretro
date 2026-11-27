"""An engine folder against its manifest: which of its files count, their digests and modes, and the manifest's own
digest. No locations: backend/system/paths.py applies these to the bundled engine and its prepared copy, and
tools/engine/manifest.py writes the manifest with them. Stdlib only."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_bytecode(name: str) -> bool:
    """Whether a file or folder name is Python's own bytecode, which running the engine's scripts writes."""
    return name == "__pycache__" or name.endswith(".pyc")


def is_left_beside(name: str) -> bool:
    """Whether a file or folder name is one the system writes beside the engine's files rather than part of it:
    Python's bytecode, or the .DS_Store macOS Finder leaves in a folder it showed (git ignores both, so an update
    keeps them). Never recorded in the manifest, compared with it nor copied into the prepared engine."""
    return is_bytecode(name) or name == ".DS_Store"


# hermretro's record of the engine, at its top: its contract (tool contracts and manifest, paths.ENGINE_PINS) and its
# changelog.
ENGINE_RECORD = ("contract", "CHANGES.md")


def is_engine_record(root: Path | str, path: Path | str) -> bool:
    """Whether path is part of the engine's record (ENGINE_RECORD), which no copy or manifest of the engine holds: a
    note in the changelog is not a change to the engine."""
    return Path(path).parent == Path(root) and Path(path).name in ENGINE_RECORD


def engine_entries(root: Path, *, engine_folder: bool = True) -> list[Path]:
    """Every file and link under root, sorted, but Python's bytecode and, in an engine folder (the bundled engine or
    another checkout's), its record. A running script writes bytecode and renames it into place meanwhile, so it is
    left out by name from the folder listing, before anything stats it; a link is listed whatever its name. A copy of
    the engine holds no record, so one there is listed like any other file."""
    found: list[Path] = []
    folders = [root]
    while folders:
        with os.scandir(folders.pop()) as listing:
            for entry in listing:
                if entry.is_symlink():
                    found.append(Path(entry.path))
                elif is_left_beside(entry.name) or (engine_folder and is_engine_record(root, entry.path)):
                    continue
                elif entry.is_dir():
                    folders.append(Path(entry.path))
                else:
                    found.append(Path(entry.path))
    return sorted(found)


def compare_tree(
    root: Path,
    expected: dict[str, str],
    optional: frozenset[str] = frozenset(),
    *,
    engine_folder: bool = True,
    executable: dict[str, bool] | None = None,
) -> list[str]:
    """Every regular file under root against rel -> SHA-256. No extras, no symlinks. With ``executable`` (rel -> whether
    its owner may run it, from the manifest), a file listed there must also keep that bit: the engine runs some itself.
    Group and world bits are the checkout's umask, so they are not compared."""
    problems: list[str] = []
    seen: set[str] = set()
    for path in engine_entries(root, engine_folder=engine_folder):
        info = path.lstat()
        rel = path.relative_to(root).as_posix()
        if stat.S_ISLNK(info.st_mode):
            problems.append(f"unexpected symlink {rel}")
        elif stat.S_ISREG(info.st_mode):
            seen.add(rel)
            if rel not in expected:
                problems.append(f"unexpected file {rel}")
            elif file_sha256(path) != expected[rel]:
                problems.append(f"changed {rel}")
            elif executable is not None and rel in executable and bool(info.st_mode & stat.S_IXUSR) != executable[rel]:
                problems.append(f"changed mode of {rel}")
    problems.extend(f"missing {rel}" for rel in sorted(set(expected) - seen - optional))
    return problems


def describe_problems(problems: list[str]) -> str:
    return "; ".join(problems[:5]) + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else "")


def executable(entries: list[dict]) -> dict[str, bool]:
    """rel -> whether a manifest's entries record the file as runnable by its owner."""
    return {e["path"]: bool(int(e["mode"], 8) & stat.S_IXUSR) for e in entries if "mode" in e}


def manifest_digest(entries: list[dict]) -> str:
    """The digest of a manifest's entries, its ``aggregate_sha256`` (tools/engine/manifest.py writes it)."""
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
