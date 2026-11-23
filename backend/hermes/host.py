"""The helpers every feature's Hermes side shares, and the engine tool handler.

Shared helpers (the data folder, the profile, the library registry, the chat's project, the broker client,
subagent tracking, and for a post_tool_call hook an engine tool's result payload and its library game) live here; feature modules call them as ``host.<name>`` at call time, so one
``mock.patch.object(host, ...)`` reaches every module. The approval hook is declared in hooks.py, the engine
tools in tools.py, the prompt section and skills in prompt.py. Each feature declares its own RPCs, tools and
hooks in its folder (backend/hermes/declare.py).

Handlers run wherever Hermes dispatches tools (gateway, plugin host or an isolated
turn process). They hold no state of their own: every call goes to the broker.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from .. import library
from ..system import paths
from . import api as hermes_api, contracts, results

# try_connect is used by the feature modules as host.try_connect, so a test's patch here reaches them.
from ..broker import BrokerUnavailable, OtherCopyBusy, ensure_broker, try_connect  # noqa: F401 - used as host.try_connect (above)

logger = logging.getLogger(__name__)

_APPROVAL_TOOLS = {"chromatic_flash", "chromatic_play", "chromatic_setup"}

# Runtime session ids of delegated subagents alive in this process. The subagent_start hook and
# the child's tool calls run in the same process, so this is host-observed, not model-supplied.
_child_sessions: dict[str, float] = {}
_child_lock = threading.Lock()


def _data_dir() -> Path:
    return hermes_api.plugin_data_dir(paths.PLUGIN_ID)


def _profile_identity() -> str:
    """Canonical identity of the active Hermes profile: its plugin data directory."""
    return str(_data_dir().resolve())


def _attach_images() -> bool:
    """Whether the active model route takes images inside tool results.

    Hermes has no public helper for this yet; core tools share this private gate. Any failure
    means "do not attach", and the saved files still carry the images."""
    return hermes_api.tool_results_take_images()


def _is_child(session_id: str) -> bool:
    with _child_lock:
        return bool(session_id) and session_id in _child_sessions


def on_subagent_start(child_session_id=None, **_kwargs):
    if child_session_id:
        with _child_lock:
            _child_sessions[str(child_session_id)] = time.time()
            for stale in sorted(_child_sessions, key=lambda key: _child_sessions[key])[:-512]:
                del _child_sessions[stale]


def on_subagent_stop(child_session_id=None, **_kwargs):
    if child_session_id:
        with _child_lock:
            _child_sessions.pop(str(child_session_id), None)


def _deliver(response: dict, name: str):
    """Shape a broker response for the model. By now the tool has already run, so a failure here
    (for example the frames folder cannot be written) must not read as "the tool did not run"."""
    try:
        return results.encode(response, name, _data_dir() / "frames", _attach_images())
    except Exception as error:
        logger.exception("Chromatic tool %s ran but its result could not be fully delivered", name)
        problem = f"{type(error).__name__}: {error}"
    try:
        plain = results.encode(response, name, None, False)  # the same result, without saving images
        payload = json.loads(plain) if isinstance(plain, str) else None
        if isinstance(payload, dict):
            payload["deliveryProblem"] = (
                "The tool ran. Its images could not be saved or attached "
                f"({problem}); the rest of the result is complete."
            )
            return json.dumps(payload)
        return plain
    except Exception:
        logger.exception("Chromatic tool %s: plain delivery failed too", name)
        if response.get("denied") or not (response.get("ok") or response.get("dispatched")):
            return json.dumps(
                {
                    "error": f"hermretro could not report why this call did not run ({problem}).",
                    "code": "ADAPTER_ERROR",
                    "dispatched": False,
                    "nextStep": results.ADAPTER_ERROR_NEXT_STEP,
                }
            )
        return json.dumps(
            {
                "error": f"The tool ran, but hermretro could not deliver its result ({problem}).",
                "code": "RESULT_NOT_DELIVERED",
                "dispatched": True,
                "nextStep": "The operation was sent to the engine. Inspect current state before deciding what to "
                "do; do not simply repeat it.",
            }
        )


# How many numbered folders a new game tries when other chats keep taking the free one.
NAME_ATTEMPTS = 5


def _destination_taken(response: dict) -> bool:
    result = response.get("result") if response.get("ok") else None
    structured = (result or {}).get("structuredContent")
    return bool(result and result.get("isError") and isinstance(structured, dict)) and (
        structured.get("code") == "PROJECT_ALREADY_EXISTS"
    )


_STAY_IN_TOOLS = (
    "Do not build, play or edit the game outside the chromatic tools while they are unavailable, and do not "
    "save a workaround as a skill."
)


def _other_copy_busy(error: OtherCopyBusy, conversation_id: str, session_id: str) -> dict:
    """The answer when another copy of the plugin's broker still runs games: whether one of them is this very
    chat's (hermretro's folder changed while the chat was working), only other chats', or, when that copy cannot
    be asked (an older version), unknown."""
    own = None
    ids = [value for value in (conversation_id, session_id) if value]
    client, _ = try_connect(paths.runtime_dir()) if ids else (None, None)
    if client is not None:
        with client:
            try:
                answer = client.request({"op": "activity", "profile": _profile_identity(), "ids": ids, "limit": 1})
            except (BrokerUnavailable, ValueError):
                answer = {}
        if answer.get("ok"):
            own = answer.get("matched") == "chat" and bool((answer.get("lane") or {}).get("alive"))
    where = f" ({error.plugin_root})" if error.plugin_root else ""
    if own:
        message = (
            f"This chat's game is still open in another copy of hermretro{where}: hermretro's plugin folder changed "
            "while this chat was working, and that copy keeps the chat's game until it has been idle for a while "
            "(longer while its player is open). Nothing was run."
        )
        next_step = "Tell the user the game tools are paused for that reason, and stop. " + _STAY_IN_TOOLS
    elif own is False:
        message = str(error) + " Nothing was run."
        next_step = (
            "Tell the user another copy of hermretro is running games in other chats, and try again once those "
            "chats are finished (it stops by itself when they are idle). " + _STAY_IN_TOOLS
        )
    else:
        message = (
            str(error) + " One of those may be this chat's own game, if hermretro's plugin folder changed while it "
            "was working. Nothing was run."
        )
        next_step = (
            "Tell the user the game tools are paused until that copy of hermretro has finished its games (it stops "
            "by itself when they are idle), and stop. " + _STAY_IN_TOOLS
        )
    return {"error": message, "code": "UNAVAILABLE", "dispatched": False, "nextStep": next_step}


def make_tool_handler(ctx, tool: dict):
    original = tool["name"]
    name = contracts.hermes_name(original)

    def handler(args: dict, **kwargs) -> object:
        try:
            conversation_id = str(kwargs.get("conversation_id") or "")
            session_id = str(kwargs.get("session_id") or "")
            owner = {"profile": _profile_identity(), "conversation_id": conversation_id} if conversation_id else None
            origin = {
                "session_id": session_id,
                "task_id": str(kwargs.get("task_id") or ""),
                "delegated": _is_child(session_id),
            }
            policy = {
                "hardware_enabled": bool(ctx.get_config("hardware_enabled", False)),
                "live_player": bool(ctx.get_config("live_player", True)),
            }
            args = args if isinstance(args, dict) else {}
            # New games live in the Studio's games folder unless the user asked for another place.
            automatic = original in contracts.CREATORS and not args.get("destinationPath")
            with ensure_broker() as client:
                for _attempt in range(NAME_ATTEMPTS):
                    if automatic:
                        paths.games_dir(create=True)
                        args = {**args, "destinationPath": contracts.default_destination(args.get("name"))}
                    response = client.call(owner, original, args, origin=origin, policy=policy)
                    # Two chats making games of the same name can both pick the same free folder; the
                    # engine refuses the second, which then takes the next free number.
                    if not (automatic and _destination_taken(response)):
                        break
            if conversation_id and session_id and session_id != conversation_id and not origin["delegated"]:
                try:  # a game's conversation keeps its game when compression rotates the session id
                    _registry().note_alias(_profile_identity(), conversation_id, session_id)
                except Exception:
                    logger.debug("hermretro: could not record the session alias", exc_info=True)
            return _deliver(response, name)
        except OtherCopyBusy as error:
            return json.dumps(_other_copy_busy(error, conversation_id, session_id))
        except BrokerUnavailable as error:
            return json.dumps(
                {
                    "error": str(error),
                    "code": "UNAVAILABLE",
                    "dispatched": False,
                    "nextStep": "Load the skill hermretro:setup for how to prepare this machine. " + _STAY_IN_TOOLS,
                }
            )
        except Exception as error:  # a handler must never raise
            logger.exception("Chromatic tool %s failed in the host adapter", name)
            return json.dumps(
                {
                    "error": f"hermretro adapter error: {type(error).__name__}: {error}",
                    "code": "ADAPTER_ERROR",
                    "nextStep": results.ADAPTER_ERROR_NEXT_STEP,
                }
            )

    return handler


# -- the games library, shared by the RPC and tool modules ---------------------------


def _registry() -> library.Registry:
    return library.Registry(paths.library_dir())


def _game_root(identifier) -> Path | None:
    entry = _registry().get(identifier) if library.valid_id(identifier) else None
    root = Path(entry["projectRoot"]) if entry else None
    return root if root is not None and root.is_dir() else None


def _chat_binding(conversation_id: str, session_id: str) -> tuple[str | None, dict | None]:
    """What this chat is on the Build page: ``("game", entry)``, ``("pending", record)`` (a New Game conversation
    whose project does not exist yet) or ``(None, None)``."""
    ids = [value for value in (conversation_id, session_id) if value]
    return _registry().binding_for(_profile_identity(), ids) if ids else (None, None)


def _bound_game(conversation_id: str, session_id: str) -> dict | None:
    """The library entry of the game whose Build conversation this chat is, or None (not a game's chat)."""
    kind, entry = _chat_binding(conversation_id, session_id)
    return entry if kind == "game" and isinstance(entry, dict) else None


def _chat_project(conversation_id: str, session_id: str) -> str | None:
    """The project this chat works on: the game whose Build conversation it is, else its broker lane's
    selection (memory only, never starts the broker or a worker), else the library game whose chat link is
    this conversation. A game's own chat always answers its game, so no other game can stand in for it."""
    ids = [value for value in (conversation_id, session_id) if value]
    if not ids:
        return None
    bound = _bound_game(conversation_id, session_id)
    if bound is not None and isinstance(bound.get("projectRoot"), str):
        return bound["projectRoot"]
    client, _error = try_connect(paths.runtime_dir())
    if client is not None:
        with client:
            answer = client.request({"op": "activity", "profile": _profile_identity(), "ids": ids, "limit": 1})
        root = (
            (answer.get("lane") or {}).get("project_root")
            if answer.get("ok") and answer.get("matched") == "chat"
            else None
        )
        if isinstance(root, str) and root:
            return root
    here = _profile_identity()
    linked = [
        entry
        for entry in _registry().load()["games"].values()
        if isinstance(entry, dict)
        and isinstance(entry.get("chat"), dict)
        and entry["chat"].get("profile") in (None, here)
        and (entry["chat"].get("conversationId") in ids or entry["chat"].get("sessionId") in ids)
    ]
    linked.sort(key=lambda entry: -(entry.get("updatedAt") or 0))
    return linked[0]["projectRoot"] if linked and isinstance(linked[0].get("projectRoot"), str) else None


# -- what a post_tool_call hook reads: an engine tool's result and the library game it touched ---------


def tool_result_payload(result) -> dict | None:
    """A tool result as the model saw it, as a dict: the JSON text parsed, or the multimodal envelope's text
    summary parsed; None when it is neither (a hook gets ``result`` exactly as Hermes delivered it)."""
    if isinstance(result, dict) and result.get("_multimodal"):
        result = result.get("text_summary")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return None
    return result if isinstance(result, dict) else None


def library_game_for(candidates) -> tuple[str, Path] | None:
    """``(game id, real project root)`` of the library game whose project is, or most closely contains, the first of
    ``candidates`` that is in one (paths from the result, the arguments, the chat; non-strings are skipped), or None.
    The deepest root wins, so a project inside another game's folder is never taken for that game."""
    roots = []
    for entry in _registry().load()["games"].values():
        if isinstance(entry, dict) and isinstance(entry.get("projectRoot"), str):
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
        holding = [root for root in roots if (real == root or root in real.parents) and root.is_dir()]
        if holding:
            root = max(holding, key=lambda path: len(path.parts))
            return library.game_id(root), root
    return None


# How a game is made, in order: the one statement the prompt section and the Build-page context share (SOUL.md
# says the same in its own words).
GAME_STEPS = (
    "Make a game in this order: agree what to make with the user (a few quick questions, then a short list of what "
    "you will make that they change until they approve it; or with hermretro:game-planning a brief, kept in the new "
    "project, that they approve); create the project; author everything agreed with the chromatic_* tools, building "
    "with chromatic_rom_build as you go (a build is a checkpoint, not a hand-off); once all of it is in, "
    + results.DELIVER
)
# What keeps the game the user's real, buildable project.
GAME_RULES = (
    "Change the game only through the chromatic_* tools: draw art as PNG files and bring it in with "
    "chromatic_asset_import, but never write .gbsres or .gbsproj files or anything under build/ yourself, and never "
    "build, export or playtest the game with other programs. When no tool can do what the game needs, tell the "
    "user what is missing. Do not create or change skills unless the user asks."
)

# The build card's guidance, for the Build conversation's context and the prompt section.
BUILD_REPORT_GUIDANCE = (
    "At the end of a turn that changed or built the game (after building, your own playtest and presenting), "
    "call chromatic_build_report once (title, summary, changes with asset paths, tested/untested, notes, up to 4 "
    "suggestions), then keep the written reply to one or two short sentences."
)


# -- hooks -------------------------------------------------------------------------


def make_pre_tool_call(ctx):
    def pre_tool_call(tool_name=None, args=None, **_kwargs):
        """Send every hardware-changing call through Hermes's own human-approval gate. Denial, timeout or
        nobody to ask all leave the tool unrun. (The vendor download's approval is setup's: setup/hooks.py.)"""
        if tool_name not in _APPROVAL_TOOLS or not ctx.get_config("hardware_enabled", False):
            return None  # disabled hardware is refused by the broker; nothing to approve
        args = args or {}
        if tool_name == "chromatic_flash":
            message = (
                "Write a ROM to the cartridge in the connected Chromatic. Existing cartridge game data is "
                f"erased, saves may be lost and no backup is made. ROM: {args.get('romPath')} "
                f"({args.get('expectedSizeBytes')} bytes, SHA-256 {args.get('expectedSha256')})."
            )
        elif tool_name == "chromatic_play":
            message = (
                "Stream a host-emulated demo to the connected Chromatic. This loads a streaming image into "
                f"the device; it does not write the cartridge. ROM: {args.get('romPath')}."
            )
        else:
            message = (
                "Chromatic device setup: " + str(args.get("command")) + ". Installing drivers changes "
                "system USB access; cartridge detection reconfigures the device."
            )
        # A unique rule key per request, so one approval can never cover a later or different operation.
        detail = json.dumps(
            [args.get(key) for key in ("requestId", "command", "romPath", "expectedSizeBytes", "expectedSha256")],
            default=str,
        )  # unambiguous: a path may itself contain a separator
        return {"action": "approve", "message": message, "rule_key": f"hermretro:{tool_name}:{detail}"}

    return pre_tool_call


SYSTEM_PROMPT_SECTION = (
    "hermretro is installed: tools named chromatic_* build real Game Boy / Game Boy Color games "
    "(native GB Studio projects) for the ModRetro Chromatic. For any work on such a game, first load the matching "
    "skill with skill_view: "
    "hermretro:setup (any setup or repair), hermretro:game-planning, hermretro:authoring, "
    "hermretro:pixel-art, hermretro:rom-debugging (build and emulator testing), "
    "hermretro:deployment (physical Chromatic). Call chromatic_* tools directly, never from execute_code. "
    "One conversation works on one project folder; use a new chat for a different project. "
    "New games go in the hermretro games folder: leave out destinationPath unless the user names another "
    "folder. " + GAME_STEPS + " "
    "Nothing opens for the user after a build; chromatic_present_game shows the game in the hermretro emulator. "
    "After chromatic_build_report, keep the written reply to one or two short sentences. "
    + GAME_RULES
    + " Hardware tools stay off until the user enables them in Settings > Plugins > hermretro."
)
