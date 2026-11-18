"""Tests for the development CLI (tools/retrodev). The package imports as `retrodev`, as __main__.py does."""

import sys
from pathlib import Path

TOOLS = str(Path(__file__).resolve().parents[2] / "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)


def load_tests(loader, standard_tests, pattern):
    """Discovery (python tools/check.py unit): the package's parallel tests share one thread pool."""
    from tests.retrodev.pool import one_pool

    found = loader.discover(start_dir=str(Path(__file__).resolve().parent), pattern=pattern or "test*.py")
    standard_tests.addTests(one_pool(found))
    return standard_tests
