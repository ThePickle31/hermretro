"""The Build page's build history: the builds and build_restore RPCs over the snapshots in snapshots.py."""

from __future__ import annotations

from pathlib import Path

from ..hermes import host
from ..hermes.declare import rpc
from . import snapshots

logger = host.logger  # one logger for the Hermes side of the backend


def _snapshots_dir() -> Path:
    return host._data_dir() / "snapshots"


@rpc("builds")
def rpc_builds(ctx):
    """The Build page's build history for one library game: ``{game}`` → its snapshots, newest first."""

    def builds(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            game = str(params.get("game") or "")
            if host._game_root(game) is None:
                return {"ok": False, "code": "NO_GAME", "error": "Only a game in your library has builds."}
            return {"ok": True, "builds": snapshots.list_snapshots(_snapshots_dir(), game)}
        except Exception as error:
            logger.exception("hermretro builds failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}

    return builds


@rpc("build_restore")
def rpc_build_restore(ctx):
    """Put a game's files back as they were at one build (``{game, id}``). The current files are kept
    first as a ``before-restore`` snapshot; the page then asks the agent to rebuild."""

    def build_restore(params, **_kwargs):
        try:
            params = params if isinstance(params, dict) else {}
            game = str(params.get("game") or "")
            root = host._game_root(game)
            if root is None:
                return {"ok": False, "code": "NO_GAME", "error": "Only a game in your library can be restored."}
            identifier = str(params.get("id") or "")
            restored = snapshots.restore(
                _snapshots_dir(),
                game,
                root,
                identifier,
                build_ref=params.get("buildRef"),
                build_at=params.get("buildAt"),
            )
            if restored.get("problems"):
                return {"ok": False, "code": "PARTIAL", "error": "Some files could not be restored.", **restored}
            return {"ok": True, **restored}
        except snapshots.SnapshotError as error:
            return {"ok": False, "code": error.code, "error": str(error)}
        except Exception as error:
            logger.exception("hermretro build_restore failed")
            return {"ok": False, "code": "ERROR", "error": f"{type(error).__name__}: {error}"}

    return build_restore
