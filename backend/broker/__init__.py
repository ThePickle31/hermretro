"""The broker process (`python -m backend.broker`) and its client. Stdlib only, no Hermes imports.

Front door: the client side other features use to reach the broker.
"""

from .client import (
    BrokerNotRunning,
    BrokerRestarting,
    BrokerUnavailable,
    BrokenBroker,
    LegacyBrokerHello,
    OtherCopyBusy,
    ensure_broker,
    request_shutdown,
    try_connect,
)

__all__ = [
    "BrokerNotRunning",
    "BrokerRestarting",
    "BrokerUnavailable",
    "BrokenBroker",
    "LegacyBrokerHello",
    "OtherCopyBusy",
    "ensure_broker",
    "request_shutdown",
    "try_connect",
]

EVENTS: dict[str, str] = {}
