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

from . import game_card

VERSION = 1
SELECTORS = frozenset({"project_select", "project_create", "project_create_blank"})
# Folders under a project that hold build output, recordings or tooling, never game source.
NOT_SOURCE = frozenset({"build", "captures", "save-states", "artifacts", "node_modules", "__pycache__", "docs"})
# How many source files sources_newer_than looks at before it stops and calls the ROM current. Its own bound, not the
# snapshot cap (backend/history/snapshots.py MAX_FILES, which skips the copy): the two only happen to share a number.
MAX_SOURCE_FILES = 20000
MAX_THUMB_BYTES = 64 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_PRESENTATIONS = 100
MAX_NOTE_CHARS = 300
# A failed build's error, as recorded in lastBuild and answered by the games RPC.
ERROR_CHARS = 240
# File times of a build and the web export made right after it can differ by a little.
FRESH_SLACK_SECONDS = 2.0
# The record the engine writes into each web export it makes (engine/modretro-chromatic/dist/web-build.js).
WEB_MANIFEST = ".codex-web-build.json"


def game_id(root: str | os.PathLike) -> str:
    """Stable id of a project: the first 12 hex digits of SHA-1 over its canonical root."""
    return hashlib.sha1(os.path.realpath(str(root)).encode()).hexdigest()[:12]


def valid_id(value) -> bool:
    return isinstance(value, str) and len(value) == 12 and all(c in "0123456789abcdef" for c in value)


def decode_png(data_url, limit: int) -> bytes:
    """A ``data:image/png;base64,`` URL (or bare base64) to PNG bytes, bounded and checked."""
    if not isinstance(data_url, str) or not data_url:
        raise ValueError("png must be a data:image/png;base64 URL.")
    payload = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    if data_url.startswith("data:") and not data_url[:32].lower().startswith("data:image/png;base64,"):
        raise ValueError("png must be a data:image/png;base64 URL.")
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
    temporary.write_bytes(data)
    os.replace(temporary, path)


_hash_cache: dict[tuple, str] = {}
_hash_lock = threading.Lock()


def file_sha256(path: Path) -> str:
    info = path.stat()
    key = (str(path), info.st_size, info.st_mtime_ns)
    with _hash_lock:
        known = _hash_cache.get(key)
    if known:
        return known
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    value = digest.hexdigest()
    with _hash_lock:
        if len(_hash_cache) > 256:
            _hash_cache.clear()
        _hash_cache[key] = value
    return value


# -- facts read from the project on disk ---------------------------------------------


def project_file(root: Path) -> Path | None:
    try:
        return next(iter(sorted(root.glob("*.gbsproj"))), None)
    except OSError:
        return None


def project_kind(root: Path) -> str:
    return "gbstudio" if project_file(root) else "gbdk"


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def project_title(root: Path) -> str:
    project = project_file(root)
    if project:
        name = _json(project).get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()[:200]
    name = (_json(root / "build" / "web" / "gbstudio.json").get("project") or {}).get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()[:200]
    return root.name


def web_dir(root: Path) -> Path:
    return root / "build" / "web"


def has_web_export(root: Path) -> bool:
    web = web_dir(root)
    return (web / "index.html").is_file() and (web / "js" / "binjgb.wasm").is_file()


def web_rom(root: Path) -> Path | None:
    """The ROM inside the web export, from its ``gbstudio.json`` (path-checked)."""
    web = web_dir(root)
    rel = _json(web / "gbstudio.json").get("rom")
    if (
        not isinstance(rel, str)
        or not rel
        or rel.startswith("/")
        or ".." in rel.split("/")
        or not rel.lower().endswith((".gb", ".gbc"))
    ):
        return None
    path = web / rel
    try:
        if path.is_file() and path.resolve().is_relative_to(web.resolve()):
            return path
    except OSError:
        pass
    return None


def _newest_build_rom(root: Path) -> Path | None:
    try:
        roms = [p for p in (root / "build").glob("*.gb*") if p.suffix.lower() in (".gb", ".gbc") and p.is_file()]
    except OSError:
        return None
    return max(roms, key=lambda p: p.stat().st_mtime, default=None)


def web_export_time(root: Path) -> float | None:
    """When the playable web copy was written: its ROM's file time (else its ``index.html``)."""
    if not has_web_export(root):
        return None
    target = web_rom(root) or (web_dir(root) / "index.html")
    try:
        return target.stat().st_mtime
    except OSError:
        return None


def engine_made_export(root: Path) -> bool:
    """Whether ``build/web`` is the engine's own export, unchanged: its ``.codex-web-build.json`` lists the
    ROM and ``index.html`` it wrote, with their hashes, and both files still match. A copy assembled or edited
    by hand has no such record, or one whose hashes no longer match."""
    web = web_dir(root)
    manifest = _json(web / WEB_MANIFEST)
    files = manifest.get("files")
    rom = web_rom(root)
    if not isinstance(files, list) or rom is None or manifest.get("indexPath") != "index.html":
        return False
    if manifest.get("romPath") != rom.relative_to(web).as_posix():
        return False
    hashes = {item.get("path"): item.get("sha256") for item in files if isinstance(item, dict)}
    for relative in ("index.html", manifest["romPath"]):
        try:
            # The bytes as they are now, never a cached digest: a swapped file can keep its size and time.
            current = hashlib.sha256((web / relative).read_bytes()).hexdigest()
        except OSError:
            return False
        if current != hashes.get(relative):
            return False
    return True


# What a GB Studio web export is made from (the engine's own source fingerprint covers the same).
EXPORT_SOURCES = ("project", "assets", "plugins")


def source_digest(root: Path) -> str | None:
    """A digest of what the playable copy is made from: the ``.gbsproj`` and every file under ``project/``,
    ``assets/`` and ``plugins/``, by path and content. A deleted or renamed file changes it too; the card, the
    plans and the README do not. None for a project that is not GB Studio's, or past ``MAX_SOURCE_FILES``."""
    descriptor = project_file(root)
    if descriptor is None:
        return None
    digest = hashlib.sha256(b"hermretro\0export-sources\0v1\0")
    seen = 0
    files = [descriptor]
    for folder in EXPORT_SOURCES:
        for directory, folders, names in os.walk(root / folder):
            folders.sort()
            files += [Path(directory, name) for name in sorted(names)]
    for path in files:
        seen += 1
        if seen > MAX_SOURCE_FILES:
            return None
        try:
            if path.is_symlink() or not path.is_file():
                continue
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + file_sha256(path).encode() + b"\0")
        except OSError:
            continue
    return digest.hexdigest()


# What to do about a stale playable copy, by why it is stale.
_REBUILD = (
    "Run chromatic_rom_build for this project (with the 'Keep the playable copy current' setting on it also "
    "makes the playable copy; with it off, call chromatic_web_preview after it), then call "
    "chromatic_present_game again."
)
_REMAKE = (
    "Call chromatic_web_preview to make the playable copy from the current build, then call chromatic_present_game "
    "again. If chromatic_web_preview fails, tell the user what it said instead of building again."
)


def export_freshness(
    root: Path, last_build: dict | None = None, last_web_export: dict | None = None
) -> tuple[bool, str | None, str | None]:
    """Whether the web copy shows the latest build: ``(fresh, why, next step)``. Fresh means it exists, the engine
    made it (``engine_made_export``), it is not older than the last ROM build, and no game source changed after it.
    When the library recorded the build, its time counts (the native ROM file otherwise), and the copy's time is
    the later of its files and the last successful web export the broker recorded (the engine reuses an unchanged
    export without rewriting it). A failed build after the copy also counts as stale: the user would be shown an
    older game than the one being worked on."""
    last = last_build if isinstance(last_build, dict) else None
    recorded = float(last.get("t") or 0) if last else 0.0
    newest_rom = _newest_build_rom(root)
    try:
        rom_time = newest_rom.stat().st_mtime if newest_rom is not None else None
    except OSError:
        rom_time = None
    # When hermretro's own successful build is the newest ROM, only its playable copy is missing: building the
    # same thing again would loop, so the copy is made from it. A newer ROM nobody recorded needs a real build.
    remake = bool(last and last.get("ok")) and recorded + FRESH_SLACK_SECONDS >= (rom_time or 0.0)
    recover = _REMAKE if remake else _REBUILD
    exported = web_export_time(root)
    if exported is None:
        return False, "This game has no playable web copy yet.", recover
    if not engine_made_export(root):
        return (
            False,
            "The playable copy in build/web was not made by hermretro's build, or was changed after it, so it may "
            "not be this game as its sources stand.",
            "Never make, copy or edit files in build/ yourself. " + recover,
        )
    if isinstance(last_web_export, dict) and isinstance(last_web_export.get("t"), (int, float)):
        exported = max(exported, float(last_web_export["t"]))
    built = None if last else rom_time  # a recorded build's time counts, else the newest ROM file's
    if last and last.get("ok") is False and recorded > exported + FRESH_SLACK_SECONDS:
        return (
            False,
            "The last chromatic_rom_build of this game failed, so the playable copy is an older build.",
            "Fix what the build reported first. " + _REBUILD,
        )
    latest = max([moment for moment in (built, recorded if last and last.get("ok") else None) if moment] or [0.0])
    if latest > exported + FRESH_SLACK_SECONDS:
        return False, "The playable web copy is older than the last ROM build.", recover
    recorded_sources = last_web_export.get("sources") if isinstance(last_web_export, dict) else None
    if isinstance(recorded_sources, str):
        changed = source_digest(root) != recorded_sources
    else:  # an export recorded before the library kept its sources' digest
        changed = sources_newer_than(root, exported)
    if changed:
        return False, "Game files changed after the playable copy was made, so it is not the current game.", _REBUILD
    return True, None, None


def sources_newer_than(root: Path, moment: float) -> bool:
    """Whether any game source file under the project changed after ``moment`` (a ROM's mtime)."""
    seen = 0
    top = os.fspath(root)
    for directory, folders, files in os.walk(root):
        folders[:] = [f for f in folders if not f.startswith(".") and f not in NOT_SOURCE]
        for name in files:
            # The game card (game.json, cover.png) describes the game; it is not game source.
            if name.startswith(".") or (directory == top and name in game_card.CARD_FILES):
                continue
            seen += 1
            if seen > MAX_SOURCE_FILES:
                return False
            try:
                if os.stat(os.path.join(directory, name)).st_mtime > moment + 1.0:
                    return True
            except OSError:
                continue
    return False


# -- the registry ----------------------------------------------------------------------


MAX_PENDING = 50


class BindingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _session_matches(binding, profile: str | None, wanted: set) -> bool:
    if not isinstance(binding, dict) or not isinstance(binding.get("storedId"), str):
        return False
    if profile is not None and binding.get("profile") not in (None, profile):
        return False
    known = {binding["storedId"], *(alias for alias in binding.get("aliases") or [] if isinstance(alias, str))}
    return bool(known & wanted)


def _takes_chat(entry: dict, chat: dict) -> bool:
    """Whether ``chat`` may become the game's chat link. A game with a Build conversation keeps that one: another
    chat that touches it (with the user's go-ahead) must never become the chat that finds this game later."""
    session = entry.get("session")
    if not isinstance(session, dict):
        return True
    return _session_matches(session, chat.get("profile"), {chat.get("conversationId"), chat.get("sessionId")})


def _chat_follows_session(entry: dict) -> None:
    """A game just given its Build conversation links to it, unless its chat link already names that conversation
    (the shelf and the player open the linked chat)."""
    session = entry["session"]
    chat = entry.get("chat")
    if not isinstance(chat, dict) or not _takes_chat(entry, chat):
        stored = session["storedId"]
        entry["chat"] = {"conversationId": stored, "sessionId": stored, "profile": session.get("profile")}


def public_session(binding) -> dict | None:
    if not isinstance(binding, dict) or not isinstance(binding.get("storedId"), str):
        return None
    return {"storedId": binding["storedId"], "createdAt": binding.get("createdAt"), "profile": binding.get("profile")}


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
        data = _json(self.path)
        games = data.get("games")
        shown = data.get("presentations")
        pending = data.get("pending")
        # Unknown top-level keys are kept: another hermretro copy may share this file.
        return {
            **data,
            "version": VERSION,
            "games": games if isinstance(games, dict) else {},
            "presentations": [item for item in shown if isinstance(item, dict)] if isinstance(shown, list) else [],
            # Build: conversations started on New Game whose project does not exist yet (stored id → record).
            "pending": {key: value for key, value in pending.items() if isinstance(value, dict)}
            if isinstance(pending, dict)
            else {},
        }

    def _save(self, data: dict) -> None:
        _atomic_write(self.path, json.dumps(data, indent=1, sort_keys=True).encode())

    def get(self, identifier: str) -> dict | None:
        entry = self.load()["games"].get(identifier) if valid_id(identifier) else None
        return entry if isinstance(entry, dict) and isinstance(entry.get("projectRoot"), str) else None

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
            if entry is not None and only_if_missing:
                return entry
            entry = entry if isinstance(entry, dict) else {"id": identifier, "projectRoot": str(real), "addedAt": now}
            entry["projectRoot"] = str(real)
            entry["updatedAt"] = now
            try:
                entry["title"] = project_title(real)
                entry["kind"] = project_kind(real)
            except OSError:
                entry.setdefault("title", real.name)
            if chat and _takes_chat(entry, chat):
                entry["chat"] = chat
            if build is not None:
                entry["lastBuild"] = build
            if web_export is not None:
                entry["lastWebExport"] = {"t": web_export, **({"sources": sources} if sources else {})}
            data["games"][identifier] = entry
            self._save(data)
            return entry

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
            entry["projectRoot"] = str(real)
            entry["updatedAt"] = now
            try:
                entry["title"] = project_title(real)
                entry["kind"] = project_kind(real)
            except OSError:
                entry.setdefault("title", real.name)
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
            return {**entry, "presentation": record}

    def presentations(self, since: float | None = None) -> list[dict]:
        """Presentations newer than ``since`` (seconds), oldest first."""
        listed = [
            item
            for item in self.load()["presentations"]
            if valid_id(item.get("gameId")) and isinstance(item.get("t"), (int, float))
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
        path = self.thumbs / f"{identifier}.png"
        try:
            raw = path.read_bytes()
        except OSError:
            return None
        if not raw.startswith(PNG_MAGIC) or len(raw) > MAX_THUMB_BYTES:
            return None
        return "data:image/png;base64," + base64.b64encode(raw).decode()

    # -- Build: one game, one conversation --------------------------------------------
    # ``games[id].session = {storedId, profile, createdAt, aliases, plan?}`` names the one Hermes session that
    # works on a game (the Build page's conversation for it). ``pending[storedId]`` is a New Game
    # conversation whose project does not exist yet; the first project it creates or selects becomes
    # its game. Sessions are keyed per profile identity: session ids are per profile store.

    def binding_for(self, profile: str | None, ids) -> tuple[str | None, dict | None]:
        """``("game", entry)``, ``("pending", record)`` or ``(None, None)`` for a conversation."""
        wanted = {value for value in ids if isinstance(value, str) and value}
        return self._binding_in(self.load(), profile, wanted) if wanted else (None, None)

    def game_around(self, path: str) -> dict | None:
        """The library game whose folder holds ``path`` (not ``path`` itself); None when there is none. Only folders that
        still exist count: a game deleted from disk leaves its folder free."""
        real = Path(os.path.realpath(path))
        for entry in self.load()["games"].values():
            if not isinstance(entry, dict) or not isinstance(entry.get("projectRoot"), str):
                continue
            root = Path(os.path.realpath(entry["projectRoot"]))
            if root in real.parents and root.is_dir():
                return entry
        return None

    def game_for_root(self, root: str) -> dict | None:
        real = os.path.realpath(root)
        entry = self.load()["games"].get(game_id(real))
        return entry if isinstance(entry, dict) else None

    def build_start(self, stored: str, profile: str | None, name: str | None = None, plan: bool = False) -> dict:
        """Record a conversation started on New Game (before its project exists)."""
        if not isinstance(stored, str) or not stored or len(stored) > 256:
            raise BindingError("INVALID", "A stored session id is required.")
        with self._locked():
            data = self.load()
            kind, _ = self._binding_in(data, profile, {stored})
            if kind == "game":
                raise BindingError("BOUND", "This conversation already belongs to a game.")
            record = {
                "storedId": stored,
                "profile": profile,
                "createdAt": time.time(),
                "name": name.strip()[:120] if isinstance(name, str) and name.strip() else None,
                "plan": plan is True,
            }
            data["pending"][stored] = record
            # Keep the newest few: an abandoned New Game should not linger forever.
            for key in sorted(data["pending"], key=lambda k: data["pending"][k].get("createdAt") or 0)[:-MAX_PENDING]:
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
            kind, other = self._binding_in(data, profile, {stored})
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
                    return entry
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
            _chat_follows_session(entry)
            data["pending"].pop(stored, None)
            self._save(data)
            return entry

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
            if current.get("plan") is True:
                entry.setdefault("initialPlan", True)
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
                "aliases": record.get("aliases", []),
            }
            entry.setdefault("initialPlan", record.get("plan") is True)
            if entry["initialPlan"] is True:
                entry["session"]["plan"] = True
            _chat_follows_session(entry)
            data["pending"].pop(record["storedId"], None)
            self._save(data)
            return entry

    def note_alias(self, profile: str | None, conversation_id: str, session_id: str) -> None:
        """Remember a bound conversation's live session id (compression rotates it), so a hook that only
        knows the session id still finds the game."""
        if not conversation_id or not session_id or conversation_id == session_id:
            return
        with self._locked():
            data = self.load()
            kind, found = self._binding_in(data, profile, {conversation_id})
            binding = found.get("session") if kind == "game" else found
            if not isinstance(binding, dict) or session_id in (binding.get("aliases") or []):
                return
            binding["aliases"] = ((binding.get("aliases") or []) + [session_id])[-16:]
            self._save(data)

    @staticmethod
    def _binding_in(data: dict, profile: str | None, wanted: set) -> tuple[str | None, dict | None]:
        for entry in data["games"].values():
            if isinstance(entry, dict) and _session_matches(entry.get("session"), profile, wanted):
                return "game", entry
        for record in data["pending"].values():
            if _session_matches(record, profile, wanted):
                return "pending", record
        return None, None

    def pending(self, profile: str | None = None) -> list[dict]:
        listed = [
            {
                "storedId": r.get("storedId"),
                "name": r.get("name"),
                "createdAt": r.get("createdAt"),
                "profile": r.get("profile"),
            }
            for r in self.load()["pending"].values()
            if isinstance(r.get("storedId"), str) and (profile is None or r.get("profile") in (None, profile))
        ]
        return sorted(listed, key=lambda r: r.get("createdAt") or 0)

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
    def describe(self, entry: dict) -> dict | None:
        root = Path(entry["projectRoot"])
        if not root.is_dir():
            return None
        identifier = entry.get("id") or game_id(root)
        last = entry.get("lastBuild") if isinstance(entry.get("lastBuild"), dict) else None
        rom_path = None
        if last and last.get("ok") and isinstance(last.get("rom"), str) and Path(last["rom"]).is_file():
            rom_path = Path(last["rom"])
        rom_path = rom_path or web_rom(root) or _newest_build_rom(root)
        rom, built = None, None
        if rom_path is not None:
            info = rom_path.stat()
            built = info.st_mtime
            rom = {"path": str(rom_path), "sha256": file_sha256(rom_path), "size": info.st_size, "builtAt": int(built)}
        # The player runs the web export, whose ROM is its own compilation (not byte-identical to the
        # native build): the page compares this hash with the one the player loaded.
        exported = has_web_export(root)
        web_path = web_rom(root) if exported else None
        web = None
        if web_path is not None:
            web_info = web_path.stat()
            web = {"sha256": file_sha256(web_path), "builtAt": int(web_info.st_mtime)}
        if last and last.get("ok") is False and (built is None or float(last.get("t") or 0) >= built):
            state = "failed"
        elif built is None:
            state = "unbuilt"
        elif sources_newer_than(root, built):
            state = "changed"
        else:
            state = "ready"
        try:
            title = project_title(root)
        except OSError:
            title = entry.get("title") or root.name
        card = game_card.public(root)
        cover = game_card.cover_data_url(root) if card and card["hasCover"] else None
        return {
            "id": identifier,
            "title": title,
            "projectRoot": str(root),
            "kind": project_kind(root),
            "state": state,
            "rom": rom,
            "webExport": exported,
            "web": web,
            "thumb": cover or self.thumb(identifier),
            "cover": bool(cover),
            "card": card,
            "displayTitle": (card or {}).get("title") or title,
            "chat": entry.get("chat") if isinstance(entry.get("chat"), dict) else None,
            "session": public_session(entry.get("session")),
            "error": (str((last or {}).get("error") or "The build failed."))[:ERROR_CHARS]
            if state == "failed"
            else None,
            "updatedAt": entry.get("updatedAt"),
        }

    def library(self) -> list[dict]:
        games = []
        for entry in self.load()["games"].values():
            if not isinstance(entry, dict) or not isinstance(entry.get("projectRoot"), str):
                continue
            try:
                described = self.describe(entry)
            except OSError:
                described = None
            if described:
                games.append(described)
        games.sort(key=lambda g: -(g.get("updatedAt") or 0))
        return games
