"""Development-only helpers. Not part of the plugin runtime."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.system import paths  # noqa: E402
from backend.broker.engine import EngineProcess  # noqa: E402,F401


def dev_engine_root() -> Path:
    """The bundled engine, or another copy named by HERMRETRO_DEV_ENGINE_ROOT for comparison."""
    override = os.environ.get("HERMRETRO_DEV_ENGINE_ROOT")
    return Path(override).resolve(strict=True) if override else paths.ENGINE_ROOT
