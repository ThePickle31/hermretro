"""The Hermes layer: everything that touches Hermes, and the registration of what each feature declares.

- api.py: the one door to Hermes itself (every Hermes name used, in ``USED``).
- declare.py: how a feature declares its RPCs, tools, hooks, skills and prompt sections.
- host.py: the helpers shared by every feature's Hermes side (data folder, profile, library, broker client,
  the engine tool handler).
- contracts.py, results.py: the engine's pinned tool contracts and result shaping.
- tools.py, hooks.py, prompt.py: what this layer itself declares (the engine tools, the approval and
  subagent hooks, the skills and the prompt section).

Importing this package hands Hermes's own answer for the Hermes home to backend.system (system never imports
Hermes), before anything reads a location. Front door for features: ``backend.hermes.host`` and
``backend.hermes.declare``.
"""
from ..system import hermes_home as _hermes_home
from . import api as _api

_hermes_home.provide(_api.default_hermes_root)

__all__: list[str] = []
