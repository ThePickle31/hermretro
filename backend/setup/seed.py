"""Reusing another install's download cache for the toolchain (ModRetro's Codex plugin keeps one). Stdlib only."""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import time
from pathlib import Path

from ..system import paths

_SETUP_MARKER = ".gb-studio-setup.json"
_SEED_PARTS = ("downloads", "cache")
TOOLCHAIN_SEED_RECORD = "toolchain-seed.json"


def shared_setup_root() -> Path:
    """Where the engine keeps its toolchain when another app (ModRetro's Codex plugin) hosts it."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "modretro-chromatic"
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "modretro-chromatic"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "modretro-chromatic"


def seed_toolchain_cache(source: Path | None = None) -> dict:
    """Copy another install's verified download cache into this plugin's own toolchain folder.

    Only the engine's download archives and package caches are copied, never an installed toolchain:
    the engine then installs from them into the toolchain folder exactly as it would after downloading,
    re-checking every archive against its pinned SHA-256. The other install is read, never changed.
    Happens only for a toolchain folder that does not exist yet."""
    destination = paths.setup_root()
    source = Path(source) if source is not None else shared_setup_root()
    if os.environ.get("GB_STUDIO_SETUP_ROOT"):
        return {"seeded": False, "reason": "a custom toolchain folder is configured"}
    if destination.exists():
        return {"seeded": False, "reason": "the toolchain folder already exists"}
    try:
        if source.resolve() == destination.resolve() or not source.is_dir() or source.is_symlink():
            return {"seeded": False, "reason": "no other install found"}
        marker = source / _SETUP_MARKER
        info = marker.lstat()
        owner = getattr(os, "getuid", lambda: info.st_uid)()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_size > 4096
            or info.st_uid != owner
            or source.lstat().st_uid != owner
            or json.loads(marker.read_text()).get("owner") != "codex-gb-studio-setup"
        ):
            return {"seeded": False, "reason": "the other install is not an engine-owned setup folder"}
        parts = [name for name in _SEED_PARTS if (source / name).is_dir() and not (source / name).is_symlink()]
        if "downloads" not in parts:
            return {"seeded": False, "reason": "the other install has no download cache"}
        paths.DEPS_ROOT.mkdir(mode=0o755, parents=True, exist_ok=True)
        stage = paths.DEPS_ROOT / f"toolchain.seeding-{os.getpid()}"
        shutil.rmtree(stage, ignore_errors=True)
        try:
            stage.mkdir(mode=0o700)
            for name in parts:
                shutil.copytree(source / name, stage / name, symlinks=True)
            shutil.copy2(marker, stage / _SETUP_MARKER)
            os.rename(stage, destination)  # fails if a toolchain folder appeared meanwhile
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        record = {
            "seeded": True,
            "from": str(source),
            "parts": parts,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        (paths.DEPS_ROOT / TOOLCHAIN_SEED_RECORD).write_text(json.dumps(record, indent=2) + "\n")
        return record
    except (OSError, ValueError) as error:
        return {"seeded": False, "reason": f"could not reuse the other install's cache: {error}"}


def _seed_source() -> str | None:
    try:
        return json.loads((paths.DEPS_ROOT / TOOLCHAIN_SEED_RECORD).read_text()).get("from")
    except (OSError, ValueError):
        return None
