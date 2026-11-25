"""A broker of the releases before retirement, for the acceptance check of the upgrade from one (``update.py``): it
answers ``{"op": "shutdown", "replace": true}`` as a plain shutdown, as those releases do.

    python -m tests.acceptance.legacy_broker --state-dir <run folder> --node <node>
"""

from backend.broker import server
from backend.broker.broker import Broker


def main() -> int:
    control = Broker.control
    Broker.control = lambda broker, request: control(broker, {k: v for k, v in request.items() if k != "replace"})
    return server.main()


if __name__ == "__main__":
    raise SystemExit(main())
