"""hermretro's Python backend, one folder per feature (backend/features.py lists them in registration order).

Each feature declares what it adds to Hermes in its own folder (rpcs.py, tools.py, hooks.py; see
backend/hermes/declare.py), exposes what other features may use in its front door (``__init__.py``,
``__all__``) and the events it emits (``EVENTS``), and reacts to other features in listeners.py.
backend/system and backend/hermes are shared layers. tests/repo/test_boundaries.py checks how features connect;
everything the broker imports stays standard-library only (tests/repo/test_broker_imports.py).
"""
