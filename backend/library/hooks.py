"""The library's Hermes hooks: a game's Build conversation is told which game it works on (``pre_llm_call``,
ephemeral context every turn), and Hermes's file tools write into a library game's folder only from that game's own
conversation and never into its ``.hermretro/`` (``pre_tool_call``). A terminal command is not parsed, so a shell
command can still write there: this guards the file tools, not the shell."""

from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path

from ..hermes import host, workflow
from ..hermes.declare import hook
from . import layout

# Hermes's own file-writing tools (a terminal command is not parsed), and a V4A patch's file headers.
FILE_WRITE_TOOLS = frozenset({"write_file", "patch"})
PATCH_TARGET = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", re.M)


def _targets(args: dict) -> list[str]:
    """The files a ``write_file`` or ``patch`` call would write: its ``path``, and a V4A patch's file headers."""
    found = [args["path"]] if isinstance(args.get("path"), str) else []
    if isinstance(args.get("patch"), str):
        found += [match.strip() for match in PATCH_TARGET.findall(args["patch"])]
    return found


def _resolved(target: str, base: str | None = None) -> Path | None:
    try:
        path = os.path.expanduser(target)
        return Path(os.path.realpath(os.path.join(base, path) if base and not os.path.isabs(path) else path))
    except (TypeError, ValueError, OSError):
        return None


def _candidates(target: str) -> list[Path]:
    """Where a file tool may write ``target``. A relative path is read against the configured terminal folder and this
    process's folder: Hermes resolves it against the chat's own working folder, which a hook cannot see."""
    if os.path.isabs(os.path.expanduser(target)):
        bases = [None]
    else:
        configured = os.environ.get("TERMINAL_CWD")
        bases = [configured if configured and os.path.isabs(configured) else None, None]
    return [path for path in (_resolved(target, base) for base in bases) if path is not None]


def _in_game_record(resolved: Path) -> bool:
    """Whether ``resolved`` is in a ``.hermretro/`` folder (letter case aside)."""
    return any(part.lower() == layout.STATE_DIR for part in resolved.parts)


def _parts(path: Path) -> tuple[str, ...]:
    """A real path's parts, compared without letter case on macOS (its file systems ignore it)."""
    return tuple(part.lower() for part in path.parts) if sys.platform == "darwin" else path.parts


def _owning_game(resolved: Path) -> tuple[dict, Path] | None:
    """The library game whose folder is or holds ``resolved``: the deepest one, so a project inside another game's
    folder is never taken for that game."""
    wanted = _parts(resolved)
    best = None
    for entry in host._registry().load()["games"].values():
        if not isinstance(entry, dict) or not isinstance(entry.get("projectRoot"), str):
            continue
        root = _resolved(entry["projectRoot"])
        if root is None or not root.is_dir():
            continue
        parts = _parts(root)
        if wanted[: len(parts)] == parts and (best is None or len(parts) > len(_parts(best[1]))):
            best = (entry, root)
    return best


def _other_game(resolved: Path, conversation_id: str, session_id: str) -> str | None:
    """The refusal when ``resolved`` is in a library game's folder and this chat is not that game's conversation."""
    found = _owning_game(resolved)
    if found is None:
        return None
    entry, root = found
    kind, bound = host._chat_binding(conversation_id, session_id)
    own = bound.get("projectRoot") if kind == "game" and isinstance(bound, dict) else None
    mine = _resolved(own) if isinstance(own, str) and own else None
    if mine is not None and _parts(mine) == _parts(root):
        return None
    title = entry.get("title") or root.name
    if kind == "game":
        mine = bound.get("title") or Path(str(bound.get("projectRoot") or "")).name
        return (
            f"{resolved} is in the game \"{title}\" ({root}), and this conversation belongs to \"{mine}\": each game's "
            "files are written only from its own conversation. Write this game's files only. Nothing was changed."
        )
    return (
        f"{resolved} is in the hermretro game \"{title}\" ({root}), whose files are written only from its own "
        f"conversation. Tell the user to open \"{title}\" on the hermretro Build page and continue there. Nothing was "
        "changed."
    )


@hook("pre_tool_call")
def guard_game_record(tool_name=None, args=None, conversation_id=None, session_id=None, **_kwargs):
    """``pre_tool_call``: refuse a file-tool write into a game's ``.hermretro/`` (its id and publish record), and one
    into a library game's folder from any chat but that game's own conversation."""
    if tool_name not in FILE_WRITE_TOOLS or not isinstance(args, dict):
        return None
    resolved = [path for target in _targets(args) for path in _candidates(target)]
    if any(_in_game_record(path) for path in resolved):
        return {
            "action": "block",
            "message": f"{layout.STATE_DIR}/ is hermretro's record of the game (its id and publish record); it "
            "cannot be edited. Leave it as it is.",
        }
    for path in resolved:
        try:
            refusal = _other_game(path, str(conversation_id or ""), str(session_id or ""))
        except Exception:
            continue  # an unreadable library never blocks a write outside any game
        if refusal:
            return {"action": "block", "message": refusal}
    return None


@hook("pre_llm_call")
def build_context(session_id=None, is_first_turn=False, **_kwargs):
    """``pre_llm_call``: tell a game's Build conversation which game it is (ephemeral, per turn)."""
    if not isinstance(session_id, str) or not session_id:
        return None
    try:
        kind, bound = host._registry().binding_for(host._profile_identity(), [session_id])
    except Exception:
        return None
    if kind == "game":
        root = bound.get("projectRoot")
        title = bound.get("title") or Path(root or "").name
        guidance = _game_guidance(bound, root, is_first_turn)
        return {
            "context": (
                f"[hermretro] This is the Build conversation of the game \"{title}\" "
                f"({bound.get('projectRoot')}). The game is selected for you on the first chromatic "
                "call. This conversation works on this one game: do not create or open other "
                "projects here; for another game the user uses New Game or picks it on the "
                "hermretro Build page. "
                + workflow.SHOW_ART_CONTEXT
                + " "
                + guidance
                + " "
                + workflow.BUILD_REPORT_GUIDANCE
                + " "
                + workflow.GAME_RULES
            )
        }
    if kind == "pending":
        name = bound.get("name")
        called = f" called \"{name}\"" if name else ""
        if is_first_turn:
            start = "; their message is the idea. " + (
                workflow.PLAN_START if bound.get("plan") else workflow.BUILD_START
            )
        else:
            start = ". " + (workflow.PLAN_CONTINUE if bound.get("plan") else workflow.BUILD_CONTINUE)
        return {
            "context": (
                f"[hermretro] The user started a new Game Boy Color game{called} with New Game on the "
                "hermretro Build page" + start + " Create exactly one new "
                "project (chromatic_project_create or chromatic_project_create_blank): it becomes this "
                "conversation's game. " + workflow.GAME_RULES
            )
        }
    return None


def _game_guidance(game: dict, root: str | None, first: bool) -> str:
    presented = game.get("presented")
    if isinstance(presented, dict) and isinstance(presented.get("t"), (int, float)):
        return workflow.EDIT_GAME

    session = game.get("session")
    session = session if isinstance(session, dict) else {}
    plan = game.get("initialPlan", session.get("plan"))
    if plan is True:
        return workflow.PLAN_BOUND
    if plan is False:
        return workflow.BUILD_BOUND
    if session.get("edit") is True or first or not root:
        return workflow.EDIT_GAME

    # A legacy New Game bound the chat before writing its plans or making its first build.
    # Earlier plans or activity belong to an existing game, even if later turns updated its notes.
    bound_at = session.get("createdAt")
    activity = (game.get(key) for key in ("lastBuild", "lastWebExport"))
    if isinstance(bound_at, (int, float)) and not any(
        isinstance(record, dict) and isinstance(record.get("t"), (int, float)) and record["t"] < bound_at
        for record in activity
    ):
        docs = Path(root, "docs", "game")
        for name, guidance in (("GAME-BRIEF.md", workflow.PLAN_BOUND), ("FIRST-BUILD.md", workflow.BUILD_BOUND)):
            try:
                info = (docs / name).stat(follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode) and info.st_mtime >= bound_at:
                return guidance
    return workflow.EDIT_GAME
