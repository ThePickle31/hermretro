"""Build history: after each successful build of a library game a snapshot of its files is kept
(snapshots.py, the post_tool_call hook in hooks.py), and the Build page lists and restores them (rpcs.py).

Front door: nothing is exported.
"""

__all__: list[str] = []

EVENTS = {
    "history.build_kept": "A successful build of a library game was kept as a snapshot; game=<id>, root=<project>",
}
