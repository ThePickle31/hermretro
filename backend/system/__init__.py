"""The machine: locations (paths.py), the Linux/macOS differences and the supported-system check (host.py),
events between features (events.py) and the Hermes home handed over by the Hermes layer (hermes_home.py).
Stdlib only; imports nothing of ours outside itself.

A shared layer: every feature may import its modules directly (``from ..system import paths``).
"""
__all__: list[str] = []
