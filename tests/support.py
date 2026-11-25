"""Shared test helpers. Tests must never touch the developer's real Hermes home or hermretro's folder in it.

``isolated_home(self)`` in a test's setUp moves both at once: ``HERMRETRO_HOME`` (games, library, broker) and
Hermes's plugin data folder (``backend.hermes.host._data_dir()``: history snapshots, asset versions, frames),
which ``HERMRETRO_HOME`` alone does not move. ``throwaway_profile`` patches only the plugin data folder,
``throwaway_deps`` the downloads (fixed at import, so ``HERMRETRO_HOME`` does not move them either).
``python tools/check.py unit`` fails when the suite writes anything into the home folder.

Import these as ``from tests.support import ...``: putting tests/ itself on sys.path makes tests/backend shadow
the real backend package (tests/repo/test_test_imports.py refuses it)."""

import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend.hermes import api as hermes_api
from backend.hermes import host as hermes_host
from backend.library import freshness
from backend.system import paths


# Per-folder overrides that would win over HERMRETRO_HOME when the developer's shell sets them.
FOLDER_OVERRIDES = ("HERMRETRO_LIBRARY_DIR", "HERMRETRO_RUNTIME_DIR", "HERMRETRO_GAMES_DIR")


def isolated_home(test) -> SimpleNamespace:
    """Give ``test`` (a unittest.TestCase, in setUp) its own hermretro home and plugin data folder, both in one
    new temp folder, undone by the test's cleanups. Returns ``base`` (the temp folder), ``home`` (the
    ``HERMRETRO_HOME``), ``data`` (what ``host._data_dir()`` returns, created; its profile home is
    ``data.parents[1]``, so session lookups read nothing real either) and ``runtime`` (its own short
    ``HERMRETRO_RUNTIME_DIR`` under /tmp, removed afterwards)."""
    return test.enterContext(home_isolation())


@contextmanager
def home_isolation():
    """``isolated_home`` as a context manager, for code that is not a test case (the acceptance suite's studio
    chat)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp).resolve()
        home, data = base / "hermretro", base / "profile" / "plugin-data" / "hermretro"
        data.mkdir(parents=True)
        # Its own runtime folder, short enough for the broker socket wherever the temp base is (paths falls back
        # to the shared /tmp/hermretro-<uid> for a deep home, and an inherited HERMRETRO_RUNTIME_DIR would win).
        runtime = tempfile.mkdtemp(prefix="hrt-", dir="/tmp")
        environ = {key: value for key, value in os.environ.items() if key not in FOLDER_OVERRIDES}
        environ.update(HERMRETRO_HOME=str(home), HERMRETRO_RUNTIME_DIR=runtime)
        try:
            with mock.patch.dict(os.environ, environ, clear=True), throwaway_profile(base):
                yield SimpleNamespace(base=base, home=home, data=data, runtime=Path(runtime))
        finally:
            shutil.rmtree(runtime, ignore_errors=True)


def throwaway_profile(base: Path):
    """Patch hermes_host's view of Hermes storage so this plugin's data folder is inside ``base``.

    The data folder's profile home (``base/profile``) is where hermes_host looks for the session
    database, so chat titles and session lookups read nothing real either. Returns the patch (start it,
    or use it as a context manager); Hermes itself does not need to be importable."""
    data = Path(base) / "profile" / "plugin-data" / "hermretro"
    return mock.patch.object(hermes_host, "_data_dir", lambda: data)


def fake_profile_config(test, api=hermes_api) -> list[tuple[str, object]]:
    """Stand in for Hermes's profile config reads and one-key writes (``api``, backend/hermes/api.py or a loaded copy's)
    for the rest of ``test``. A profile's config.yaml is JSON here (YAML reads it the same) and, as in Hermes, a write
    goes through a link to its target. Returns the (key, value) pairs written, in order."""
    written = []

    def read(home):
        try:
            return json.loads((home / "config.yaml").read_text())
        except FileNotFoundError:
            return {}

    def write_key(home, key, value):
        written.append((key, value))
        config = section = read(home)
        *parents, last = key.split(".")
        for name in parents:
            if not isinstance(section.get(name), dict):
                section[name] = {}
            section = section[name]
        section[last] = value
        (home / "config.yaml").write_text(json.dumps(config))

    for name, effect in (("read_profile_config", read), ("write_profile_config_key", write_key)):
        patch = mock.patch.object(api, name, side_effect=effect)
        patch.start()
        test.addCleanup(patch.stop)
    return written


@contextmanager
def throwaway_deps(base: Path):
    """Point every downloaded-dependency location (toolchain, prepared engine, device CLI receipt, the
    install lock) inside ``base`` for the duration, instead of the real hermretro home."""
    cache = Path(base) / ".cache"
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(paths, "DEPS_ROOT", cache))
        stack.enter_context(mock.patch.object(paths, "PREPARED_ENGINE", cache / f"engine-{paths.ENGINE_IDENTITY}"))
        stack.enter_context(
            mock.patch.object(paths, "DEVICE_CLI_RECEIPT", cache / f"device-cli-{paths.ENGINE_IDENTITY}.json")
        )
        stack.enter_context(mock.patch.object(paths, "setup_root", lambda: cache / "toolchain"))
        yield cache


class FakeBrokerClient:
    """A connected broker client (``backend/broker/client.py``) stand-in: a context manager whose ``request(message)``
    and ``call(owner, tool, args, **options)`` record what they were sent (``asked``, ``calls``) and answer ``answer``
    (a dict, or a function given what was sent). Patch it in with ``mock.patch.object(hermes_host, "try_connect",
    lambda _dir: (client, None))`` or ``mock.patch.object(hermes_host, "ensure_broker", lambda: client)``."""

    hello = {"pid": -1}  # the broker's handshake; -1 is no real process

    def __init__(self, answer=None):
        self.answer, self.asked, self.calls = answer, [], []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def _reply(self, *sent, **options):
        return self.answer(*sent, **options) if callable(self.answer) else self.answer

    def request(self, message):
        self.asked.append(message)
        return self._reply(message)

    def call(self, *args, **options):
        self.calls.append(args)
        return self._reply(*args, **options)


def registered_hook(name: str, ctx=None):
    """The callback the plugin registers for the Hermes hook ``name``: one feature's, or the chain of every
    feature that hooks it (backend/hermes/declare.py), built from the ``backend`` modules tests patch."""
    from backend.features import FEATURES
    from backend.hermes import declare

    return declare.collect("backend", FEATURES).hook(name, ctx)


def encode_png(width, height, pixel):
    """A plain 8-bit RGBA PNG whose pixel at (x, y) is ``pixel(x, y)``."""
    import struct
    import zlib

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    rows = b"".join(b"\0" + bytes(value for x in range(width) for value in pixel(x, y)) for y in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


# A 160x144 pixel-art cover: four colours in bands.
COVER = encode_png(
    160,
    144,
    lambda x, y: ((40, 120, 60, 255), (230, 160, 60, 255), (60, 90, 200, 255), (250, 250, 240, 255))[
        (x // 40 + y // 36) % 4
    ],
)


def complete_card(root: Path) -> None:
    """Give a test project a finished game card (game.json + cover.png)."""
    (root / "cover.png").write_bytes(COVER)
    (root / "game.json").write_text(
        json.dumps(
            {
                "version": 1,
                "title": "Space Game",
                "tagline": "Fly a tiny ship through a meteor field.",
                "description": "Dodge meteors, grab fuel cells and reach the space station before your tank runs dry.",
                "genres": ["Arcade"],
                "cover": "cover.png",
            }
        )
    )


TILE = encode_png(8, 8, lambda x, y: (40, 120, 60, 255) if (x + y) % 2 else (250, 250, 240, 255))  # a valid image


def add_images(root: Path, count: int, folder: str = "sprites", prefix: str = "image") -> list[Path]:
    """Put ``count`` pictures (``TILE``, a real 8x8 PNG) in ``root/assets/<folder>/`` as ``<prefix>000.png``,
    ``<prefix>001.png``... (sorted as numbered) and return them: what ``project_images`` and the ``assets`` RPC list (``folder``: ``sprites``, ``backgrounds``, ``ui`` or
    ``fonts``). No ``.gbsres`` sidecar, so each is named by its file stem; write ``<image>.png.gbsres`` (JSON with a
    ``name``) beside one for a sidecar name."""
    where = root / "assets" / folder
    where.mkdir(parents=True, exist_ok=True)
    images = [where / f"{prefix}{index:03d}.png" for index in range(count)]
    for image in images:
        image.write_bytes(TILE)
    return images


def write_web_manifest(web_dir: Path, rom: str = "rom/game.gbc") -> None:
    """The record the engine writes into a web export it made (``.codex-web-build.json``): the ROM and
    ``index.html`` with their current hashes, so ``games.engine_made_export`` takes the folder as the engine's."""
    files = [
        {"path": relative, "sha256": hashlib.sha256((web_dir / relative).read_bytes()).hexdigest()}
        for relative in ("index.html", rom)
    ]
    manifest = {"version": 1, "builder": "gb-studio-cli", "indexPath": "index.html", "romPath": rom, "files": files}
    (web_dir / ".codex-web-build.json").write_text(json.dumps(manifest))


def make_project(base: Path, name="Space Game", web=True, built=True, card=True) -> Path:
    root = base / name.lower().replace(" ", "-")
    (root / "project").mkdir(parents=True)
    (root / f"{root.name}.gbsproj").write_text(json.dumps({"_resourceType": "project", "name": name}))
    (root / "project" / "scene.gbsres").write_text("{}")
    if built:
        (root / "build").mkdir()
        (root / "build" / "game.gbc").write_bytes(b"\1" * 512)  # the canonical ROM, which the web copy plays
    if web:
        web_dir = root / "build" / "web"
        (web_dir / "js").mkdir(parents=True)
        (web_dir / "rom").mkdir()
        (web_dir / "rom" / "game.gbc").write_bytes(b"\1" * 512)
        (web_dir / "js" / "binjgb.wasm").write_bytes(b"\0asm-test")
        (web_dir / "index.html").write_text("<html><head></head><body></body></html>")
        (web_dir / "gbstudio.json").write_text(json.dumps({"rom": "rom/game.gbc", "project": {"name": name}}))
        write_web_manifest(web_dir)
    if card:
        complete_card(root)
    old = time.time() - 600
    for path in root.rglob("*"):
        os.utime(path, (old, old))
    for rom in root.glob("build/**/*.gb*"):
        os.utime(rom, (old + 300, old + 300))
    return root


def recorded_build(root: Path, **fields) -> dict:
    """The library's record of a successful build of ``root`` as it stands (``lastBuild``), as the broker writes it:
    the ROM's time and hash and the sources' digest; ``fields`` override any of them."""
    rom = root / "build" / "game.gbc"
    return {
        "t": rom.stat().st_mtime,
        "ok": True,
        "rom": str(rom),
        "sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
        "sources": freshness.source_digest(root),
        "error": None,
        **fields,
    }


def record_build(root: Path, **fields) -> dict:
    """Register ``root`` in the library with ``recorded_build(root, **fields)`` as its last build (call
    ``isolated_home(self)`` first); returns the library entry."""
    return hermes_host._registry().upsert(str(root), build=recorded_build(root, **fields))


def make_library_game(
    home: SimpleNamespace,
    name: str = "Game",
    *,
    built: bool = True,
    web: bool = True,
    card: bool = True,
    chat: str | None = None,
    recorded: bool = True,
) -> tuple[str, Path]:
    """A game in the library, as the gateway records one: ``make_project(paths.games_dir(), name, ...)`` (a
    ``.gbsproj``, a scene, a built ROM and web export, a finished card) registered with ``host._registry().upsert``.
    ``home`` is what ``isolated_home(self)`` returns. ``built``, ``web`` and ``card`` are ``make_project``'s, with its
    defaults: by default the game is ready to present; ``web=False`` gives one with no playable copy,
    ``card=False`` one without a card (``built=False`` leaves out the native ROM, ``recorded=False`` only the
    broker's record of building it). Returns ``(game id, project
    root)`` either way (the id is always there); ``host._game_root(id)`` answers the root. Registering never reaches
    the broker (and the isolated runtime folder has none), so nothing else needs patching. Pictures for the assets
    RPC: ``add_images(root, count)``. ``chat`` binds the game to that conversation id (in this profile): a game's
    tools act on it only from its own conversation."""
    for folder in (paths.library_dir(), paths.games_dir()):
        assert Path(folder).is_relative_to(home.base), f"call isolated_home(self) first, unpatched: {folder}"
    root = make_project(paths.games_dir(create=True), name, web=web, built=built, card=card)
    entry = hermes_host._registry().upsert(str(root), build=recorded_build(root) if built and recorded else None)
    assert entry is not None and entry.get("id"), f"the library did not register {root}"
    if chat is not None:
        hermes_host._registry().bind(entry["id"], chat, hermes_host._profile_identity())
    return entry["id"], root


# -- games installed from a link (backend/library/installs.py) ------------------------------------

NINTENDO_LOGO = bytes.fromhex(
    "ceed6666cc0d000b03730083000c000d0008111f8889000edccc6ee6ddddd999bbbb67636e0eecccdddc999fbbb9333e"
)


def make_rom(size: int = 32 * 1024, *, colour: bool = True, kind: int = 0x1E, ram: int = 4, fill: int = 0) -> bytes:
    """A Game Boy ROM with a whole, valid cartridge header (logo, sizes, both checksums): what GB Studio writes."""
    rom = bytearray([fill & 0xFF]) * size
    rom[0x104:0x134] = NINTENDO_LOGO
    rom[0x134:0x13D] = b"TESTGAME\0"
    rom[0x143] = 0x80 if colour else 0x00
    rom[0x147], rom[0x149] = kind, ram
    rom[0x148] = max(0, (size // (32 * 1024)).bit_length() - 1)
    checksum = 0
    for byte in rom[0x134:0x14D]:
        checksum = (checksum - byte - 1) & 0xFF
    rom[0x14D] = checksum
    rom[0x14E] = rom[0x14F] = 0
    total = sum(rom) & 0xFFFF
    rom[0x14E], rom[0x14F] = total >> 8, total & 0xFF
    return bytes(rom)


def git(cwd: Path, *args: str) -> str:
    """Run git in a test repository, with none of the developer's own git configuration."""
    import subprocess

    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    config = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "init.defaultBranch=main"]
    config += ["-c", f"core.hooksPath={os.devnull}", "-c", "commit.gpgSign=false"]
    result = subprocess.run(
        ["git", *config, *args], cwd=cwd, env=environment, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def make_game_folder(
    root: Path,
    *,
    source: bool = False,
    identifier: str = "ab" * 16,
    title: str = "Space Game",
    rom: bytes | None = None,
) -> Path:
    """A published game's files in ``root``: the card (with ``identifier`` and the ROM's ``romSha256``), the cover and
    ``build/game.gbc`` (``rom``, else ``make_rom()``), and with ``source`` its ``.gbsproj`` and ``project/`` too."""
    rom = make_rom() if rom is None else rom
    (root / "build").mkdir(parents=True, exist_ok=True)
    (root / "build" / "game.gbc").write_bytes(rom)
    (root / "cover.png").write_bytes(COVER)
    card = {
        "version": 1,
        "id": identifier,
        "title": title,
        "tagline": "Fly a tiny ship through a meteor field.",
        "description": "Dodge meteors, grab fuel cells and reach the space station before your tank runs dry.",
        "genres": ["Arcade"],
        "cover": "cover.png",
        "gameVersion": "0.1.0",
        "rom": "build/game.gbc",
        "romSha256": hashlib.sha256(rom).hexdigest(),
    }
    (root / "game.json").write_text(json.dumps(card, indent=2))
    (root / "CHANGELOG.md").write_text("# Changelog\n")
    if source:
        (root / "project").mkdir(exist_ok=True)
        (root / "space-game.gbsproj").write_text(json.dumps({"_resourceType": "project", "name": title}))
        (root / "project" / "scene.gbsres").write_text("{}")
    return root


def make_game_repo(base: Path, name: str = "space-game", **game) -> tuple[Path, str]:
    """A git repository holding a published game (``make_game_folder``), committed on ``main``. Returns the repository
    folder and its ``file://`` link."""
    repo = base / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    make_game_folder(repo, **game)
    commit_all(repo, "First version")
    return repo, repo.resolve().as_uri()


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")
