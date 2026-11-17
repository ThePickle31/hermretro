"""How backend.system learns where the Hermes home is, without importing Hermes or backend.hermes.

The Hermes layer hands over its way of asking (``backend/hermes/__init__.py`` calls ``provide`` as it is
imported, before anything reads a location: the plugin's ``__init__`` imports backend.hermes first). Without it
(the broker, tests, tools run outside Hermes) ``asked()`` is None and paths.py falls back to ``HERMES_HOME``.
Stdlib only.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

_ask: Callable[[], Path | None] | None = None


def provide(ask: Callable[[], Path | None]) -> None:
    """Install the function that answers the Hermes home (or None when Hermes cannot say)."""
    global _ask
    _ask = ask


def asked() -> Path | None:
    """The Hermes home as Hermes itself names it, or None when nobody provided a way to ask."""
    return _ask() if _ask is not None else None
