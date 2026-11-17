"""Build history's Hermes hook: after a successful build of a library game, keep a snapshot of its files
(``post_tool_call``; assets' own post_tool_call runs first, see backend/features.py)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .. import library
from ..hermes import host
from ..hermes.declare import hook
from ..system.events import emit
from . import snapshots
from .rpcs import _snapshots_dir

logger = host.logger


def _result_payload(result):
    """A tool result as the model saw it: the JSON text, or the multimodal envelope's text summary."""
    if isinstance(result, dict) and result.get("_multimodal"):
        result = result.get("text_summary")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return None
    return result if isinstance(result, dict) else None


def build_succeeded(result, status=None) -> bool:
    """Whether a delivered ``chromatic_rom_build`` result is a successful build: no error from Hermes or
    the backend, and the engine's own ``structuredContent.success`` is true."""
    if status not in (None, "", "ok"):
        return False
    payload = _result_payload(result)
    if not payload or payload.get("error") or payload.get("isError"):
        return False
    structured = payload.get("structuredContent")
    return isinstance(structured, dict) and structured.get("success") is True


def _library_root_for(candidates) -> tuple[str, Path] | None:
    """The first library game whose project is, or contains, one of ``candidates``."""
    games = [
        entry
        for entry in host._registry().load()["games"].values()
        if isinstance(entry, dict) and isinstance(entry.get("projectRoot"), str)
    ]
    roots = []
    for entry in games:
        try:
            roots.append(Path(os.path.realpath(entry["projectRoot"])))
        except (OSError, ValueError):
            continue
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate:
            continue
        try:
            real = Path(os.path.realpath(candidate))
        except (OSError, ValueError):
            continue
        for root in roots:
            if (real == root or root in real.parents) and root.is_dir():
                return library.game_id(root), root
    return None


@hook("post_tool_call")
def snapshot_after_build(
    tool_name=None, args=None, result=None, status=None, conversation_id=None, session_id=None, **_kwargs
):
    """``post_tool_call``: after a successful build of a library game, keep a snapshot of its files for
    the Build page's history (Restore). Never raises."""
    try:
        if tool_name != "chromatic_rom_build" or not build_succeeded(result, status):
            return
        args = args if isinstance(args, dict) else {}
        if args.get("sourcePath"):
            return  # a standalone C experiment, not the game's build
        structured = (_result_payload(result) or {}).get("structuredContent") or {}
        candidates = [structured.get("projectRoot"), args.get("projectPath")]
        try:
            candidates.append(host._chat_project(str(conversation_id or ""), str(session_id or "")))
        except Exception:
            logger.debug("hermretro: no chat project for the build snapshot", exc_info=True)
        candidates += [structured.get("outputPath"), structured.get("romPath")]
        found = _library_root_for(candidates)
        if found is None:
            return
        game, root = found
        taken = snapshots.take(_snapshots_dir(), game, root, "build")
        if taken.get("skipped"):
            logger.debug("hermretro: build snapshot of %s skipped: %s", root, taken["skipped"])
        else:
            emit("history.build_kept", game=game, root=root)
    except Exception:
        logger.debug("hermretro snapshot_after_build failed", exc_info=True)
