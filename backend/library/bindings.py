"""Build conversation ownership, session aliases and pending New Game records.

``games[id].session`` names the Hermes conversation that works on a game. ``pending[storedId]`` names
a New Game conversation awaiting its first project. Matching uses the profile identity and session IDs.
Each binding write uses the registry lock from load through save.
"""

from __future__ import annotations

import time

from . import project


def _pending_name(name) -> str | None:
    return (name.strip()[:120] or None) if isinstance(name, str) else None


class BindingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def session_aliases(binding: dict) -> list[str]:
    aliases = binding.get("aliases")
    return [alias for alias in aliases if isinstance(alias, str)] if isinstance(aliases, list) else []


def _session_matches(binding, profile: str | None, wanted: set) -> bool:
    if not isinstance(binding, dict) or not isinstance(binding.get("storedId"), str):
        return False
    if profile is not None and binding.get("profile") not in (None, profile):
        return False
    known = {binding["storedId"], *session_aliases(binding)}
    return bool(known & wanted)


def _takes_chat(entry: dict, chat: dict) -> bool:
    """Whether ``chat`` may become the game's chat link. A game with a Build conversation keeps that one: another
    chat that touches it (with the user's go-ahead) must never become the chat that finds this game later."""
    session = entry.get("session")
    if not isinstance(session, dict):
        return True
    wanted = {value for key in ("conversationId", "sessionId") if isinstance(value := chat.get(key), str)}
    return _session_matches(session, chat.get("profile"), wanted)


def _chat_follows_session(entry: dict) -> None:
    """A game just given its Build conversation links to it, unless its chat link already names that conversation
    (the shelf and the player open the linked chat)."""
    session = entry["session"]
    chat = entry.get("chat")
    if not isinstance(chat, dict) or not _takes_chat(entry, chat):
        stored = session["storedId"]
        entry["chat"] = {"conversationId": stored, "sessionId": stored, "profile": session.get("profile")}


def record_chat(entry: dict, chat: dict | None) -> None:
    """Keep the game's chat link with its own conversation when one is bound."""
    if chat and _takes_chat(entry, chat):
        entry["chat"] = chat


def binding_for(registry, profile: str | None, ids) -> tuple[str | None, dict | None]:
    wanted = {value for value in ids if isinstance(value, str) and value}
    if not wanted:
        return None, None
    kind, identifier, entry = _binding_in(registry.load(), profile, wanted)
    return kind, project.identified_game(identifier, entry) if kind == "game" else entry


def build_start(registry, stored: str, profile: str | None, name: str | None, plan: bool, *, max_pending: int) -> dict:
    if not isinstance(stored, str) or not stored or len(stored) > 256:
        raise BindingError("INVALID", "A stored session id is required.")
    with registry._locked():
        data = registry.load()
        kind, _, _ = _binding_in(data, profile, {stored})
        if kind == "game":
            raise BindingError("BOUND", "This conversation already belongs to a game.")
        record = {
            "storedId": stored,
            "profile": profile,
            "createdAt": time.time(),
            "name": _pending_name(name),
            "plan": plan is True,
        }
        data["pending"][stored] = record
        # Keep the newest few: an abandoned New Game should not linger forever.
        records = [
            (key, project.timestamp(item.get("createdAt")))
            for key, item in data["pending"].items()
            if isinstance(item, dict)
        ]
        for key, _ in sorted(records, key=lambda item: item[1])[:-max_pending]:
            del data["pending"][key]
        registry._save(data)
        return record


def build_cancel(registry, stored: str, profile: str | None) -> bool:
    with registry._locked():
        data = registry.load()
        record = data["pending"].get(stored)
        if not _session_matches(record, profile, {stored}):
            return False
        del data["pending"][stored]
        registry._save(data)
        return True


def bind(registry, identifier: str, stored: str, profile: str | None, *, replace: str | None = None) -> dict:
    if not project.valid_id(identifier) or not isinstance(stored, str) or not stored or len(stored) > 256:
        raise BindingError("INVALID", "A game id and a stored session id are required.")
    if replace is not None and (not isinstance(replace, str) or not replace or len(replace) > 256):
        raise BindingError("INVALID", "replace must be the stored session id being replaced.")
    with registry._locked():
        data = registry.load()
        entry = data["games"].get(identifier)
        if not isinstance(entry, dict):
            raise BindingError("NO_GAME", "That game is not in the library.")
        kind, _, other = _binding_in(data, profile, {stored})
        if kind == "game" and other is not entry:
            raise BindingError("BOUND", "This conversation already belongs to another game.")
        current = entry.get("session")
        if isinstance(current, dict):
            current_id = current.get("storedId")
            if current_id != stored and replace is None:
                raise BindingError("HAS_CONVERSATION", "This game already has its own conversation.")
            if profile is not None and current.get("profile") not in (None, profile):
                raise BindingError("OTHER_PROFILE", "This game's conversation lives in another Hermes profile.")
            if current_id == stored:
                return project.identified_game(identifier, entry)
            if current_id != replace:
                raise BindingError("STALE", "This game's conversation changed since the page last looked.")
        elif replace is not None:
            raise BindingError("STALE", "This game no longer has the conversation being replaced.")
        entry["session"] = {"storedId": stored, "profile": profile, "createdAt": time.time(), "aliases": []}
        if kind == "pending":
            entry.setdefault("initialPlan", other.get("plan") is True)
        elif isinstance(current, dict) and current.get("plan") is True:
            entry.setdefault("initialPlan", True)
        if entry.get("initialPlan") is True:
            entry["session"]["plan"] = True
        elif kind != "pending" and entry.get("initialPlan") is None:
            entry["session"]["edit"] = True
        _chat_follows_session(entry)
        data["pending"].pop(stored, None)
        registry._save(data)
        return project.identified_game(identifier, entry)


def unbind(registry, identifier: str, stored: str, profile: str | None) -> bool:
    if not project.valid_id(identifier) or not isinstance(stored, str) or not stored:
        raise BindingError("INVALID", "A game id and a stored session id are required.")
    with registry._locked():
        data = registry.load()
        entry = data["games"].get(identifier)
        current = entry.get("session") if isinstance(entry, dict) else None
        if not isinstance(current, dict):
            return False
        if profile is not None and current.get("profile") not in (None, profile):
            raise BindingError("OTHER_PROFILE", "This game's conversation lives in another Hermes profile.")
        if not _session_matches(current, profile, {stored}):
            return False
        if current.get("plan") is True:
            entry.setdefault("initialPlan", True)
        del entry["session"]
        registry._save(data)
        return True


def claim_pending(registry, identifier: str, profile: str | None, ids) -> dict | None:
    wanted = {value for value in ids if isinstance(value, str) and value}
    with registry._locked():
        data = registry.load()
        record = next((r for r in data["pending"].values() if _session_matches(r, profile, wanted)), None)
        entry = data["games"].get(identifier)
        if record is None or not isinstance(entry, dict) or isinstance(entry.get("session"), dict):
            return None
        entry["session"] = {
            "storedId": record["storedId"],
            "profile": record.get("profile"),
            "createdAt": time.time(),
            "aliases": record.get("aliases", []),
        }
        entry.setdefault("initialPlan", record.get("plan") is True)
        if entry["initialPlan"] is True:
            entry["session"]["plan"] = True
        _chat_follows_session(entry)
        data["pending"].pop(record["storedId"], None)
        registry._save(data)
        return project.identified_game(identifier, entry)


def claim_new(registry, identifier: str, profile: str | None, conversation_id: str, sessions_seen=()) -> dict | None:
    """Make a chat that belongs to no game the conversation of the game it just made (or the project it just brought
    into the library), so every library game is edited from one chat. Nothing changes when the chat already belongs to
    a game or is a New Game conversation (``claim_pending`` is that one's), or the game already has its conversation."""
    if not isinstance(conversation_id, str) or not conversation_id or len(conversation_id) > 256:
        return None
    wanted = {conversation_id, *(value for value in sessions_seen if isinstance(value, str) and value)}
    with registry._locked():
        data = registry.load()
        entry = data["games"].get(identifier)
        kind, _, _ = _binding_in(data, profile, wanted)
        if kind is not None or not isinstance(entry, dict) or isinstance(entry.get("session"), dict):
            return None
        aliases = [value for value in sessions_seen if isinstance(value, str) and value and value != conversation_id]
        entry["session"] = {
            "storedId": conversation_id,
            "profile": profile,
            "createdAt": time.time(),
            "aliases": aliases[-16:],
        }
        _chat_follows_session(entry)
        registry._save(data)
        return project.identified_game(identifier, entry)


def note_alias(registry, profile: str | None, conversation_id: str, session_id: str) -> None:
    if not conversation_id or not session_id or conversation_id == session_id:
        return
    with registry._locked():
        data = registry.load()
        kind, _, found = _binding_in(data, profile, {conversation_id})
        binding = found.get("session") if kind == "game" else found
        if not isinstance(binding, dict) or session_id in session_aliases(binding):
            return
        binding["aliases"] = (session_aliases(binding) + [session_id])[-16:]
        registry._save(data)


def _binding_in(data: dict, profile: str | None, wanted: set) -> tuple[str | None, str | None, dict | None]:
    for identifier, entry in data["games"].items():
        if (
            project.valid_id(identifier)
            and isinstance(entry, dict)
            and _session_matches(entry.get("session"), profile, wanted)
        ):
            return "game", identifier, entry
    for record in data["pending"].values():
        if _session_matches(record, profile, wanted):
            return "pending", None, record
    return None, None, None


def pending(registry, profile: str | None = None, *, snapshot: dict | None = None) -> list[dict]:
    data = registry.load() if snapshot is None else snapshot
    listed = [
        {
            "storedId": r.get("storedId"),
            "name": _pending_name(r.get("name")),
            "createdAt": project.timestamp(r.get("createdAt"), None),
            "profile": r.get("profile"),
        }
        for r in data["pending"].values()
        if isinstance(r, dict)
        and isinstance(r.get("storedId"), str)
        and (profile is None or r.get("profile") in (None, profile))
    ]
    return sorted(listed, key=lambda r: project.timestamp(r.get("createdAt")))
