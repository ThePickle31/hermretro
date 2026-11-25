"""Which library game a path belongs to, and whether a game's files may be edited.

A path belongs to the deepest library game whose folder is or holds it, so a project inside another game's folder is
never taken for that game. Folders are matched by file-system identity (device and inode of the path's existing
ancestors), not by spelling: a macOS volume that ignores letter case finds the same folder under any case, and one
that keeps case apart keeps two folders differing only by case apart. Paths are read as the engine reads them:
``..`` is collapsed first (``path.resolve``), then links are followed.

Pure functions over paths and a registry snapshot: no Hermes, broker or registry imports.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import layout, project
from .project import project_file


def engine_path(path: str, base: str | None = None) -> Path:
    """``path`` as the engine resolves it: made absolute against ``base`` (else this process's folder), ``..`` and
    ``.`` collapsed by spelling, then every link followed."""
    joined = os.path.join(base, path) if base and not os.path.isabs(path) else path
    return Path(os.path.realpath(os.path.normpath(os.path.abspath(joined))))


def entry_path(path: str, *, spelling: bool = True) -> Path:
    """A directory entry itself (what a delete or a move acts on): its folder resolved, its own name kept, so a link
    is the link and not what it points to. ``spelling`` collapses ``..`` before following links (as the engine does);
    otherwise links come first (as ``Path.resolve`` does)."""
    absolute = os.path.abspath(path) if not spelling else os.path.normpath(os.path.abspath(path))
    parent, name = os.path.split(absolute.rstrip(os.sep) or os.sep)
    if not name or name in (".", ".."):
        return Path(os.path.realpath(absolute))
    return Path(os.path.realpath(parent), name)


def _identity(path: Path) -> tuple[int, int] | None:
    try:
        info = path.stat()
    except (OSError, ValueError):
        return None
    return (info.st_dev, info.st_ino)


def root_index(games: dict) -> dict[tuple[int, int], tuple[str, dict, Path]]:
    """``{(device, inode): (game id, entry, real root)}`` for every library game whose folder exists."""
    index: dict[tuple[int, int], tuple[str, dict, Path]] = {}
    for identifier, entry in games.items():
        if not project.valid_id(identifier) or not isinstance(entry, dict):
            continue
        root = entry.get("projectRoot")
        if not isinstance(root, str) or not root:
            continue
        real = Path(os.path.realpath(root))
        identity = _identity(real) if real.is_dir() else None
        if identity is not None:
            index.setdefault(identity, (identifier, entry, real))
    return index


def identities(folders) -> dict[tuple[int, int], Path]:
    """``{(device, inode): folder}`` for the existing ``folders``, for ``owner_in``."""
    return {identity: Path(folder) for folder in folders if (identity := _identity(Path(folder))) is not None}


def owner_in(index: dict, path: Path):
    """The value of ``index`` (keyed by folder identity) for the deepest folder that is or holds ``path``, which need
    not exist yet; None when no folder of ``index`` holds it."""
    for folder in (path, *path.parents):
        found = index.get(_identity(folder)) if os.path.lexists(folder) else None
        if found is not None:
            return found
    return None


def record_dirs(index: dict) -> list[Path]:
    """Every game's ``.hermretro/`` where it really is: a link there points the record somewhere else."""
    return [
        Path(os.path.realpath(root / layout.STATE_DIR))
        for _identifier, _entry, root in index.values()
        if os.path.lexists(root / layout.STATE_DIR)
    ]


def editable(root: Path) -> bool:
    """Whether a game's files are edited at all: it has its source (a GB Studio project file or C sources), and is
    not a game installed without its source (``.hermretro/install.json``'s ``mode`` ``game``)."""
    root = Path(root)
    if layout.state(root, layout.INSTALL_FILE).get("mode") == "game":
        return False
    if project_file(root) is not None:
        return True
    try:
        return any(root.glob("*.c")) or any(root.glob("src/**/*.c"))
    except OSError:
        return False
