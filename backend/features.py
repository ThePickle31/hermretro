"""The backend features, in registration order: one line each.

The plugin's ``__init__.register`` collects what each feature declares (rpcs.py, tools.py, hooks.py,
prompt.py; see backend/hermes/declare.py) in this order, and events (backend/system/events.py) load each
feature's listeners.py in this order. Adding a feature: make ``backend/<name>/`` (front door ``__init__.py``
with ``__all__`` and ``EVENTS``, README.md) and add its line here.
"""

FEATURES = [
    "hermes",  # the engine tools, approval and subagent hooks, skills and the prompt section
    "setup",  # the Setup page: toolchain, removal, the studio profile, ModRetro's CLI
    "library",  # games, the Build binding, the player and captures, the plugin's game tools
    "assets",  # game images: kept versions, the asset viewer
    "history",  # build snapshots and restoring them
    "player",  # the loopback player server (no declarations; used through its front door)
    "broker",  # the broker process (no declarations; used through its front door)
]
