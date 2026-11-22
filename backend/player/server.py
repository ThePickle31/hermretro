"""Loopback server that runs ModRetro's real web player inside the Studio's sandboxed frame.

The engine's own preview server refuses framing and opaque origins on purpose, so the Studio does
not proxy it. It assembles the same page the way the engine does (``dist/server.js``
``prepareAnnotations``): the game's GB Studio web export, the engine's player modules
(``dist/web-annotations``), its device artwork and the engine's bootstrap, plus a small frame shim
(storage, the host annotation API, page commands). The frame's origin is opaque (``null``), so every
response allows any origin; the random path token is what keeps other pages out.

Stdlib only and no Hermes imports. One server per gateway process, started on first use.
"""

from __future__ import annotations

import email.parser
import email.policy
import hashlib
import json
import logging
import mimetypes
import re
import secrets
import socketserver
import threading
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .. import library
from . import skins
from ..system import paths

logger = logging.getLogger(__name__)

ANNOTATION_MOUNT = "codex-annotations"
CAPTURE_NAMESPACE = uuid.UUID("5d0c7f39-3b8e-4f4f-9a43-2f6c3c7d1a11")
MAX_CAPTURE_BYTES = 132 * 1024 * 1024  # the engine's 128 MiB video limit plus form overhead
MAX_JSON_BYTES = 64 * 1024
MEDIA_EXTENSIONS = {".png": "image/png", ".webm": "video/webm", ".mp4": "video/mp4"}
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".wasm": "application/wasm",
    ".gb": "application/octet-stream",
    ".gbc": "application/octet-stream",
    ".png": "image/png",
    ".webp": "image/webp",
    ".map": "application/json; charset=utf-8",
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".ttf": "font/ttf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
}
VIEW_ANCHOR = "export const DEVICE_COLORS = [\n"
# The engine's last rule ordering its colour rail (it puts two of its finishes first): the rail keeps the skins' order.
RAIL_ANCHOR = '.codex-game-view .cgv-color[data-device-color="codex"] { order: -1; }\n'
RAIL_ORDER = ".codex-game-view .cgv-color[data-device-color] { order: 0; }\n"
COLOR_KEY = "codex-gb-studio:device-color:v1"

# The built-in demo cartridge: GB Studio's own browser player bundled in ``player/web`` plus
# ModRetro's ``hello-color`` example ROM, read from the bundled engine. It needs no project, so the
# Emulator page can always show the real player, even before the user has made a game.
DEMO_ID = "demo"
DEMO = {"id": DEMO_ID, "title": "Hello Color", "kind": "gbdk", "note": "ModRetro example"}
DEMO_ROM_PATH = "rom/hello-color.gbc"


# -- where the engine's player files are ---------------------------------------------


def annotations_dir() -> Path:
    for root in (paths.PREPARED_ENGINE, paths.ENGINE_ROOT):
        candidate = root / "dist" / "web-annotations"
        if (candidate / "bridge.js").is_file():
            return candidate
    return paths.ENGINE_ROOT / "dist" / "web-annotations"


_view_cache: dict[tuple, bytes] = {}


def patched_view(source: Path) -> bytes:
    """``view.js`` with the plugin's skins (``player/skins/``) as its finishes, in their order."""
    info = source.stat()
    key = (str(source), info.st_size, info.st_mtime_ns, skins.signature())
    if key in _view_cache:
        return _view_cache[key]
    text = source.read_text()
    start = text.find(VIEW_ANCHOR)
    end = text.find("\n];", start) + 1
    if start < 0 or end < 1:
        logger.warning("hermretro: view.js has no DEVICE_COLORS list; serving it without the plugin's skins")
    elif entries := skins.rail_entries():
        text = text[: start + len(VIEW_ANCHOR)] + entries + text[end:]
        text = text.replace(RAIL_ANCHOR, RAIL_ANCHOR + RAIL_ORDER, 1)
    _view_cache.clear()
    _view_cache[key] = text.encode()
    return _view_cache[key]


# -- the frame page ------------------------------------------------------------------

# Runs first in the frame (``player/frame-shim.js``). The frame is sandboxed (allow-scripts, opaque
# origin), so: storage lives in memory, the player's same-origin fetches are sent as CORS requests to
# this server, and the host annotation API plus page commands talk to the Studio page through
# postMessage. ``__DEFAULT_COLOR__`` and ``__COLOR_KEY__`` are filled in here.
_shim_cache: dict[tuple, str] = {}


def frame_shim() -> str:
    """The shim as an inline ``<script>`` body, read once per file version."""
    source = paths.PLUGIN_ROOT / "player" / "frame-shim.js"
    info = source.stat()
    key = (info.st_size, info.st_mtime_ns, skins.signature())
    if key not in _shim_cache:
        text = (
            source.read_text(encoding="utf-8")
            .replace("__DEFAULT_COLOR__", skins.default_skin())
            .replace("__COLOR_KEY__", COLOR_KEY)
            .replace("</script", "<\\/script")
        )
        _shim_cache.clear()
        _shim_cache[key] = text
    return _shim_cache[key]


def engine_bootstrap(runtime_sha256: str) -> str:
    """The engine's own bootstrap (``dist/server.js`` ``prepareAnnotations``), unchanged: binjgb gets
    its verified wasm bytes, the runtime hash and the input owner before ``script.js`` starts it."""
    runtime_name = f"binjgb-{runtime_sha256}.wasm"
    return (
        "<script>(function(){const expected="
        + json.dumps(runtime_sha256)
        + ";const factory=Binjgb;const bytes=fetch("
        + json.dumps(f"./{ANNOTATION_MOUNT}/{runtime_name}")
        + ").then(async response=>{if(!response.ok)throw new Error(\"The game runtime is unavailable.\");const bytes=new "
        "Uint8Array(await response.arrayBuffer());const hash=Array.from(new Uint8Array(await crypto.subtle.digest(\"SHA-256\","
        "bytes)),v=>v.toString(16).padStart(2,\"0\")).join(\"\");if(hash!==expected)throw new Error(\"The game runtime "
        "changed.\");return bytes;});Binjgb=options=>Promise.all([bytes,import("
        + json.dumps(f"./{ANNOTATION_MOUNT}/input-owner.js")
        + ")]).then(([wasmBinary,input])=>factory({...options,wasmBinary}).then(module=>{module.codexRuntimeSha256=expected;"
        "input.installInputOwner(module);return module;}));})();</script>\n"
    )


def demo_web_dir() -> Path:
    return paths.PLUGIN_ROOT / "player" / "web"


def demo_rom() -> Path | None:
    """The ModRetro example ROM, read in place from the engine (never copied into ``engine/``)."""
    for root in (paths.ENGINE_ROOT, paths.PREPARED_ENGINE):
        candidate = root / "examples" / "hello-color" / "hello-color.gbc"
        if candidate.is_file():
            return candidate
    return None


def demo_captures_root() -> Path:
    """Where the demo's captures go (``<library>/captures/demo``): the demo has no project folder."""
    return paths.library_dir()


def is_demo(identifier) -> bool:
    return identifier == DEMO_ID


def _script_json(value) -> str:
    return json.dumps(value).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


class PlayerError(Exception):
    pass


def game_build(root: Path) -> dict:
    """What the frame needs to know about a game's web export, verified like the engine does."""
    web = library.web_dir(root)
    if not library.has_web_export(root):
        raise PlayerError("This game has no playable web build yet.")
    rom = library.web_rom(root)
    if rom is None:
        raise PlayerError("The web build names no ROM inside it.")
    rom_path = rom.relative_to(web).as_posix()
    if not re.fullmatch(r"(?:[^./\\:%?#][^/\\:%?#]*/)*[^./\\:%?#][^/\\:%?#]*\.gbc?", rom_path, re.I):
        raise PlayerError("The web build's ROM path is not a plain relative .gb or .gbc file.")
    rom_sha = library.file_sha256(rom)
    runtime_sha = library.file_sha256(web / "js" / "binjgb.wasm")
    record = library.read_json(web / ".codex-web-build.json")  # noqa: SLF001 - shared helper
    revision = record.get("sourceRevision") if isinstance(record.get("sourceRevision"), str) else None
    if not revision or not (0 < len(revision) <= 1024):
        revision = "hermes-" + rom_sha[:16]
    return {
        "web": web,
        "rom": rom,
        "romPath": rom_path,
        "romSha256": rom_sha,
        "runtimeSha256": runtime_sha,
        "sourceRevision": revision,
    }


def demo_build() -> dict:
    """``game_build`` for the demo cartridge: the bundled player and the engine's example ROM."""
    web = demo_web_dir()
    if not ((web / "index.html").is_file() and (web / "js" / "binjgb.wasm").is_file()):
        raise PlayerError("The bundled demo player is missing from the plugin folder.")
    rom = demo_rom()
    if rom is None:
        raise PlayerError("The demo ROM (the engine's hello-color example) is missing.")
    rom_sha = library.file_sha256(rom)
    return {
        "web": web,
        "rom": rom,
        "romPath": DEMO_ROM_PATH,
        "romSha256": rom_sha,
        "runtimeSha256": library.file_sha256(web / "js" / "binjgb.wasm"),
        "sourceRevision": "hermes-demo-" + rom_sha[:16],
    }


def build_for(identifier: str, root: Path) -> dict:
    return demo_build() if is_demo(identifier) else game_build(root)


def frame_document(root: Path, build: dict, capture_generation: str) -> bytes:
    """The game's own ``index.html`` with the shim, the engine bootstrap and the player modules."""
    html = (build["web"] / "index.html").read_text(encoding="utf-8")
    shim = "<script>" + frame_shim() + "</script>\n"
    head = re.search(r"<head\b[^>]*>", html, re.I)
    html = html[: head.end()] + "\n" + shim + html[head.end() :] if head else shim + html
    player = re.search(r"<script\b[^>]*\bsrc=([\"'])(?:\./)?js/script\.js\1[^>]*>\s*</script>", html, re.I)
    if not player:
        raise PlayerError("This web build does not use the official GB Studio browser player.")
    html = html[: player.start()] + engine_bootstrap(build["runtimeSha256"]) + html[player.start() :]
    context = {
        "romSha256": build["romSha256"],
        "romPath": build["romPath"],
        "sourceRevision": build["sourceRevision"],
        "runtimeSha256": build["runtimeSha256"],
        "captures": {"generation": capture_generation},
    }
    injection = (
        "\n<script type=\"application/json\" id=\"codex-web-annotations-context\">"
        + _script_json(context)
        + "</script>\n<script type=\"module\" src=\"./"
        + ANNOTATION_MOUNT
        + "/bridge.js\"></script>\n"
    )
    closing = [m.start() for m in re.finditer(r"</body\s*>", html, re.I)]
    at = closing[-1] if closing else len(html)
    return (html[:at] + injection + html[at:]).encode("utf-8")


# -- captures ----------------------------------------------------------------------------


def capture_root(identifier, game_root) -> Path | None:
    """Where a game's captures live (the folder ``list_captures``/``save_capture`` take as ``root``): the library
    folder for the demo cartridge (its captures go in ``<library>/captures/demo``), else ``game_root(identifier)``,
    the project folder (``host._game_root`` on the Hermes side); None for an unknown game."""
    if is_demo(identifier):
        return demo_captures_root()
    return game_root(identifier) if library.valid_id(identifier) else None


def captures_dir(root: Path, identifier: str | None = None) -> Path:
    return root / "captures" / DEMO_ID if is_demo(identifier) else root / "captures"


def capture_id(identifier: str, filename: str) -> str:
    """Stable per file, so a capture keeps its URL across restarts without an index."""
    return str(uuid.uuid5(CAPTURE_NAMESPACE, f"{identifier}/{filename}"))


def _stamp(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H-%M-%S-") + f"{now.microsecond // 1000:03d}Z"


def _free_name(directory: Path, stem: str, extension: str) -> Path:
    candidate = directory / f"{stem}.{extension}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{counter}.{extension}"
        counter += 1
    return candidate


def save_capture(
    root: Path, identifier: str, kind: str, media: bytes, media_type: str, metadata, extra: dict | None = None
) -> dict:
    """Write ``<project>/captures/<iso>-<kind>.<ext>`` and its ``.json`` sidecar; return the receipt the
    player checks (``id``, ``kind``, ``bytes``, ``path``, ``metadataPath``, ``sha256``, ``createdAt``, urls)."""
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", kind or ""):
        raise PlayerError("Unknown capture kind.")
    if not media:
        raise PlayerError("Capture media is empty.")
    if kind == "screenshot" or media.startswith(library.PNG_MAGIC):
        if not media.startswith(library.PNG_MAGIC):
            raise PlayerError("A screenshot must be a PNG image.")
        extension = "png"
    elif "mp4" in (media_type or "").lower():
        extension = "mp4"
    else:
        extension = "webm"
    directory = captures_dir(root, identifier)
    directory.mkdir(parents=True, exist_ok=True)
    created = datetime.now(UTC)
    target = _free_name(directory, f"{_stamp(created)}-{kind}", extension)
    target.write_bytes(media)
    sha = hashlib.sha256(media).hexdigest()
    identifier_value = capture_id(identifier, target.name)
    created_at = created.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    sidecar = target.with_name(target.name + ".json")
    sidecar.write_text(
        json.dumps(
            {
                "id": identifier_value,
                "kind": kind,
                "media": target.name,
                "mimeType": MEDIA_EXTENSIONS["." + extension],
                "bytes": len(media),
                "sha256": sha,
                "createdAt": created_at,
                "game": identifier,
                **(extra or {}),
                "metadata": metadata,
            },
            indent=1,
        )
    )
    return {
        "id": identifier_value,
        "kind": kind,
        "bytes": len(media),
        "path": str(target),
        "metadataPath": str(sidecar),
        "sha256": sha,
        "createdAt": created_at,
        "url": f"./codex-captures/{identifier_value}/media",
        "metadataUrl": f"./codex-captures/{identifier_value}/metadata",
    }


def list_captures(root: Path, identifier: str) -> list[dict]:
    """Media files directly in ``<project>/captures/``, newest first."""
    directory = captures_dir(root, identifier)
    found = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    for path in entries:
        if path.suffix.lower() not in MEDIA_EXTENSIONS or path.name.startswith(".") or not path.is_file():
            continue
        sidecar = library.read_json(path.with_name(path.name + ".json"))  # noqa: SLF001 - the library's shared JSON reader
        kind = (
            sidecar.get("kind")
            if isinstance(sidecar.get("kind"), str)
            else ("screenshot" if path.suffix.lower() == ".png" else "video")
        )
        created = (
            sidecar.get("createdAt")
            if isinstance(sidecar.get("createdAt"), str)
            else datetime.fromtimestamp(path.stat().st_mtime, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        found.append(
            {
                "id": capture_id(identifier, path.name),
                "path": str(path),
                "kind": kind,
                "createdAt": created,
                "file": path.name,
            }
        )
    found.sort(key=lambda c: c["createdAt"], reverse=True)
    return found


def find_capture(root: Path, identifier: str, cid: str) -> Path | None:
    directory = captures_dir(root, identifier)
    try:
        for path in directory.iterdir():
            if path.suffix.lower() in MEDIA_EXTENSIONS and capture_id(identifier, path.name) == cid and path.is_file():
                return path
    except OSError:
        pass
    return None


def parse_multipart(content_type: str, body: bytes) -> dict:
    """``multipart/form-data`` fields: name -> (bytes, content type, filename)."""
    if not content_type.lower().startswith("multipart/form-data"):
        raise PlayerError("Expected a multipart form.")
    message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    if not message.is_multipart():
        raise PlayerError("Expected a multipart form.")
    fields = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        fields[name] = (part.get_payload(decode=True) or b"", part.get_content_type(), part.get_filename())
    return fields


# -- the server ---------------------------------------------------------------------------


class _LoopbackHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer without HTTPServer.server_bind's socket.getfqdn(host): a reverse DNS lookup of
    127.0.0.1 that took about 35 s on GitHub's Apple Silicon runners and can stall a Mac's first "show the game"."""

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


class PlayerServer:
    def __init__(self, resolve):
        """``resolve(id) -> Path | None`` maps a game id to its project root."""
        self.resolve = resolve
        self.token = secrets.token_hex(32)
        self.generations: dict[str, list[str]] = {}
        self.lock = threading.Lock()
        server = _LoopbackHTTPServer(("127.0.0.1", 0), _Handler)
        server.daemon_threads = True
        server.player = self  # type: ignore[attr-defined]
        self.httpd = server
        self.port = server.server_address[1]
        self.thread = threading.Thread(target=server.serve_forever, name="chromatic-studio-player", daemon=True)
        self.thread.start()

    def base(self, identifier: str) -> str:
        return f"http://127.0.0.1:{self.port}/{self.token}/{identifier}/"

    def url(self, identifier: str) -> str:
        return self.base(identifier) + "index.html"

    def capture_url(self, identifier: str, cid: str) -> str:
        return self.base(identifier) + f"codex-captures/{cid}/media"

    def issue_generation(self, identifier: str) -> str:
        value = secrets.token_hex(16)
        with self.lock:
            issued = self.generations.setdefault(identifier, [])
            issued.append(value)
            del issued[:-32]
        return value

    def knows_generation(self, identifier: str, value: str) -> bool:
        with self.lock:
            return value in self.generations.get(identifier, [])

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


_server: PlayerServer | None = None
_server_lock = threading.Lock()


def get_server(resolve) -> PlayerServer:
    global _server
    with _server_lock:
        if _server is None or not _server.thread.is_alive():
            _server = PlayerServer(resolve)
        else:
            _server.resolve = resolve
        return _server


class _Handler(BaseHTTPRequestHandler):
    server_version = "ChromaticStudioPlayer"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002 - base class name  # keep the gateway log quiet; failures are logged explicitly
        pass

    # -- responses ---------------------------------------------------------------
    def _headers(self, status: int, content_type: str, length: int, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self._headers(status, content_type, len(body))
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, value) -> None:
        self._send(status, json.dumps(value).encode(), "application/json; charset=utf-8")

    def _text(self, status: int, text: str) -> None:
        self._send(status, text.encode(), "text/plain; charset=utf-8")

    def _file(self, path: Path, content_type: str | None = None) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            return self._text(404, "Not found.")
        self._send(
            200,
            data,
            content_type
            or MIME.get(path.suffix.lower())
            or mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
        )

    # -- routing -----------------------------------------------------------------
    def _route(self):
        """(server, game id, project root, relative path) or None after answering."""
        player: PlayerServer = self.server.player  # type: ignore[attr-defined]
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        if host not in ("127.0.0.1", "localhost"):
            self._text(403, "Forbidden.")
            return None
        parts = urlsplit(self.path).path.split("/")
        if len(parts) < 4 or not secrets.compare_digest(parts[1], player.token):
            self._text(404, "Not found.")
            return None
        identifier = parts[2]
        root = capture_root(identifier, player.resolve)
        if root is None:
            self._text(404, "Unknown game.")
            return None
        rel = unquote("/".join(parts[3:]))
        if "\\" in rel or "\0" in rel or any(seg in ("..", ".") for seg in rel.split("/")):
            self._text(400, "Bad path.")
            return None
        return player, identifier, Path(root), rel

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        requested = self.headers.get("Access-Control-Request-Headers")
        self.send_header("Access-Control-Allow-Headers", requested if requested and len(requested) < 1024 else "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            routed = self._route()
            if routed is None:
                return
            player, identifier, root, rel = routed
            if rel in ("", "index.html"):
                build = build_for(identifier, root)
                return self._send(
                    200, frame_document(root, build, player.issue_generation(identifier)), "text/html; charset=utf-8"
                )
            if rel.startswith(ANNOTATION_MOUNT + "/"):
                return self._annotation(root, rel[len(ANNOTATION_MOUNT) + 1 :], identifier)
            if rel == "codex-states":
                return self._json(200, {"states": []})
            if rel.startswith("codex-states/"):
                return self._text(404, "This saved moment is unavailable.")
            if rel.startswith("codex-captures/"):
                return self._capture_get(root, identifier, rel.split("/")[1:])
            if rel.startswith("codex-"):
                return self._text(404, "Not available in hermretro.")
            return self._export_file(root, rel, identifier)
        except PlayerError as error:
            self._text(409, str(error))
        except Exception as error:  # never let the gateway thread die on a bad request
            logger.exception("hermretro player server failed on GET")
            self._text(500, f"{type(error).__name__}")

    def do_POST(self):
        try:
            routed = self._route()
            if routed is None:
                return
            player, identifier, root, rel = routed
            length = int(self.headers.get("Content-Length") or 0)
            limit = MAX_CAPTURE_BYTES if rel == "codex-captures" else MAX_JSON_BYTES
            if length < 0 or length > limit:
                return self._text(413, "Too large.")
            body = self.rfile.read(length) if length else b""
            if rel == "codex-captures":
                return self._capture_post(player, root, identifier, body)
            if rel == "codex-device":
                try:
                    request = json.loads(body or b"{}")
                except ValueError:
                    request = {}
                generation = request.get("generation") if isinstance(request, dict) else None
                rom_sha = build_for(identifier, root)["romSha256"]
                # Installing from inside the player stays off: the Studio's own Install button sends the
                # flash request to chat, where Hermes's approval applies. Nothing is proxied to a device.
                return self._json(
                    200,
                    {
                        "generation": generation,
                        "devices": [],
                        "rom": {"sha256": rom_sha},
                        "available": False,
                        "blocked": False,
                        "detecting": False,
                    },
                )
            return self._text(404, "Not available in hermretro.")
        except PlayerError as error:
            self._json(400, {"error": str(error)})
        except Exception as error:
            logger.exception("hermretro player server failed on POST")
            self._json(500, {"error": f"{type(error).__name__}"})

    # -- handlers ------------------------------------------------------------------
    def _export_file(self, root: Path, rel: str, identifier: str = ""):
        if is_demo(identifier):
            if rel == DEMO_ROM_PATH:
                rom = demo_rom()
                return self._file(rom) if rom else self._text(404, "Not found.")
            web = demo_web_dir().resolve()
        else:
            web = library.web_dir(root).resolve()
        target = (web / rel).resolve()
        if (
            not target.is_relative_to(web)
            or any(part.startswith(".") for part in Path(rel).parts)
            or not target.is_file()
        ):
            return self._text(404, "Not found.")
        return self._file(target)

    def _annotation(self, root: Path, name: str, identifier: str = ""):
        if re.fullmatch(r"binjgb-[a-f0-9]{64}\.wasm", name):
            wasm = (demo_web_dir() if is_demo(identifier) else library.web_dir(root)) / "js" / "binjgb.wasm"
            if wasm.is_file() and library.file_sha256(wasm) == name[7:71]:
                return self._file(wasm, "application/wasm")
            return self._text(404, "The game runtime changed.")
        if re.fullmatch(r"chromatic-[a-z0-9-]+\.(?:webp|png)", name):
            skin = skins.image_for(name.removeprefix("chromatic-").rsplit(".", 1)[0])
            return self._file(skin) if skin is not None else self._text(404, "Not found.")
        if re.fullmatch(r"[a-z0-9-]+\.js(?:\.map)?", name):
            source = annotations_dir() / name
            if not source.is_file():
                return self._text(404, "Not found.")
            if name == "view.js":
                return self._send(200, patched_view(source), MIME[".js"])
            return self._file(source)
        return self._text(404, "Not found.")

    def _capture_get(self, root: Path, identifier: str, rest: list[str]):
        if len(rest) != 2 or rest[1] not in ("media", "metadata"):
            return self._text(404, "Not found.")
        path = find_capture(root, identifier, rest[0])
        if path is None:
            return self._text(404, "This capture is unavailable.")
        if rest[1] == "media":
            return self._file(path, MEDIA_EXTENSIONS[path.suffix.lower()])
        sidecar = path.with_name(path.name + ".json")
        if sidecar.is_file():
            return self._file(sidecar, "application/json; charset=utf-8")
        return self._json(200, {"id": rest[0], "media": path.name})

    def _capture_post(self, player: PlayerServer, root: Path, identifier: str, body: bytes):
        generation = self.headers.get("x-codex-preview-capture") or ""
        if not player.knows_generation(identifier, generation):
            return self._json(409, {"error": "The preview changed before saving. Keep the browser download."})
        fields = parse_multipart(self.headers.get("Content-Type") or "", body)
        kind = (fields.get("kind") or (b"", "", None))[0].decode("utf-8", "replace").strip()
        media, media_type, _filename = fields.get("media") or (b"", "", None)
        raw_meta = (fields.get("metadata") or (b"null", "", None))[0]
        try:
            metadata = json.loads(raw_meta or b"null")
        except ValueError:
            metadata = None
        build = build_for(identifier, root)
        receipt = save_capture(
            root,
            identifier,
            kind,
            media,
            media_type,
            metadata,
            {"romSha256": build["romSha256"], "sourceRevision": build["sourceRevision"]},
        )
        return self._json(200, receipt)
