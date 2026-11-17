"""The broker process (`python -m backend.broker`) and its client. Stdlib only, no Hermes imports.

Front door: the client side other features use to reach the broker.
"""
from .client import BrokerUnavailable, ensure_broker, try_connect

__all__ = ["BrokerUnavailable", "ensure_broker", "try_connect"]

EVENTS: dict[str, str] = {}
