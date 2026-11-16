"""Everything that touches Hermes: tool handlers, hooks, the prompt section, and the helpers shared by
the RPC and tool modules.

The page's RPCs and the plugin-owned tools live in host_setup, host_tools, host_games and host_assets;
this module re-exports their names (``hermes_host.rpc_status`` and so on), and those modules look the
shared helpers up here at call time.

Handlers run wherever Hermes dispatches tools (gateway, plugin host or an isolated
turn process). They hold no state of their own: every call goes to the broker.
"""
from __future__ import annotations

import importlib
import json
import logging
import threading
import time
from pathlib import Path

from . import contracts, hermes_api, paths, provision, results
from . import games as library
# try_connect is used by the area modules as hermes_host.try_connect, so a test's patch here reaches them.
from .client import BrokerUnavailable, ensure_broker, try_connect  # noqa: F401

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


def _deliver(response: dict, name: str, encode=results.encode):
    """Shape a broker response for the model. By now the tool has already run, so a failure here
    (for example the frames folder cannot be written) must not read as "the tool did not run"."""
    try:
        return encode(response, name, _data_dir() / "frames", _attach_images())
    except Exception as error:
        logger.exception("Chromatic tool %s ran but its result could not be fully delivered", name)
        problem = f"{type(error).__name__}: {error}"
    try:
        plain = encode(response, name, None, False)       # the same result, without saving images
        payload = json.loads(plain) if isinstance(plain, str) else None
        if isinstance(payload, dict):
            payload["deliveryProblem"] = ("The tool ran. Its images could not be saved or attached "
                                          f"({problem}); the rest of the result is complete.")
            return json.dumps(payload)
        return plain
    except Exception:
        logger.exception("Chromatic tool %s: plain delivery failed too", name)
        if response.get("denied") or not (response.get("ok") or response.get("dispatched")):
            return json.dumps({"error": f"hermretro could not report why this call did not run ({problem}).",
                               "code": "ADAPTER_ERROR", "dispatched": False})
        return json.dumps({
            "error": f"The tool ran, but hermretro could not deliver its result ({problem}).",
            "code": "RESULT_NOT_DELIVERED", "dispatched": True,
            "guidance": "The operation was sent to the engine. Inspect current state before deciding what to "
                        "do; do not simply repeat it."})


def make_tool_handler(ctx, tool: dict):
    original = tool["name"]
    name = contracts.hermes_name(original)

    def handler(args: dict, **kwargs) -> object:
        try:
            conversation_id = str(kwargs.get("conversation_id") or "")
            session_id = str(kwargs.get("session_id") or "")
            owner = {"profile": _profile_identity(), "conversation_id": conversation_id} if conversation_id else None
            origin = {"session_id": session_id, "task_id": str(kwargs.get("task_id") or ""),
                      "delegated": _is_child(session_id)}
            policy = {"hardware_enabled": bool(ctx.get_config("hardware_enabled", False)),
                      "live_player": bool(ctx.get_config("live_player", True))}
            if original in contracts.CREATORS and isinstance(args, dict) and not args.get("destinationPath"):
                # New games live in the Studio's games folder unless the user asked for another place.
                paths.games_dir(create=True)
                args = {**args, "destinationPath": contracts.default_destination(args.get("name"))}
            with ensure_broker() as client:
                response = client.call(owner, original, args if isinstance(args, dict) else {},
                                       origin=origin, policy=policy)
            if conversation_id and session_id and session_id != conversation_id and not origin["delegated"]:
                try:  # a game's conversation keeps its game when compression rotates the session id
                    _registry().note_alias(_profile_identity(), conversation_id, session_id)
                except Exception:
                    logger.debug("hermretro: could not record the session alias", exc_info=True)
            return _deliver(response, name)
        except BrokerUnavailable as error:
            return json.dumps({"error": str(error), "code": "UNAVAILABLE", "dispatched": False,
                               "guidance": "Load the skill hermretro:setup for how to prepare this machine."})
        except Exception as error:  # a handler must never raise
            logger.exception("Chromatic tool %s failed in the host adapter", name)
            return json.dumps({"error": f"hermretro adapter error: {type(error).__name__}: {error}",
                               "code": "ADAPTER_ERROR"})

    return handler


# -- the games library, shared by the RPC and tool modules ---------------------------

def _registry() -> library.Registry:
    return library.Registry(paths.library_dir())


def _game_root(identifier) -> Path | None:
    entry = _registry().get(identifier) if library.valid_id(identifier) else None
    root = Path(entry["projectRoot"]) if entry else None
    return root if root is not None and root.is_dir() else None


# The build card's guidance, for the Build conversation's context and the prompt section.
BUILD_REPORT_GUIDANCE = (
    "At the end of a turn that changed or built the game (after building, your own playtest and presenting), "
    "call chromatic_build_report once (title, summary, changes with asset paths, tested/untested, notes, up to 4 "
    "suggestions), then keep the written reply to one or two short sentences.")


# -- hooks -------------------------------------------------------------------------

def make_pre_tool_call(ctx):
    from .host_tools import DEVICE_CLI_TOOL

    def pre_tool_call(tool_name=None, args=None, **_kwargs):
        """Send every hardware-changing call, and the vendor download, through Hermes's own
        human-approval gate. Denial, timeout or nobody to ask all leave the tool unrun."""
        if tool_name == DEVICE_CLI_TOOL["name"]:
            if not isinstance(args, dict) or args.get("action") != "install":
                return None  # status is passive
            try:
                host = provision.host_target()
                pins = provision._pins(host["target"]) if host["target"] else None
            except Exception:
                pins = None
            if pins is None:
                return None  # nothing can be installed here; the tool explains why
            megabytes = pins["package"]["bytes"] / 1_000_000
            return {"action": "approve",
                    "message": (f"Download ModRetro's Chromatic CLI {pins['version']} ({megabytes:.1f} MB) from "
                                f"{pins['package']['url']} into hermretro's folder in the Hermes home. It is proprietary "
                                f"ModRetro software; approving means you agree to ModRetro's terms "
                                f"({provision.VENDOR_TERMS_URL}). Nothing is sent to a device."),
                    # One key per CLI release: "always" covers a reinstall, never a different version.
                    "rule_key": f"hermretro:device-cli-install:{pins['version']}"}
        if tool_name not in _APPROVAL_TOOLS or not ctx.get_config("hardware_enabled", False):
            return None  # disabled hardware is refused by the broker; nothing to approve
        args = args or {}
        if tool_name == "chromatic_flash":
            message = ("Write a ROM to the cartridge in the connected Chromatic. Existing cartridge game data is "
                       f"erased, saves may be lost and no backup is made. ROM: {args.get('romPath')} "
                       f"({args.get('expectedSizeBytes')} bytes, SHA-256 {args.get('expectedSha256')}).")
        elif tool_name == "chromatic_play":
            message = ("Stream a host-emulated demo to the connected Chromatic. This loads a streaming image into "
                       f"the device; it does not write the cartridge. ROM: {args.get('romPath')}.")
        else:
            message = ("Chromatic device setup: " + str(args.get("command")) + ". Installing drivers changes "
                       "system USB access; cartridge detection reconfigures the device.")
        # A unique rule key per request, so one approval can never cover a later or different operation.
        detail = json.dumps([args.get(key) for key in
                             ("requestId", "command", "romPath", "expectedSizeBytes", "expectedSha256")],
                            default=str)       # unambiguous: a path may itself contain a separator
        return {"action": "approve", "message": message, "rule_key": f"hermretro:{tool_name}:{detail}"}
    return pre_tool_call


SYSTEM_PROMPT_SECTION = (
    "hermretro is installed: tools named chromatic_* build real Game Boy / Game Boy Color games "
    "(native GB Studio projects) for the ModRetro Chromatic. When the user wants to plan, create, edit, build, "
    "playtest or deploy such a game, first load the matching skill with skill_view: "
    "hermretro:setup (install or repair dependencies; load it for any setup request), hermretro:game-planning, hermretro:authoring, "
    "hermretro:pixel-art, hermretro:rom-debugging (build and emulator testing), "
    "hermretro:deployment (physical Chromatic). Call chromatic_* tools directly, never from execute_code. "
    "One conversation works on one project folder; use a new chat for a different project. "
    "New games go in the hermretro games folder: leave destinationPath out of chromatic_project_create "
    "and chromatic_project_create_blank unless the user names another folder. "
    "Build after each meaningful change. Nothing opens for the user after a build: when the game is ready for "
    "the user to try (after your own testing), fill in its game card with chromatic_game_info (pixel-art cover, "
    "title, tagline, description, genres), then call chromatic_present_game, optionally with a short note on what "
    "to try; it shows the game in the hermretro emulator beside the chat. Call it again after later "
    "changes the user should test. " + BUILD_REPORT_GUIDANCE + " "
    "Do not open the game with desktop_preview or reload it with drive_preview. "
    "Only if the user says they cannot see the emulator, open studio.playerUrl from chromatic_present_game with "
    "desktop_preview (action \"open\"); without desktop tools, give the user that url. "
    "Hardware tools stay off until the user enables them in Settings > Plugins > hermretro."
)


# -- names that moved to the area modules ------------------------------------------
# hermes_host.<name> keeps working for __init__.py and the tests. Resolved on first use, so an area module
# can import this one at its top in any import order.
_MOVED = {
    "host_setup": (
        "_COMPONENT_LABELS", "_OPTIONAL_COMPONENTS", "_platform_report", "LOADED_FINGERPRINT",
        "rpc_status", "rpc_install", "rpc_remove_tools", "BROKER_STOP_WAIT", "_REMOVE_BUSY",
        "_broker_lock", "rpc_studio_profile", "rpc_activity", "rpc_doctor",
    ),
    "host_tools": (
        "DEVICE_CLI_TOOL", "device_cli_handler", "PRESENT_TOOL", "_chat_project", "_present_error",
        "_tool_project", "present_game_handler", "GAME_INFO_TOOL", "_CARD_FIELDS", "game_info_handler",
        "REPORT_LIMITS", "REPORT_COUNTS", "REPORT_KINDS", "REPORT_MESSAGE", "_report_list",
        "BUILD_REPORT_TOOL", "_report_text", "_report_asset", "build_report_handler",
    ),
    "host_assets": (
        "ASSET_SUFFIXES", "ASSET_MAX_BYTES", "_image_size", "_asset_kind", "ASSET_KEEP_VERSIONS",
        "_MEDIA_LINE", "_asset_roots", "_asset_file", "_versions_dir", "_keep_version", "_version_at",
        "_keep_paths", "keep_delivered_images", "keep_inspected_images", "rpc_asset",
        "_ANIMATION_NAMES", "_FACING_SLOT", "_ASSET_INFO_SCENES", "_ASSET_INFO_ACTORS", "_read_json",
        "_tiles", "_sprite_animations", "_standing_frame", "_project_index", "_palette",
        "_player_sprite_id", "_actor_palette", "_scene_view", "_SPRITE_USES", "_SPRITE_USES_ROOTS",
        "_MOVING_OFFSET", "_project_stamp", "_sprite_uses", "_sprite_look", "_versions",
        "rpc_asset_info", "rpc_asset_restore", "_ASSET_LIST_FOLDERS", "ASSET_LIST_LIMIT", "_list_root",
        "rpc_assets",
    ),
    "host_games": (
        "_games_dir_made", "_profile_name", "_chat_titles", "_existing_sessions", "_seed_library",
        "_demo_entry", "_capture_root", "rpc_games", "rpc_build", "SHOW_ART_CONTEXT", "build_context",
        "_snapshots_dir", "_result_payload", "build_succeeded", "_library_root_for",
        "snapshot_after_build", "after_tool_call", "rpc_builds", "rpc_build_restore", "rpc_game_thumb",
        "rpc_player", "rpc_presentations", "rpc_captures", "rpc_capture_image",
    ),
}
_HOME = {name: module for module, names in _MOVED.items() for name in names}


def __getattr__(name):
    module = _HOME.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(f".{module}", __package__), name)
