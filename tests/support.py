"""Shared test helpers. Tests must never touch the developer's real Hermes home or hermretro's folder in it:
patch Hermes storage with ``throwaway_profile``, downloads with ``throwaway_deps``, and point
``HERMRETRO_HOME`` (or ``HERMRETRO_LIBRARY_DIR`` / ``HERMRETRO_RUNTIME_DIR`` / ``HERMRETRO_GAMES_DIR``) at a temp
folder. ``python tools/check.py unit`` fails when the suite writes anything into the home folder."""

from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock

from backend.hermes import host as hermes_host
from backend.system import paths


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
