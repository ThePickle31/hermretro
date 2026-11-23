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
import json
import logging
import mimetypes
import os
import re
import secrets
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .. import library
from . import skins
from .captures import MEDIA_EXTENSIONS, capture_root, find_capture, save_capture
from .frame import (
    ANNOTATION_MOUNT,
    DEMO_ROM_PATH,
    PlayerError,
    annotations_dir,
    build_for,
    demo_rom,
    demo_web_dir,
    frame_document,
    is_demo,
    patched_view,
)

logger = logging.getLogger(__name__)

MAX_CAPTURE_BYTES = 132 * 1024 * 1024  # the engine's 128 MiB video limit plus form overhead
MAX_JSON_BYTES = 64 * 1024
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
        mime = (
            content_type
            or MIME.get(path.suffix.lower())
            or mimetypes.guess_type(path.name)[0]
            or "application/octet-stream"
        )
        try:
            stream = path.open("rb")
        except OSError:
            return self._text(404, "Not found.")
        with stream:
            remaining = os.fstat(stream.fileno()).st_size
            self._headers(200, mime, remaining)
            if self.command == "HEAD":
                return
            while remaining:
                chunk = stream.read(min(remaining, 256 * 1024))
                if not chunk:
                    self.close_connection = True
                    return
                self.wfile.write(chunk)
                remaining -= len(chunk)

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
