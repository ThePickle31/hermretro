"""A Broker with no sockets and no engine: only the coordination state its tests drive.

`fields` sets what a test needs on top of the base (the selected lane state, the library registry,
the install state). A missing attribute then fails loudly in the test that forgot it.
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import Broker  # noqa: E402 - the repository root goes on sys.path first


def bare_broker(**fields):
    broker = Broker.__new__(Broker)
    broker.lanes, broker.writer_leases = {}, {}
    broker.table_lock = threading.RLock()
    broker.events = []
    broker.trace = lambda **record: broker.events.append(record)
    for name, value in fields.items():
        setattr(broker, name, value)
    return broker
