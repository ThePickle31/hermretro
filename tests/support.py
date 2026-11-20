"""Shared test helpers. Tests must never touch the developer's real Hermes home or hermretro's folder in it.

``isolated_home(self)`` in a test's setUp moves both at once: ``HERMRETRO_HOME`` (games, library, broker) and
Hermes's plugin data folder (``backend.hermes.host._data_dir()``: history snapshots, asset versions, frames),
which ``HERMRETRO_HOME`` alone does not move. ``throwaway_profile`` patches only the plugin data folder,
``throwaway_deps`` the downloads (fixed at import, so ``HERMRETRO_HOME`` does not move them either).
``python tools/check.py unit`` fails when the suite writes anything into the home folder.

Import these as ``from tests.support import ...``: putting tests/ itself on sys.path makes tests/backend shadow
the real backend package (tests/repo/test_test_imports.py refuses it)."""

import json
import os
import shutil
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    base = Path(tmp.name).resolve()
    home, data = base / "hermretro", base / "profile" / "plugin-data" / "hermretro"
    data.mkdir(parents=True)
    # Its own runtime folder, short enough for the broker socket wherever the temp base is (paths falls back
    # to the shared /tmp/hermretro-<uid> for a deep home, and an inherited HERMRETRO_RUNTIME_DIR would win).
    runtime = tempfile.mkdtemp(prefix="hrt-", dir="/tmp")
    test.addCleanup(shutil.rmtree, runtime, ignore_errors=True)
    environ = {key: value for key, value in os.environ.items() if key not in FOLDER_OVERRIDES}
    environ.update(HERMRETRO_HOME=str(home), HERMRETRO_RUNTIME_DIR=runtime)
    for patch in (
        mock.patch.dict(os.environ, environ, clear=True),
        throwaway_profile(base),
    ):
        patch.start()
        test.addCleanup(patch.stop)
    return SimpleNamespace(base=base, home=home, data=data, runtime=Path(runtime))


def throwaway_profile(base: Path):
    """Patch hermes_host's view of Hermes storage so this plugin's data folder is inside ``base``.

    The data folder's profile home (``base/profile``) is where hermes_host looks for the session
    database, so chat titles and session lookups read nothing real either. Returns the patch (start it,
    or use it as a context manager); Hermes itself does not need to be importable."""
    data = Path(base) / "profile" / "plugin-data" / "hermretro"
    return mock.patch.object(hermes_host, "_data_dir", lambda: data)


@contextmanager
def throwaway_deps(base: Path):
    """Point every downloaded-dependency location (toolchain, prepared engine, device CLI receipt, the
    install lock) inside ``base`` for the duration, instead of the real hermretro home."""
    cache = Path(base) / ".cache"
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(paths, "DEPS_ROOT", cache))
        stack.enter_context(mock.patch.object(paths, "PREPARED_ENGINE", cache / f"engine-{paths.ENGINE_VERSION}"))
        stack.enter_context(
            mock.patch.object(paths, "DEVICE_CLI_RECEIPT", cache / f"device-cli-{paths.ENGINE_VERSION}.json")
        )
        stack.enter_context(mock.patch.object(paths, "setup_root", lambda: cache / "toolchain"))
        yield cache


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


def make_project(base: Path, name="Space Game", web=True, built=True, card=True) -> Path:
    root = base / name.lower().replace(" ", "-")
    (root / "project").mkdir(parents=True)
    (root / f"{root.name}.gbsproj").write_text(json.dumps({"_resourceType": "project", "name": name}))
    (root / "project" / "scene.gbsres").write_text("{}")
    if built:
        (root / "build").mkdir()
        (root / "build" / "project.gb").write_bytes(b"\0" * 512)
    if web:
        web_dir = root / "build" / "web"
        (web_dir / "js").mkdir(parents=True)
        (web_dir / "rom").mkdir()
        (web_dir / "rom" / "game.gbc").write_bytes(b"\1" * 512)
        (web_dir / "js" / "binjgb.wasm").write_bytes(b"\0asm-test")
        (web_dir / "index.html").write_text("<html><head></head><body></body></html>")
        (web_dir / "gbstudio.json").write_text(json.dumps({"rom": "rom/game.gbc", "project": {"name": name}}))
    if card:
        complete_card(root)
    old = time.time() - 600
    for path in root.rglob("*"):
        os.utime(path, (old, old))
    for rom in root.glob("build/**/*.gb*"):
        os.utime(rom, (old + 300, old + 300))
    return root


def make_library_game(home: SimpleNamespace, name: str = "Game") -> tuple[str, Path]:
    """A game in the library, as the gateway records one: ``make_project(paths.games_dir(), name)`` (a
    ``.gbsproj``, a scene, a built ROM and web export, a finished card) registered with ``host._registry().upsert``.
    ``home`` is what ``isolated_home(self)`` returns. Returns ``(game id, project root)``; ``host._game_root(id)``
    answers the root. Registering never reaches the broker (and the isolated runtime folder has none), so nothing
    else needs patching."""
    for folder in (paths.library_dir(), paths.games_dir()):
        assert Path(folder).is_relative_to(home.base), f"call isolated_home(self) first, unpatched: {folder}"
    root = make_project(paths.games_dir(create=True), name)
    entry = hermes_host._registry().upsert(str(root))
    assert entry is not None and entry.get("id"), f"the library did not register {root}"
    return entry["id"], root
