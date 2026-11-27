"""Emptying hermretro's download folder ``<hermretro home>/.cache``: Setup's "remove the tools" and the factory reset's
toolchain part. Stdlib only."""

from __future__ import annotations

import os
import tempfile
from contextlib import ExitStack
from pathlib import Path

from ..system import paths
from . import copy_lease, provision
from .trees import folder_bytes, remove_tree


def remove_downloads() -> dict:
    """Empty hermretro's download folder ``<hermretro home>/.cache`` (toolchain, prepared engine with ModRetro's
    CLI, receipts). Games and the library are elsewhere and untouched; links inside are removed, never followed.
    The caller holds the broker's election lock, so no broker or worker runs from it meanwhile. Refused when the
    location was configured by hand, since that folder is the user's."""
    if os.environ.get("HERMRETRO_DEPS_ROOT") or os.environ.get("GB_STUDIO_SETUP_ROOT"):
        raise provision.ProvisionError(
            "CUSTOM_LOCATION",
            "The downloaded tools are in a folder you configured "
            "(HERMRETRO_DEPS_ROOT or GB_STUDIO_SETUP_ROOT); delete it yourself.",
        )
    root = paths.DEPS_ROOT
    home = paths.hermretro_home().resolve()
    if root != home / ".cache" or root.is_relative_to(paths.PLUGIN_ROOT) or root.is_symlink():
        raise provision.ProvisionError(
            "UNEXPECTED_LOCATION", f"Refusing to delete {root}: it is not hermretro's download folder."
        )
    if not root.is_dir():
        return {"ok": True, "removed_bytes": 0, "left_bytes": 0, "root": str(root)}
    with provision.lock(), ExitStack() as leases:  # no device-CLI install meanwhile, and no worker in a copy
        for copy in root.glob("engine-*"):
            # The caller stopped the broker: a copy from before leases, without a lease file, has no worker of it.
            in_use = not leases.enter_context(copy_lease.unused(copy, unleased_is_unused=True))
            if copy.is_dir() and not copy.is_symlink() and in_use:
                raise provision.ProvisionError("IN_USE", provision.IN_USE)
        # Inside .cache, so every move is a rename on the same filesystem; the folder empties at once.
        trash = Path(tempfile.mkdtemp(prefix=_TRASH_PREFIX, dir=root))
        for child in list(root.iterdir()):
            if child.name == ".provision.lock" or child.name.startswith(_TRASH_PREFIX):
                continue
            os.replace(child, trash / child.name)
    removed = 0
    for leftover in [p for p in root.iterdir() if p.name.startswith(_TRASH_PREFIX)]:  # also earlier, failed runs
        removed += folder_bytes(leftover)
        remove_tree(leftover)
    left = sum(folder_bytes(p) for p in root.iterdir() if p.name.startswith(_TRASH_PREFIX))
    return {
        "ok": not left,
        "removed_bytes": removed - left,
        "left_bytes": left,
        "root": str(root),
        **(
            {"code": "PARTLY_REMOVED", "error": f"{left // 1_000_000} MB could not be deleted from {root}."}
            if left
            else {}
        ),
    }


_TRASH_PREFIX = ".removing-"
