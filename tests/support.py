"""Shared test helpers. Tests must never touch the developer's real Hermes home: patch Hermes storage with
``throwaway_profile`` and point ``HERMRETRO_LIBRARY_DIR`` and ``HERMRETRO_RUNTIME_DIR`` at a temp folder in any
test that reaches the library or the broker's runtime folder."""
from pathlib import Path
from unittest import mock

from adapter import hermes_host


def throwaway_profile(base: Path):
    """Patch hermes_host's view of Hermes storage so this plugin's data folder is inside ``base``.

    The data folder's profile home (``base/profile``) is where hermes_host looks for the session
    database, so chat titles and session lookups read nothing real either. Returns the patch (start it,
    or use it as a context manager); Hermes itself does not need to be importable."""
    data = Path(base) / "profile" / "plugin-data" / "hermretro"
    return mock.patch.object(hermes_host, "_data_dir", lambda: data)
