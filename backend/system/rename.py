"""Directory publication with the filesystem's no-replace guarantee on Linux and macOS."""

import ctypes
import os
import sys


def rename_unoccupied(source: str, target: str, *, source_dir: int, target_dir: int) -> None:
    """Rename relative to open directories. An empty destination directory also counts as occupied."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename, flag = libc.renameatx_np, 0x4  # RENAME_EXCL
    else:
        rename, flag = libc.renameat2, 1  # RENAME_NOREPLACE
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source_dir, os.fsencode(source), target_dir, os.fsencode(target), flag):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), target)
