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


def make_library_game(
    home: SimpleNamespace, name: str = "Game", *, built: bool = True, web: bool = True, card: bool = True
) -> tuple[str, Path]:
    """A game in the library, as the gateway records one: ``make_project(paths.games_dir(), name, ...)`` (a
    ``.gbsproj``, a scene, a built ROM and web export, a finished card) registered with ``host._registry().upsert``.
    ``home`` is what ``isolated_home(self)`` returns. ``built``, ``web`` and ``card`` are ``make_project``'s, with its
    defaults: by default the game is ready to present; ``web=False`` gives one with no playable copy,
    ``card=False`` one without a card (``built=False`` leaves out the native ROM only). Returns ``(game id, project
    root)`` either way (the id is always there); ``host._game_root(id)`` answers the root. Registering never reaches
    the broker (and the isolated runtime folder has none), so nothing else needs patching. Pictures for the assets
    RPC: ``add_images(root, count)``."""
    for folder in (paths.library_dir(), paths.games_dir()):
        assert Path(folder).is_relative_to(home.base), f"call isolated_home(self) first, unpatched: {folder}"
    root = make_project(paths.games_dir(create=True), name, web=web, built=built, card=card)
    entry = hermes_host._registry().upsert(str(root))
    assert entry is not None and entry.get("id"), f"the library did not register {root}"
    return entry["id"], root
