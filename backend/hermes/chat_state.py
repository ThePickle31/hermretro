"""Where a studio chat stands, told to it again after a context compaction.

Hermes's compaction summary keeps what the agent did but not reliably where it stands, and it drops the skill pages
the agent was following. So this module keeps, per chat, what its last results said: the project, the last build,
the live emulator session (ROM and frame), its recording, and the skill pages loaded with ``skill_view``.

- ``engine_result``: the engine tool handler (``host.make_tool_handler``) folds each engine result in and, after a
  compaction, gets the note that result carries as ``hermretroContext``. The note rides in hermretro's own result, so
  it is there whatever the hook order, with images too, and no other plugin's result is touched.
- ``observe`` (``post_tool_call``): the skill pages loaded with ``skill_view``.
- ``compacted`` (``post_compaction``): the chat's next engine result carries the note (Hermes has no hook that adds
  context mid-turn, and ``pre_llm_call`` runs once per user turn, while a studio chat compacts inside its tool loop).
- ``child_started`` and ``child_stopped`` (``subagent_start``, ``subagent_stop``): a delegated subagent reports its
  parent's ``conversation_id``, so it gets a state of its own, keyed by its session id, and never reads, adds to or
  marks its parent's.

The state is this process's memory: the hooks and the tool handlers run in the process that loaded the plugin. A
chat is keyed by its compression-stable ``conversation_id`` when Hermes gives one, else by its session id; a
compaction that moves the chat to a new session id carries the key along.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Callable

logger = logging.getLogger(__name__)

SKILL_VIEW = "skill_view"
# A compaction that only shortened old tool results leaves the chat's own summary of where it stands intact.
PRUNE_ONLY = "prune_tool_results"
# Engine tools whose result is the whole live session (worker ``state``): its ROM, frame and recording, if any.
SESSION_RESULTS = frozenset({"emulator_run", "emulator_status"})
MAX_CHATS = 64
MAX_SKILL_PAGES = 12
SHA_SHOWN = 12

_lock = threading.Lock()
_chats: OrderedDict[str, dict] = OrderedDict()  # chat key -> state
_keys: dict[str, str] = {}  # session id -> chat key


def _key(session_id: str | None, conversation_id: str | None = None) -> str | None:
    """The chat's key for these ids (made when new), or None without an id. Caller holds the lock."""
    if session_id and session_id in _keys:
        return _keys[session_id]
    key = conversation_id or session_id
    if not key:
        return None
    if session_id:
        _keys[session_id] = key
    return key


def _state(key: str) -> dict:
    """The chat's state, made when new; the oldest chat is forgotten past MAX_CHATS. Caller holds the lock."""
    state = _chats.pop(key, None) or {"skills": []}
    _chats[key] = state
    while len(_chats) > MAX_CHATS:
        _forget(next(iter(_chats)))
    return state


def _forget(key: str) -> None:
    """Drop a chat's state and every session id that leads to it. Caller holds the lock."""
    _chats.pop(key, None)
    for session in [session for session, chat in _keys.items() if chat == key]:
        del _keys[session]


def child_started(child_session_id=None, **_kwargs):
    """``subagent_start``: the delegated subagent's own state, never its parent's conversation's."""
    if child_session_id:
        with _lock:
            _keys[str(child_session_id)] = str(child_session_id)


def child_stopped(child_session_id=None, **_kwargs):
    """``subagent_stop``: the subagent's state goes with it."""
    if child_session_id:
        with _lock:
            _forget(_keys.get(str(child_session_id), str(child_session_id)))


def observe(tool_name=None, args=None, status=None, session_id=None, conversation_id=None, **_kwargs):
    """``post_tool_call``: remember a skill page a successful ``skill_view`` loaded. Never raises."""
    try:
        if tool_name != SKILL_VIEW or status not in (None, "", "ok"):
            return
        page = _skill_page(args if isinstance(args, dict) else {})
        if page:
            with _lock:
                key = _key(session_id, conversation_id)
                if key:
                    _remember_page(_state(key), page)
    except Exception:
        logger.debug("hermretro chat_state.observe failed", exc_info=True)


def _skill_page(args: dict) -> str | None:
    name = args.get("name")
    if not isinstance(name, str) or not name:
        return None
    page = args.get("file_path")
    return f"{name} {page}" if isinstance(page, str) and page else name


def _remember_page(state: dict, page: str) -> None:
    pages = [seen for seen in state["skills"] if seen != page] + [page]
    state["skills"] = pages[-MAX_SKILL_PAGES:]


def compacted(session_id=None, old_session_id=None, kind=None, **_kwargs):
    """``post_compaction``: the chat's next engine result carries where it stands. Never raises."""
    try:
        if kind == PRUNE_ONLY or not session_id:
            return
        with _lock:
            key = _keys.get(old_session_id or "") or _key(session_id)
            _keys[session_id] = key
            _state(key)["due"] = True
    except Exception:
        logger.debug("hermretro chat_state.compacted failed", exc_info=True)


def engine_result(
    tool: str,
    args: dict,
    response: dict,
    *,
    session_id: str,
    conversation_id: str,
    project: Callable[[], str | None],
) -> str | None:
    """Fold an engine tool's broker response into the chat's state (``tool`` is the engine's name, without
    ``chromatic_``). After a compaction, answer the note this result carries, built after this result was taken in;
    None otherwise. The note stays due until a result that reached the engine carries it. ``project`` answers the
    chat's project as hermretro knows it now. Never raises."""
    try:
        with _lock:
            key = _key(session_id, conversation_id)
            if key is None:
                return None
            state = _state(key)
            result = response.get("result") if response.get("ok") else None
            structured = result.get("structuredContent") if isinstance(result, dict) else None
            if isinstance(structured, dict) and not result.get("isError"):
                _take(state, tool, args if isinstance(args, dict) else {}, structured)
            if not state.get("due") or not isinstance(result, dict):
                return None
            state["due"] = False
            known = {name: value for name, value in state.items() if name != "due"}
        try:
            current = project()
        except Exception:
            current = None
        note = note_for(known, current)
        if note is None:
            with _lock:
                state["due"] = True
        return note
    except Exception:
        logger.debug("hermretro chat_state.engine_result failed", exc_info=True)
        return None


def _take(state: dict, tool: str, args: dict, structured: dict) -> None:
    """Fold one successful engine result into the chat's state, by tool and action: only a result that describes
    the live session changes what the note says about it."""
    if isinstance(structured.get("projectRoot"), str):
        state["project"] = structured["projectRoot"]
    if tool == "rom_build":
        rom = structured.get("rom")
        if structured.get("success") is True and isinstance(rom, dict):
            state["build"] = {"path": rom.get("path") or structured.get("outputPath"), "sha256": rom.get("sha256")}
    elif tool in SESSION_RESULTS or (tool == "emulator_checkpoint" and args.get("action") == "restore"):
        # A fresh boot without a recording, or a session that has none, clears the one known before.
        _session(state, structured.get("romPath"), structured)
        _live_recording(state, _recording(structured.get("recording")))
    elif tool == "emulator_replay":
        # A replay boots the ROM it was given; its result names that ROM's hash but not its path. Its recording is
        # live unless finishRecording stopped it in the same call (then the result gives its status).
        _session(state, args.get("romPath"), structured)
        recording = structured.get("recording")
        _live_recording(
            state,
            _recording(recording, None if isinstance(recording, dict) and recording.get("status") else "recording"),
        )
    elif tool in ("emulator_step", "emulator_observe"):
        if _frame(structured) is not None:
            state.setdefault("emulator", {})["frame"] = _frame(structured)
        if tool == "emulator_step" and isinstance(structured.get("recordingSpan"), dict):
            _live_recording(state, _recording(structured["recordingSpan"], "recording"))
    elif tool == "emulator_recording":
        recording = _recording(structured)
        live = state.get("recording") or {}
        if args.get("action") == "stop" and recording is not None:
            state["recording"] = recording
        elif recording is not None and recording["id"] == live.get("id"):
            # status or export of the live attempt; one about an older attempt changes nothing.
            state["recording"] = {**live, **recording}
    elif tool == "emulator_close":
        state.pop("emulator", None)
        live = state.get("recording")
        if live and live.get("status") == "recording":
            # Closing finishes the attempt as stopped; its path and branch still resume it with a replay.
            live["status"] = "stopped"


def _frame(structured: dict) -> int | None:
    frame = structured.get("frame")
    return frame if isinstance(frame, int) and not isinstance(frame, bool) else None


def _session(state: dict, rom, structured: dict) -> None:
    """The live emulator session, as a result that started or describes one says."""
    state["emulator"] = {
        name: value
        for name, value in (
            ("rom", rom if isinstance(rom, str) and rom else None),
            ("sha256", structured.get("romSha256")),
            ("frame", _frame(structured)),
        )
        if value is not None
    }


def _recording(block, status: str | None = None) -> dict | None:
    """A recording as the note names it: path, session id, branch and status; None when ``block`` is not one."""
    if not isinstance(block, dict) or not isinstance(block.get("sessionId"), str):
        return None
    status = status or block.get("status")
    recording = {
        "path": block.get("recordingPath"),
        "id": block["sessionId"],
        "branch": block.get("branchId"),
        "status": status,
    }
    return {name: value for name, value in recording.items() if isinstance(value, str) and value}


def _live_recording(state: dict, recording: dict | None) -> None:
    if recording is None:
        state.pop("recording", None)
    else:
        state["recording"] = recording


def note_for(state: dict, project: str | None = None) -> str | None:
    """The note for a chat's state (``project``: the chat's project as hermretro knows it now), or None when
    nothing is known."""
    parts = []
    project = project or state.get("project")
    if project:
        parts.append(f"Project: {project}.")
    build = state.get("build") or {}
    if build.get("path"):
        parts.append(f"Last build: {build['path']}{_sha(build.get('sha256'))}.")
    emulator = state.get("emulator")
    if emulator is not None:
        where = f"Emulator: frame {emulator['frame']}" if "frame" in emulator else "Emulator: running"
        if emulator.get("rom") or emulator.get("sha256"):
            where += f" of {emulator.get('rom') or 'a ROM'}{_sha(emulator.get('sha256'))}"
            if build.get("sha256") and emulator.get("sha256") and build["sha256"] != emulator["sha256"]:
                where += ", not the last build"
        parts.append(where + ".")
    recording = state.get("recording") or {}
    if recording.get("id"):
        details = [f"session {recording['id']}"] + [
            recording[name] for name in ("branch", "status") if name in recording
        ]
        parts.append(f"Recording: {recording.get('path') or 'path unknown'} ({', '.join(details)}).")
    if state.get("skills"):
        parts.append(
            "Skill pages you had loaded: " + ", ".join(state["skills"]) + ". Load again with skill_view only the "
            "ones your next step needs."
        )
    if not parts:
        return None
    return "The context was just compacted. Where this chat stands, from its last tool results: " + " ".join(parts)


def _sha(sha256) -> str:
    return f" (sha256 {sha256[:SHA_SHOWN]}…)" if isinstance(sha256, str) and sha256 else ""


def reset() -> None:
    """Forget every chat (tests)."""
    with _lock:
        _chats.clear()
        _keys.clear()
