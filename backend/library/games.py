"""The user's game library: which projects hermretro has worked on, and their build state.

Written by the broker whenever a conversation selects, creates, builds or previews a project, and
read by the desktop page (RPC ``games``). One small JSON file plus title-screen thumbnails, in a
per-user directory that survives restarts. Stdlib only and no Hermes imports: the broker loads it.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from stat import S_ISREG

from . import bindings, build_record, game_card, layout, ownership, project, shelf
from .bindings import BindingError as BindingError
from .bindings import session_aliases as session_aliases
from .freshness import (  # noqa: F401 - existing library imports
    EXPORT_SOURCES,
    FRESH_SLACK_SECONDS,
    MAX_SOURCE_FILES,
    WEB_MANIFEST,
    engine_made_export,
    export_freshness,
    source_digest,
    sources_newer_than,
    web_export_time,
)
from .project import (  # noqa: F401 - existing library imports
    NOT_SOURCE,
    _json,
    file_sha256,
    game_id,
    has_web_export,
    project_file,
    project_kind,
    project_title,
    valid_id,
    web_dir,
    web_rom,
)
from .shelf import public_session as public_session
from .shelf import ERROR_CHARS as ERROR_CHARS
from .thumbnails import MAX_THUMB_BYTES as MAX_THUMB_BYTES
from .thumbnails import PNG_MAGIC as PNG_MAGIC
from .thumbnails import decode_png as decode_png
from .thumbnails import read_thumbnail

VERSION = 1
SELECTORS = frozenset({"project_select", "project_create", "project_create_blank"})
MAX_PRESENTATIONS = 100
MAX_PENDING = 50
MAX_NOTE_CHARS = 300


def _atomic_write(path: Path, data: bytes, *, replace: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_bytes(data)
        if replace:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
    finally:
        temporary.unlink(missing_ok=True)


class RegistryError(OSError):
    """The library exists but could not be read safely."""


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
            return project.identified_game(identifier, entry)
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
        claim: tuple | None = None,
    ) -> dict | None:
        """Add or refresh a game. ``claim`` is ``(profile, conversation id, sessions seen)``: in the same locked step,
        a chat that belongs to no game becomes this game's conversation if it has none (``bindings.claim_in``), so no
        reader ever sees the game registered without the chat that brought it in."""
        real = Path(os.path.realpath(root))
        if not real.is_dir():
            return None
        identifier = game_id(real)
        now = time.time()
        with self._locked():
            data = self.load()
            entry = data["games"].get(identifier)
            if only_if_missing and identifier in data["games"]:
                return project.identified_game(identifier, entry) if isinstance(entry, dict) else None
            entry = entry if isinstance(entry, dict) else {"id": identifier, "projectRoot": str(real), "addedAt": now}
            self._update_project(entry, real, now)
            data["games"][identifier] = entry
            if claim is not None:
                bindings.claim_in(data, identifier, *claim)
            bindings.record_chat(entry, chat)
            if build is not None:
                entry["lastBuild"] = build
            if web_export is not None:
                entry["lastWebExport"] = {"t": web_export, **({"sources": sources} if sources else {})}
            data["games"][identifier] = entry
            self._save(data)
            return project.identified_game(identifier, entry)

    def move(self, old_root: str, new_root: str) -> tuple[str, str] | None:
        """Re-key the game at ``old_root`` to the folder it moved to, keeping its chat, session and builds.
        ``(old id, new id)``, or None when the library has no such game."""
        old_id, real = game_id(old_root), Path(os.path.realpath(new_root))
        with self._locked():
            data = self.load()
            entry = data["games"].pop(old_id, None)
            if not isinstance(entry, dict):
                return None
            new_id = game_id(real)
            entry["id"] = new_id
            self._update_project(entry, real, time.time())
            data["games"][new_id] = entry
            self._save(data)
        return old_id, new_id

    def forget_chats(self, kept: set[str] | None = None) -> None:
        """Games let go of conversations that are gone (the factory reset deleted the studio's chats): a Build
        session, a chat link and a New Game conversation not yet claimed, unless named in ``kept`` (the session ids
        still there; None: none are). A first plan still owed stays owed."""
        if not self.path.exists():
            return
        kept = kept or set()
        with self._locked():
            data = self.load()
            for entry in data["games"].values():
                if not isinstance(entry, dict):
                    continue
                session, chat = entry.get("session"), entry.get("chat")
                if isinstance(session, dict) and not (
                    {session.get("storedId"), *bindings.session_aliases(session)} & kept
                ):
                    if session.get("plan") is True:
                        entry.setdefault("initialPlan", True)
                    del entry["session"]
                if isinstance(chat, dict) and not ({chat.get("sessionId"), chat.get("conversationId")} & kept):
                    del entry["chat"]
            data["pending"] = {stored: value for stored, value in (data.get("pending") or {}).items() if stored in kept}
            self._save(data)

    def forget_builds(self, root: str) -> None:
        """Drop the recorded build and playable copy of a game whose files were replaced (an update)."""
        identifier = game_id(os.path.realpath(root))
        with self._locked():
            data = self.load()
            entry = data["games"].get(identifier)
            if isinstance(entry, dict) and {"lastBuild", "lastWebExport"} & entry.keys():
                entry.pop("lastBuild", None)
                entry.pop("lastWebExport", None)
                self._save(data)

    def present(
        self, root: str, *, chat: dict | None = None, note: str | None = None, unfinished: dict | None = None
    ) -> dict | None:
        """Record that the agent showed this game to the user (``chromatic_present_game``): the chat
        that did it, when, the note for the user and, for a game shown before it passed its checks, ``unfinished``
        (the user's request and what was not verified). The desktop reads it back via ``presentations``."""
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
            bindings.record_chat(entry, chat)
            entry["presented"] = {"t": now, "note": note, **({"unfinished": unfinished} if unfinished else {})}
            data["games"][identifier] = entry
            record = {
                "gameId": identifier,
                "t": now,
                "note": note,
                "title": entry.get("title") or real.name,
                "sessionId": (chat or {}).get("sessionId"),
                "conversationId": (chat or {}).get("conversationId"),
                "profile": (chat or {}).get("profile"),
                **({"unfinished": unfinished} if unfinished else {}),
            }
            data["presentations"] = (data["presentations"] + [record])[-MAX_PRESENTATIONS:]
            self._save(data)
            return {**project.identified_game(identifier, entry), "presentation": record}

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
        _atomic_write(path, png, replace=False)
        return path

    def thumb(self, identifier: str) -> str | None:
        if not valid_id(identifier):
            return None
        path = self.thumbs / f"{identifier}.png"
        return read_thumbnail(path)

    def game_around(self, path: str) -> dict | None:
        """The library game whose folder holds ``path`` (not ``path`` itself); None when there is none. Only folders that
        still exist count: a game deleted from disk leaves its folder free."""
        real = Path(os.path.realpath(path))
        for identifier, entry in self.load()["games"].items():
            if not valid_id(identifier) or not isinstance(entry, dict) or not isinstance(entry.get("projectRoot"), str):
                continue
            root = Path(os.path.realpath(entry["projectRoot"]))
            if root in real.parents and root.is_dir():
                return project.identified_game(identifier, entry)
        return None

    def owning_game(self, path: str, *, snapshot: dict | None = None) -> dict | None:
        """The library game whose folder is, or most deeply holds, ``path`` (read as the engine reads it); None when
        it is in no game. Folders match by file-system identity (``ownership``)."""
        data = self.load() if snapshot is None else snapshot
        found = ownership.owner_in(ownership.root_index(data["games"]), ownership.engine_path(path))
        return project.identified_game(found[0], found[1]) if found else None

    def game_for_root(self, root: str) -> dict | None:
        real = os.path.realpath(root)
        identifier = game_id(real)
        entry = self.load()["games"].get(identifier)
        return project.identified_game(identifier, entry) if isinstance(entry, dict) else None

    # -- Build conversations -------------------------------------------------------

    def binding_for(self, profile: str | None, ids, *, snapshot: dict | None = None) -> tuple[str | None, dict | None]:
        """``("game", entry)``, ``("pending", record)`` or ``(None, None)`` for a conversation (read from ``snapshot``
        when given)."""
        return bindings.binding_for(self, profile, ids, snapshot)

    def build_start(self, stored: str, profile: str | None, name: str | None = None, plan: bool = False) -> dict:
        """Record a conversation started on New Game (before its project exists)."""
        return bindings.build_start(self, stored, profile, name, plan, max_pending=MAX_PENDING)

    def build_cancel(self, stored: str, profile: str | None) -> bool:
        return bindings.build_cancel(self, stored, profile)

    def bind(self, identifier: str, stored: str, profile: str | None, *, replace: str | None = None) -> dict:
        """Give a game its conversation. ``replace`` names the stored id of the conversation the page saw
        was removed: the swap happens only while the game is still bound to exactly that one, so two
        stale pages racing to replace it cannot detach each other's conversation."""
        return bindings.bind(self, identifier, stored, profile, replace=replace)

    def unbind(self, identifier: str, stored: str, profile: str | None) -> bool:
        """Stop editing: the game lets go of its conversation (the session itself is kept). Only the
        named conversation, and only from its own profile, so a stale page cannot drop a newer one."""
        return bindings.unbind(self, identifier, stored, profile)

    def claim_pending(self, identifier: str, profile: str | None, ids) -> dict | None:
        """Bind a game to the pending conversation among ``ids``, if there is one and the game is free."""
        return bindings.claim_pending(self, identifier, profile, ids)

    def claim_new(self, identifier: str, profile: str | None, conversation_id: str, sessions_seen=()) -> dict | None:
        """Bind a game to the chat that just made it (or brought it into the library), when that chat belongs to no
        game and the game has no conversation yet."""
        return bindings.claim_new(self, identifier, profile, conversation_id, sessions_seen)

    def note_alias(self, profile: str | None, conversation_id: str, session_id: str) -> None:
        """Remember a bound conversation's live session id (compression rotates it), so a hook that only
        knows the session id still finds the game."""
        bindings.note_alias(self, profile, conversation_id, session_id)

    def pending(self, profile: str | None = None, *, snapshot: dict | None = None) -> list[dict]:
        return bindings.pending(self, profile, snapshot=snapshot)

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
        sources_before: str | None = None,
    ) -> dict | None:
        """Record what one finished engine call means for the library. Called by the broker; ``sources_before`` is
        a build's ``source_digest`` of the project taken before it started."""
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
            # A chat that belongs to no game becomes the conversation of the game it makes or brings into the
            # library, in the same step that registers it (the broker's guard_selection lets such a chat open only
            # projects the library did not have; one that lost the race to another chat is refused by the broker).
            claim = (profile, conversation_id, tuple(sessions_seen)) if conversation_id else None
            entry = self.upsert(root, chat=chat if owns else None, claim=claim)
            if entry is not None and tool != "project_select":
                # Every game gets its card file when it is made; the agent fills it in before presenting.
                try:
                    game_card.scaffold(Path(root), project_title(Path(root)))
                    layout.ensure(Path(root))  # and the rest of the game layout
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
            if not project.game_build(Path(root), arguments):
                return None
            rom = structured.get("outputPath") or structured.get("romPath")
            sha = project.built_rom_sha256(structured)
            build = {
                "t": time.time(),
                "ok": not failed,
                "rom": rom if isinstance(rom, str) else None,
                "sha256": sha,
                "error": None,
            }
            if failed:
                message = structured.get("error") or structured.get("message") or "The build failed."
                build["error"] = (message if isinstance(message, str) else json.dumps(message))[:ERROR_CHARS]
            elif sources_before is not None and source_digest(Path(root)) == sources_before:
                # What the ROM was built from (pipeline.rom_state). Left out when a file changed while it ran: the
                # gate never pairs this ROM with sources the compiler may not have read.
                build["sources"] = sources_before
            if not failed and isinstance(rom, str) and sha:
                try:  # game.json's romSha256 and builtWith, for the file this build made
                    build_record.record_build(Path(root), rom, sha, project.build_cli(structured))
                except OSError:
                    pass
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
        shelf.mark_duplicates(games)
        return games, unavailable
