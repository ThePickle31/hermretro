"""The user's game library: which projects hermretro has worked on, and their build state.

Written by the broker whenever a conversation selects, creates, builds or previews a project, and
read by the desktop page (RPC ``games``). One small JSON file plus title-screen thumbnails, in a
per-user directory that survives restarts. Stdlib only and no Hermes imports: the broker loads it.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from stat import S_ISREG

from . import game_card, project, shelf
from .project import (  # noqa: F401 - existing library imports
    EXPORT_SOURCES,
    FRESH_SLACK_SECONDS,
    MAX_SOURCE_FILES,
    NOT_SOURCE,
    WEB_MANIFEST,
    _json,
    engine_made_export,
    export_freshness,
    file_sha256,
    has_web_export,
    project_file,
    project_kind,
    project_title,
    source_digest,
    sources_newer_than,
    web_dir,
    web_export_time,
    web_rom,
)
from .shelf import public_session as public_session
from .shelf import ERROR_CHARS as ERROR_CHARS

VERSION = 1
SELECTORS = frozenset({"project_select", "project_create", "project_create_blank"})
MAX_THUMB_BYTES = 64 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_PRESENTATIONS = 100
MAX_NOTE_CHARS = 300


def game_id(root: str | os.PathLike) -> str:
    """Stable id of a project: the first 12 hex digits of SHA-1 over its canonical root."""
    return hashlib.sha1(os.path.realpath(str(root)).encode()).hexdigest()[:12]


def valid_id(value) -> bool:
    return isinstance(value, str) and len(value) == 12 and all(c in "0123456789abcdef" for c in value)


def decode_png(data_url, limit: int) -> bytes:
    """A ``data:image/png;base64,`` URL (or bare base64) to PNG bytes, bounded and checked."""
    if not isinstance(data_url, str) or not data_url:
        raise ValueError("png must be a data:image/png;base64 URL.")
    if data_url.startswith("data:") and not data_url[:32].lower().startswith("data:image/png;base64,"):
        raise ValueError("png must be a data:image/png;base64 URL.")
    payload = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    if len(payload) > (limit * 4) // 3 + 8:
        raise ValueError(f"The image is larger than {limit // 1024} KB.")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("png is not valid base64.") from error
    if len(raw) > limit:
        raise ValueError(f"The image is larger than {limit // 1024} KB.")
    if not raw.startswith(PNG_MAGIC):
        raise ValueError("png is not a PNG image.")
    return raw


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


MAX_PENDING = 50


def _pending_name(name) -> str | None:
    return (name.strip()[:120] or None) if isinstance(name, str) else None


class BindingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class RegistryError(OSError):
    """The library exists but could not be read safely."""


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


def _identified_game(identifier: str, entry: dict) -> dict:
    """Use the registry key even when a stored record names a different id."""
    return {**entry, "id": identifier}


class Registry:
    """``<dir>/games.json`` plus ``<dir>/thumbs/<id>.png``. Safe across processes: every change is
    a locked read-modify-write and the file is replaced atomically."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.path = self.directory / "games.json"
        self.thumbs = self.directory / "thumbs"

    @contextmanager
    def _locked(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with open(self.directory / "games.lock", "a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def load(self) -> dict:
        """Read the registry, defaulting only for an absent file and fields older registries omit."""
        try:
            try:
                info = self.path.lstat()
            except FileNotFoundError:
                return {"version": VERSION, "games": {}, "presentations": [], "pending": {}}
            if not S_ISREG(info.st_mode) and not S_ISREG(self.path.stat().st_mode):
                raise ValueError("The registry is not a regular file.")
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("games"), dict):
                raise ValueError("Expected a registry with a games object.")
            version = data.get("version", VERSION)
            if type(version) is not int or version != VERSION:
                raise ValueError(f"Unsupported registry version: {version!r}.")
            if not isinstance(data.get("presentations", []), list) or not isinstance(data.get("pending", {}), dict):
                raise ValueError("Invalid presentations or pending records.")
        except (OSError, ValueError, RecursionError) as error:
            raise RegistryError(f"Could not read the game library at {self.path}: {error}") from error
        # Preserve unknown keys and individual records, even if a reader skips malformed metadata.
        return {"version": VERSION, "presentations": [], "pending": {}, **data}

    def _save(self, data: dict) -> None:
        _atomic_write(self.path, json.dumps(data, indent=1, sort_keys=True).encode())

    def get(self, identifier: str) -> dict | None:
        entry = self.load()["games"].get(identifier) if valid_id(identifier) else None
        if isinstance(entry, dict) and isinstance(entry.get("projectRoot"), str):
            return _identified_game(identifier, entry)
        return None

    @staticmethod
    def _update_project(entry: dict, real: Path, now: float) -> None:
        entry["projectRoot"] = str(real)
        entry["updatedAt"] = now
        entry["title"] = project_title(real, entry.get("title"))
        entry["kind"] = project_kind(real)

    def upsert(
        self,
        root: str,
        *,
        chat: dict | None = None,
        build: dict | None = None,
        web_export: float | None = None,
        sources: str | None = None,
        only_if_missing: bool = False,
    ) -> dict | None:
        real = Path(os.path.realpath(root))
        if not real.is_dir():
            return None
        identifier = game_id(real)
        now = time.time()
        with self._locked():
            data = self.load()
            entry = data["games"].get(identifier)
            if only_if_missing and identifier in data["games"]:
                return _identified_game(identifier, entry) if isinstance(entry, dict) else None
            entry = entry if isinstance(entry, dict) else {"id": identifier, "projectRoot": str(real), "addedAt": now}
            self._update_project(entry, real, now)
            if chat and _takes_chat(entry, chat):
                entry["chat"] = chat
            if build is not None:
                entry["lastBuild"] = build
            if web_export is not None:
                entry["lastWebExport"] = {"t": web_export, **({"sources": sources} if sources else {})}
            data["games"][identifier] = entry
            self._save(data)
            return _identified_game(identifier, entry)

    def present(self, root: str, *, chat: dict | None = None, note: str | None = None) -> dict | None:
        """Record that the agent showed this game to the user (``chromatic_present_game``): the chat
        that did it, when, and the note for the user. The desktop reads it back via ``presentations``."""
        real = Path(os.path.realpath(root))
        if not real.is_dir():
            return None
        identifier = game_id(real)
        note = note.strip()[:MAX_NOTE_CHARS] if isinstance(note, str) and note.strip() else None
        now = time.time()
        with self._locked():
            data = self.load()
            entry = data["games"].get(identifier)
            entry = entry if isinstance(entry, dict) else {"id": identifier, "projectRoot": str(real), "addedAt": now}
            self._update_project(entry, real, now)
            if chat and _takes_chat(entry, chat):
                entry["chat"] = chat
            entry["presented"] = {"t": now, "note": note}
            data["games"][identifier] = entry
            record = {
                "gameId": identifier,
                "t": now,
                "note": note,
                "title": entry.get("title") or real.name,
                "sessionId": (chat or {}).get("sessionId"),
                "conversationId": (chat or {}).get("conversationId"),
                "profile": (chat or {}).get("profile"),
            }
            data["presentations"] = (data["presentations"] + [record])[-MAX_PRESENTATIONS:]
            self._save(data)
            return {**_identified_game(identifier, entry), "presentation": record}

    def presentations(self, since: float | None = None) -> list[dict]:
        """Presentations newer than ``since`` (seconds), oldest first."""
        listed = [
            item
            for item in self.load()["presentations"]
            if isinstance(item, dict)
            and valid_id(item.get("gameId"))
            and project.timestamp(item.get("t"), None) is not None
        ]
        if since is not None:
            listed = [item for item in listed if item["t"] > since]
        return sorted(listed, key=lambda item: item["t"])

    def save_thumb(self, identifier: str, png: bytes) -> Path:
        if not valid_id(identifier):
            raise ValueError("Unknown game id.")
        path = self.thumbs / f"{identifier}.png"
        _atomic_write(path, png)
        return path

    def thumb(self, identifier: str) -> str | None:
        if not valid_id(identifier):
            return None
        path = self.thumbs / f"{identifier}.png"
        try:
            if not path.is_file():
                return None
            with path.open("rb") as handle:
                raw = handle.read(MAX_THUMB_BYTES + 1)
        except OSError:
            return None
        if not raw.startswith(PNG_MAGIC) or len(raw) > MAX_THUMB_BYTES:
            return None
        return "data:image/png;base64," + base64.b64encode(raw).decode()

    # -- Build: one game, one conversation --------------------------------------------
    # ``games[id].session = {storedId, profile, createdAt, aliases}`` names the one Hermes session that
    # works on a game (the Build page's conversation for it). ``pending[storedId]`` is a New Game
    # conversation whose project does not exist yet; the first project it creates or selects becomes
    # its game. Sessions are keyed per profile identity: session ids are per profile store.

    def binding_for(self, profile: str | None, ids) -> tuple[str | None, dict | None]:
        """``("game", entry)``, ``("pending", record)`` or ``(None, None)`` for a conversation."""
        wanted = {value for value in ids if isinstance(value, str) and value}
        if not wanted:
            return None, None
        kind, identifier, entry = self._binding_in(self.load(), profile, wanted)
        return kind, _identified_game(identifier, entry) if kind == "game" else entry

    def game_around(self, path: str) -> dict | None:
        """The library game whose folder holds ``path`` (not ``path`` itself); None when there is none. Only folders that
        still exist count: a game deleted from disk leaves its folder free."""
        real = Path(os.path.realpath(path))
        for identifier, entry in self.load()["games"].items():
            if not valid_id(identifier) or not isinstance(entry, dict) or not isinstance(entry.get("projectRoot"), str):
                continue
            root = Path(os.path.realpath(entry["projectRoot"]))
            if root in real.parents and root.is_dir():
                return _identified_game(identifier, entry)
        return None

    def game_for_root(self, root: str) -> dict | None:
        real = os.path.realpath(root)
        identifier = game_id(real)
        entry = self.load()["games"].get(identifier)
        return _identified_game(identifier, entry) if isinstance(entry, dict) else None

    def build_start(self, stored: str, profile: str | None, name: str | None = None, plan: bool = False) -> dict:
        """Record a conversation started on New Game (before its project exists)."""
        if not isinstance(stored, str) or not stored or len(stored) > 256:
            raise BindingError("INVALID", "A stored session id is required.")
        with self._locked():
            data = self.load()
            kind, _, _ = self._binding_in(data, profile, {stored})
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
            for key, _ in sorted(records, key=lambda item: item[1])[:-MAX_PENDING]:
                del data["pending"][key]
            self._save(data)
            return record

    def build_cancel(self, stored: str, profile: str | None) -> bool:
        with self._locked():
            data = self.load()
            record = data["pending"].get(stored)
            if not _session_matches(record, profile, {stored}):
                return False
            del data["pending"][stored]
            self._save(data)
            return True

    def bind(self, identifier: str, stored: str, profile: str | None, *, replace: str | None = None) -> dict:
        """Give a game its conversation. ``replace`` names the stored id of the conversation the page saw
        was removed: the swap happens only while the game is still bound to exactly that one, so two
        stale pages racing to replace it cannot detach each other's conversation."""
        if not valid_id(identifier) or not isinstance(stored, str) or not stored or len(stored) > 256:
            raise BindingError("INVALID", "A game id and a stored session id are required.")
        if replace is not None and (not isinstance(replace, str) or not replace or len(replace) > 256):
            raise BindingError("INVALID", "replace must be the stored session id being replaced.")
        with self._locked():
            data = self.load()
            entry = data["games"].get(identifier)
            if not isinstance(entry, dict):
                raise BindingError("NO_GAME", "That game is not in the library.")
            kind, _, other = self._binding_in(data, profile, {stored})
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
                    return _identified_game(identifier, entry)
                if current_id != replace:
                    raise BindingError("STALE", "This game's conversation changed since the page last looked.")
            elif replace is not None:
                raise BindingError("STALE", "This game no longer has the conversation being replaced.")
            entry["session"] = {"storedId": stored, "profile": profile, "createdAt": time.time(), "aliases": []}
            _chat_follows_session(entry)
            data["pending"].pop(stored, None)
            self._save(data)
            return _identified_game(identifier, entry)

    def unbind(self, identifier: str, stored: str, profile: str | None) -> bool:
        """Stop editing: the game lets go of its conversation (the session itself is kept). Only the
        named conversation, and only from its own profile, so a stale page cannot drop a newer one."""
        if not valid_id(identifier) or not isinstance(stored, str) or not stored:
            raise BindingError("INVALID", "A game id and a stored session id are required.")
        with self._locked():
            data = self.load()
            entry = data["games"].get(identifier)
            current = entry.get("session") if isinstance(entry, dict) else None
            if not isinstance(current, dict):
                return False
            if profile is not None and current.get("profile") not in (None, profile):
                raise BindingError("OTHER_PROFILE", "This game's conversation lives in another Hermes profile.")
            if not _session_matches(current, profile, {stored}):
                return False
            del entry["session"]
            self._save(data)
            return True

    def claim_pending(self, identifier: str, profile: str | None, ids) -> dict | None:
        """Bind a game to the pending conversation among ``ids``, if there is one and the game is free."""
        wanted = {value for value in ids if isinstance(value, str) and value}
        with self._locked():
            data = self.load()
            record = next((r for r in data["pending"].values() if _session_matches(r, profile, wanted)), None)
            entry = data["games"].get(identifier)
            if record is None or not isinstance(entry, dict) or isinstance(entry.get("session"), dict):
                return None
            entry["session"] = {
                "storedId": record["storedId"],
                "profile": record.get("profile"),
                "createdAt": time.time(),
                "aliases": [],
            }
            _chat_follows_session(entry)
            data["pending"].pop(record["storedId"], None)
            self._save(data)
            return _identified_game(identifier, entry)

    def note_alias(self, profile: str | None, conversation_id: str, session_id: str) -> None:
        """Remember a bound conversation's live session id (compression rotates it), so a hook that only
        knows the session id still finds the game."""
        if not conversation_id or not session_id or conversation_id == session_id:
            return
        with self._locked():
            data = self.load()
            kind, _, found = self._binding_in(data, profile, {conversation_id})
            binding = found.get("session") if kind == "game" else found
            if not isinstance(binding, dict) or session_id in session_aliases(binding):
                return
            binding["aliases"] = (session_aliases(binding) + [session_id])[-16:]
            self._save(data)

    @staticmethod
    def _binding_in(data: dict, profile: str | None, wanted: set) -> tuple[str | None, str | None, dict | None]:
        for identifier, entry in data["games"].items():
            if (
                valid_id(identifier)
                and isinstance(entry, dict)
                and _session_matches(entry.get("session"), profile, wanted)
            ):
                return "game", identifier, entry
        for record in data["pending"].values():
            if _session_matches(record, profile, wanted):
                return "pending", None, record
        return None, None, None

    def pending(self, profile: str | None = None, *, snapshot: dict | None = None) -> list[dict]:
        data = self.load() if snapshot is None else snapshot
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

    # -- broker hook ---------------------------------------------------------------
    def observe(
        self,
        tool: str,
        arguments: dict,
        structured: dict,
        failed: bool,
        *,
        lane_root: str | None,
        conversation_id: str | None,
        sessions_seen=(),
        profile: str | None = None,
    ) -> dict | None:
        """Record what one finished engine call means for the library. Called by the broker."""
        arguments = arguments if isinstance(arguments, dict) else {}
        structured = structured if isinstance(structured, dict) else {}
        chat = None
        if conversation_id:
            chat = {
                "conversationId": conversation_id,
                "sessionId": (list(sessions_seen) or [conversation_id])[-1],
                "profile": profile,
            }
        if tool in SELECTORS:
            root = structured.get("projectRoot")
            if failed or not isinstance(root, str):
                return None
            # A project created without selecting it still belongs to the library, but the chat only
            # owns the one it actually works on.
            owns = tool == "project_select" or arguments.get("select") is True
            entry = self.upsert(root, chat=chat if owns else None)
            if entry is not None and tool != "project_select":
                # Every game gets its card file when it is made; the agent fills it in before presenting.
                try:
                    game_card.scaffold(Path(root), project_title(Path(root)))
                except OSError:
                    pass
            if entry is not None and conversation_id and tool != "project_select":
                # A New Game conversation becomes its game's when it creates the project. Selecting an
                # existing game (to look at it) does not make it this conversation's game.
                claimed = self.claim_pending(entry["id"], profile, [conversation_id, *sessions_seen])
                return claimed or entry
            return entry
        if tool == "rom_build":
            root = lane_root or structured.get("projectRoot")
            if not isinstance(root, str):
                return None
            if "sourcePath" in arguments and project_file(Path(root)):
                return None  # a standalone C experiment inside a GB Studio project, not the game's build
            rom = structured.get("outputPath") or structured.get("romPath")
            sha = structured.get("romSha256") or structured.get("sha256")
            build = {
                "t": time.time(),
                "ok": not failed,
                "rom": rom if isinstance(rom, str) else None,
                "sha256": sha if isinstance(sha, str) else None,
                "error": None,
            }
            if failed:
                message = structured.get("error") or structured.get("message") or "The build failed."
                build["error"] = (message if isinstance(message, str) else json.dumps(message))[:ERROR_CHARS]
            return self.upsert(root, chat=chat, build=build)
        if tool == "web_preview" and not failed and lane_root and arguments.get("action") in (None, "open"):
            # The engine reuses an export whose sources did not change without rewriting its files, so
            # a successful open is what proves the web copy matches the latest build, not file times. Only the
            # game's own build/web counts: an export to another folder says nothing about it.
            output = arguments.get("outputPath")
            if output and os.path.realpath(Path(lane_root, output)) != os.path.realpath(web_dir(Path(lane_root))):
                return None
            return self.upsert(lane_root, chat=chat, web_export=time.time(), sources=source_digest(Path(lane_root)))
        return None

    # -- what the page sees ---------------------------------------------------------
    def describe(self, entry: dict, *, identifier: str | None = None) -> dict | None:
        root = shelf.registered_root(entry)
        if root is None:
            return None
        return shelf.describe(entry, identifier if identifier is not None else game_id(root), root, self.thumb)

    def library(self, *, snapshot: dict | None = None) -> list[dict]:
        listed, _ = self.library_listing(snapshot=snapshot)
        return listed

    def library_listing(self, *, snapshot: dict | None = None) -> tuple[list[dict], list[str]]:
        """Describe the shelf and identify registered games whose projects cannot be read."""
        data = self.load() if snapshot is None else snapshot
        games = []
        unavailable = []
        for identifier, entry in data["games"].items():
            if not valid_id(identifier):
                continue
            try:
                described = self.describe(entry, identifier=identifier)
            except OSError:
                unavailable.append(identifier)
                continue
            if described:
                games.append(described)
        games.sort(key=lambda g: project.timestamp(g.get("updatedAt")), reverse=True)
        return games, unavailable
