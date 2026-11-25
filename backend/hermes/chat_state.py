"""Where a studio chat stands, told to it again after a context compaction.

Hermes's compaction summary keeps what the agent did but not reliably where it stands, and it drops the skill pages
the agent was following. So ``observe`` (``post_tool_call``) keeps, per chat, what the tool results said last: the
project, the last build, the emulator's ROM and frame, the recording, and the skill pages loaded with ``skill_view``.
``compacted`` (``post_compaction``) marks the chat, and ``deliver`` (``transform_tool_result``) adds one short note to
the next tool result as ``hermretroContext`` (Hermes has no hook that adds context mid-turn, and ``pre_llm_call`` runs
once per user turn, while a studio chat compacts inside its tool loop).

The state is this process's memory: Hermes runs all three hooks in the process that runs the agent loop. A chat is
keyed by its compression-stable ``conversation_id`` when Hermes gives one, else by its session id; a compaction that
moves the chat to a new session id carries the key along.
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict

from . import host

ENGINE_PREFIX = "chromatic_"
SKILL_VIEW = "skill_view"
KEY = "hermretroContext"
# A compaction that only shortened old tool results leaves the chat's own summary of where it stands intact.
PRUNE_ONLY = "prune_tool_results"
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
        forgotten, _old = _chats.popitem(last=False)
        for session in [session for session, chat in _keys.items() if chat == forgotten]:
            del _keys[session]
    return state


def observe(tool_name=None, args=None, result=None, status=None, session_id=None, conversation_id=None, **_kwargs):
    """``post_tool_call``: keep what a successful engine result or ``skill_view`` said about where the chat stands.
    Never raises."""
    try:
        if status not in (None, "", "ok") or not isinstance(tool_name, str):
            return
        args = args if isinstance(args, dict) else {}
        if tool_name == SKILL_VIEW:
            page = _skill_page(args)
            if page:
                with _lock:
                    key = _key(session_id, conversation_id)
                    if key:
                        _remember_page(_state(key), page)
            return
        if not tool_name.startswith(ENGINE_PREFIX):
            return
        payload = host.tool_result_payload(result)
        if not payload or payload.get("error") or payload.get("isError"):
            return
        structured = payload.get("structuredContent")
        if not isinstance(structured, dict):
            return
        with _lock:
            key = _key(session_id, conversation_id)
            if key:
                _take(_state(key), tool_name, args, structured)
    except Exception:
        host.logger.debug("hermretro chat_state.observe failed", exc_info=True)


def _skill_page(args: dict) -> str | None:
    name = args.get("name")
    if not isinstance(name, str) or not name:
        return None
    page = args.get("file_path")
    return f"{name} {page}" if isinstance(page, str) and page else name


def _remember_page(state: dict, page: str) -> None:
    pages = [seen for seen in state["skills"] if seen != page] + [page]
    state["skills"] = pages[-MAX_SKILL_PAGES:]


def _take(state: dict, tool: str, args: dict, structured: dict) -> None:
    """Fold one successful engine result into the chat's state."""
    if isinstance(structured.get("projectRoot"), str):
        state["project"] = structured["projectRoot"]
    rom = structured.get("rom")
    if tool == "chromatic_rom_build" and structured.get("success") is True and isinstance(rom, dict):
        state["build"] = {"path": rom.get("path") or structured.get("outputPath"), "sha256": rom.get("sha256")}
    if tool == "chromatic_emulator_close":
        state.pop("emulator", None)
        state.pop("recording", None)
        return
    if not tool.startswith(ENGINE_PREFIX + "emulator_"):
        return
    emulator = state.setdefault("emulator", {})
    if isinstance(structured.get("romPath"), str):
        emulator.update(rom=structured["romPath"], sha256=structured.get("romSha256"))
    if isinstance(structured.get("frame"), int) and not isinstance(structured.get("frame"), bool):
        emulator["frame"] = structured["frame"]
    recording = next(
        (
            block
            for block in (structured.get("recording"), structured.get("recordingSpan"), structured)
            if isinstance(block, dict) and isinstance(block.get("sessionId"), str)
        ),
        None,
    )
    if recording is not None:
        known = state.get("recording") or {}
        status = recording.get("status")
        if tool == "chromatic_emulator_recording" and args.get("action") == "stop":
            status = "stopped"
        if not isinstance(status, str):
            status = known.get("status") if known.get("id") == recording["sessionId"] else None
        state["recording"] = {"id": recording["sessionId"], "status": status}


def compacted(session_id=None, old_session_id=None, kind=None, **_kwargs):
    """``post_compaction``: the chat's next tool result carries where it stands. Never raises."""
    try:
        if kind == PRUNE_ONLY or not session_id:
            return
        with _lock:
            key = _keys.get(old_session_id or "") or _key(session_id)
            _keys[session_id] = key
            _state(key)["due"] = True
    except Exception:
        host.logger.debug("hermretro chat_state.compacted failed", exc_info=True)


def deliver(result=None, session_id=None, conversation_id=None, **_kwargs):
    """``transform_tool_result``: after a compaction, the first text result the chat gets carries the note
    (a JSON object gains ``hermretroContext``; other text gains a closing line). A result with images is left as it
    is and the note waits for the next one. None when nothing changes. Never raises."""
    try:
        if not isinstance(result, str):
            return None
        with _lock:
            key = _keys.get(session_id or "") or conversation_id
            state = _chats.get(key) if key else None
            if not state or not state.get("due"):
                return None
            state["due"] = False
            known = {name: value for name, value in state.items() if name != "due"}
        try:
            project = host._chat_project(str(conversation_id or ""), str(session_id or ""))
        except Exception:
            project = None
        note = note_for(known, project)
        if not note:
            return None
        try:
            payload = json.loads(result)
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            return json.dumps({**payload, KEY: note}, ensure_ascii=False)
        return f"{result}\n\n[hermretro] {note}"
    except Exception:
        host.logger.debug("hermretro chat_state.deliver failed", exc_info=True)
        return None


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
    emulator = state.get("emulator") or {}
    if emulator.get("rom") or "frame" in emulator:
        where = f"Emulator: frame {emulator['frame']}" if "frame" in emulator else "Emulator: running"
        if emulator.get("rom"):
            where += f" of {emulator['rom']}{_sha(emulator.get('sha256'))}"
            if build.get("sha256") and emulator.get("sha256") and build["sha256"] != emulator["sha256"]:
                where += ", not the last build"
        parts.append(where + ".")
    recording = state.get("recording") or {}
    if recording.get("id"):
        parts.append(
            f"Recording: {recording['id']}" + (f" ({recording['status']})." if recording.get("status") else ".")
        )
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
