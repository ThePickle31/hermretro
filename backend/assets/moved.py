"""A game's kept image versions follow it to a new folder (an installed game's edited copy that became a game of its own,
``library.game_moved``). Versions are filed by the folder an image is shown from and the image's own path
(``versions._versions_dir``), so each image of the moved game takes its versions from its old path to its new one;
the game that took the old folder starts with none."""

from __future__ import annotations

import os
from pathlib import Path

from ..hermes import host
from . import versions


def move_game_versions(old_root: str, new_root: str) -> int:
    """Move the kept versions of every image in ``new_root`` from where they were filed under ``old_root``; an image
    that already has versions at its new place keeps those. Returns how many images' versions moved."""
    base = host._data_dir() / "asset-versions"
    old, new = Path(os.path.realpath(old_root)), Path(os.path.realpath(new_root))
    if not base.is_dir() or not new.is_dir():
        return 0
    moved = 0
    for directory, folders, names in os.walk(new):
        folders[:] = [name for name in folders if not (Path(directory) / name).is_symlink()]
        for name in names:
            image = Path(directory, name)
            if image.suffix.lower() not in versions.ASSET_SUFFIXES or image.is_symlink():
                continue
            relative = image.relative_to(new)
            before = base / versions._digest(f"{old}\0{old / relative}")
            after = base / versions._digest(f"{new}\0{image}")
            if before.is_dir() and not os.path.lexists(after):
                with versions._version_lock(image):
                    os.rename(before, after)
                moved += 1
    return moved
