"""Build identities, engine skin adaptation, and the document loaded inside the player frame."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from .. import library
from ..system import paths
from . import skins

logger = logging.getLogger(__name__)

ANNOTATION_MOUNT = "codex-annotations"
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
        candidate = root / "src" / "web-annotations"
        if (candidate / "bridge.js").is_file():
            return candidate
    return paths.ENGINE_ROOT / "src" / "web-annotations"


def patched_view(source: Path) -> bytes:
    """``view.js`` with the plugin's skins (``player/skins/``) as its finishes, in their order."""
    info = source.stat()
    return _patched_view(source, info.st_size, info.st_mtime_ns, skins.rail_entries())


@lru_cache(maxsize=1)
def _patched_view(source: Path, size: int, modified: int, entries: str) -> bytes:
    text = source.read_text()
    start = text.find(VIEW_ANCHOR)
    end = text.find("\n];", start) + 1
    if start < 0 or end < 1:
        logger.warning("hermretro: view.js has no DEVICE_COLORS list; serving it without the plugin's skins")
    elif entries:
        text = text[: start + len(VIEW_ANCHOR)] + entries + text[end:]
        text = text.replace(RAIL_ANCHOR, RAIL_ANCHOR + RAIL_ORDER, 1)
    return text.encode()


# -- the frame page ------------------------------------------------------------------


# Runs first in the frame (``player/frame-shim.js``). The frame is sandboxed (allow-scripts, opaque
# origin), so: storage lives in memory, the player's same-origin fetches are sent as CORS requests to
# this server, and the host annotation API plus page commands talk to the Studio page through
# postMessage. ``__DEFAULT_COLOR__`` and ``__COLOR_KEY__`` are filled in here.
def frame_shim() -> str:
    """The shim as an inline ``<script>`` body, read once per file version."""
    source = paths.PLUGIN_ROOT / "player" / "frame-shim.js"
    info = source.stat()
    return _frame_shim(source, info.st_size, info.st_mtime_ns, skins.default_skin())


@lru_cache(maxsize=1)
def _frame_shim(source: Path, size: int, modified: int, default_skin: str) -> str:
    return (
        source.read_text(encoding="utf-8")
        .replace("__DEFAULT_COLOR__", default_skin)
        .replace("__COLOR_KEY__", COLOR_KEY)
        .replace("</script", "<\\/script")
    )


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


def is_demo(identifier) -> bool:
    return identifier == DEMO_ID


def _script_json(value) -> str:
    return json.dumps(value).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


class PlayerError(Exception):
    pass


# A game the shell plays (``library.plays_in_shell``): the bundled player with the game's ROM at ``rom/game.gb[c]``,
# named in the ``gbstudio.json`` served for it.
SHELL_CONFIG = "gbstudio.json"


def shell_rom_path(relative: str) -> str:
    """Where the shell's ``gbstudio.json`` names a game's ROM ``relative`` (``build/game.gb[c]``)."""
    return "rom/game" + (".gbc" if relative.lower().endswith(".gbc") else ".gb")


def shell_config(relative: str) -> bytes:
    """The bundled player's ``gbstudio.json`` naming the game's ROM instead of the demo's."""
    config = json.loads((demo_web_dir() / SHELL_CONFIG).read_text(encoding="utf-8"))
    config["rom"] = shell_rom_path(relative)
    config.pop("project", None)
    return json.dumps(config).encode("utf-8")


def _shell_player(web: Path) -> None:
    if not ((web / "index.html").is_file() and (web / "js" / "binjgb.wasm").is_file()):
        raise PlayerError("The bundled player is missing from the plugin folder.")


def shell_build(root: Path) -> dict:
    """``game_build`` for a game the shell plays: the bundled player and the game's ROM (``library.shell_rom``)."""
    web = demo_web_dir()
    _shell_player(web)
    found = library.verified(root)
    if found is None:
        raise PlayerError(library.no_shell_rom(root))
    return {
        "web": web,
        "rom": Path(root) / found["relative"],
        "romPath": shell_rom_path(found["relative"]),
        "romSha256": found["sha256"],
        "runtimeSha256": library.file_sha256(web / "js" / "binjgb.wasm"),
        "sourceRevision": "hermes-rom-" + found["sha256"][:16],
        "shell": True,
    }


def game_build(root: Path) -> dict:
    """What the frame needs to know about what a game plays: its ROM in the shell (``shell_build``), else its web
    export, verified like the engine does."""
    if library.plays_in_shell(root):
        return shell_build(root)
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
    _shell_player(web)
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
