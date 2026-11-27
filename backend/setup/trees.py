"""Whole file trees in hermretro's folders: how many bytes one holds, and deleting one. Links are counted and
deleted as themselves, never followed. Stdlib only."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def remove_tree(path: Path) -> None:
    """Delete a tree, making read-only folders (from extracted archives) writable when a delete is refused."""

    def retry(function, failed, _info):
        try:
            parent = os.path.dirname(failed)
            # Only inside the tree being deleted: the folder that holds it is never made writable.
            if Path(parent).is_relative_to(path):
                os.chmod(parent, 0o700)
            if os.path.isdir(failed) and not os.path.islink(failed):
                os.chmod(failed, 0o700)
            function(failed)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def folder_bytes(path: Path) -> int:
    """Bytes in a whole file or folder tree (links counted as themselves, never followed)."""
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size
    return sum(child.lstat().st_size for child in path.rglob("*") if not child.is_dir() or child.is_symlink())
