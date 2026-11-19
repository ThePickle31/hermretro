"""Shared test helpers. Tests must never touch the developer's real Hermes home or hermretro's folder in it.

``isolated_home(self)`` in a test's setUp moves both at once: ``HERMRETRO_HOME`` (games, library, broker) and
Hermes's plugin data folder (``backend.hermes.host._data_dir()``: history snapshots, asset versions, frames),
which ``HERMRETRO_HOME`` alone does not move. ``throwaway_profile`` patches only the plugin data folder,
``throwaway_deps`` the downloads (fixed at import, so ``HERMRETRO_HOME`` does not move them either).
``python tools/check.py unit`` fails when the suite writes anything into the home folder.

Import these as ``from tests.support import ...``: putting tests/ itself on sys.path makes tests/backend shadow
the real backend package (tests/repo/test_test_imports.py refuses it)."""

import os
import shutil
import tempfile
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
