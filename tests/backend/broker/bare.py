"""A Broker with no sockets and no engine: only the coordination state its tests drive.

`fields` sets what a test needs on top of the base (the selected lane state, the library registry,
the install state). A missing attribute then fails loudly in the test that forgot it.
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import Broker  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.lifecycle import Notices  # noqa: E402 - the repository root goes on sys.path first


def bare_broker(**fields):
    broker = Broker.__new__(Broker)
    broker.stopping = threading.Event()
    broker.lanes, broker.writer_leases = {}, {}
    broker.retiring, broker.retire_started, broker.running = False, 0.0, 0
    broker.table_lock = threading.RLock()
    broker.settled = threading.Condition(broker.table_lock)
    broker.events = []
    broker.trace = lambda **record: broker.events.append(record)
    for name, value in fields.items():
        setattr(broker, name, value)
    # Kept notices are read from the run folder a test gives (state_dir); with none, there are none.
    broker.notices = Notices(fields.get("state_dir", Path("/nonexistent-hermretro-run")))
    return broker


class EngineStub:
    def __init__(self, root):
        self.root, self.calls = root, []

    def call_tool(self, tool, arguments, timeout=None):
        self.calls.append((tool, arguments))
        if tool == "session_status":
            return {"structuredContent": {"projectRoot": str(self.root), "projectPath": arguments}}
        return {"content": [], "structuredContent": {"success": True, "projectRoot": str(self.root)}}
