"""Build history's Hermes hook: after a successful build of a library game, keep a snapshot of its files
(``post_tool_call``; assets' own post_tool_call runs first, see backend/features.py)."""

from __future__ import annotations

from ..hermes import host
from ..hermes.declare import hook
from . import snapshots
from .emits import build_kept
from .rpcs import _snapshots_dir

logger = host.logger


def build_succeeded(result, status=None) -> bool:
    """Whether a delivered ``chromatic_rom_build`` result is a successful build: no error from Hermes or
    the backend, and the engine's own ``structuredContent.success`` is true."""
    if status not in (None, "", "ok"):
        return False
    payload = host.tool_result_payload(result)
    if not payload or payload.get("error") or payload.get("isError"):
        return False
    structured = payload.get("structuredContent")
    return isinstance(structured, dict) and structured.get("success") is True


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
        payload = host.tool_result_payload(result) or {}
        structured = payload["structuredContent"]
        candidates = [structured.get("projectRoot"), args.get("projectPath")]
        try:
            candidates.append(host._chat_project(str(conversation_id or ""), str(session_id or "")))
        except Exception:
            logger.debug("hermretro: no chat project for the build snapshot", exc_info=True)
        candidates += [structured.get("outputPath"), structured.get("romPath")]
        found = host.library_game_for(candidates)
        if found is None:
            return
        game, root = found
        build_ref = payload.get("buildRef")
        taken = snapshots.take(_snapshots_dir(), game, root, "build", build_ref=build_ref)
        if taken.get("skipped"):
            logger.debug("hermretro: build snapshot of %s skipped: %s", root, taken["skipped"])
        else:
            build_kept(game=game, root=root)
    except Exception:
        logger.debug("hermretro snapshot_after_build failed", exc_info=True)
