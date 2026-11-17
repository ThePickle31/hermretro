"""Events: how one feature lets others react to what it did, without importing them. Stdlib only.

The feature that owns an event declares it in its front door (``EVENTS = {"library.build_reported": "..."}``
in ``backend/<feature>/__init__.py``) and calls ``emit("library.build_reported", assets=[...])`` where it
happens. Another feature reacts from its own ``listeners.py``::

    from ..system.events import on

    @on("library.build_reported")
    def keep_reported_images(assets=(), **_payload): ...

Listeners run in the emitter's thread, in feature order (backend/features.py), with the payload as keyword
arguments. A listener that raises is logged and never breaks the emitter or the other listeners. Each
feature's listeners.py is imported on the first emit. tests/repo/test_boundaries.py checks every emitted or
listened name is declared exactly once. The broker process never emits (it does not load listeners).
"""
from __future__ import annotations

import importlib
import logging
import threading
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

_listeners: dict[str, list[Callable]] = {}
_loaded = False
_load_lock = threading.Lock()
_BACKEND = __package__.rpartition(".")[0]        # "backend", or "<plugin>.backend" inside Hermes


def on(name: str):
    """Listen to the event ``name`` (declared in its owner's front door ``EVENTS``)."""
    def listen(function: Callable):
        _listeners.setdefault(name, []).append(function)
        return function
    return listen


def _load_listeners() -> None:
    global _loaded
    with _load_lock:
        if _loaded:
            return
        _loaded = True
        features = importlib.import_module(f"{_BACKEND}.features").FEATURES
        root = Path(__file__).resolve().parents[1]
        for feature in features:
            if (root / feature / "listeners.py").is_file():
                try:
                    importlib.import_module(f"{_BACKEND}.{feature}.listeners")
                except Exception:
                    logger.exception("hermretro: the listeners of %s could not be loaded", feature)


def emit(name: str, **payload) -> None:
    """Tell every listener of ``name``. Never raises because of a listener."""
    _load_listeners()
    for listener in list(_listeners.get(name, ())):
        try:
            listener(**payload)
        except Exception:
            logger.exception("hermretro: a listener of %s failed", name)
