# backend/broker

The per-user broker process (`python -m backend.broker`): the single authority over engine workers, project writers and the hardware gate (`broker.py`, `lane.py`, `control.py`, `install.py` (the desktop page's toolchain install: start, MCP cancel, stall
watch, journal), `server.py`, `engine.py`, `leases.py`), and the client the gateway uses to reach it (`client.py`). Standard library only, no Hermes: `tests/repo/test_broker_imports.py` walks everything it imports. The broker never emits events (their listeners live in the gateway).

After Node discovery, the client bounds broker startup, including replacement. It also bounds handshakes, status and install start and cancel acknowledgements. An install start carries a deadline on the host's monotonic clock. The broker checks it under the install lock and acknowledges the admitted run without reading progress from disk. It still accepts the Unix-millisecond deadline older gateways send. Lane status allows the engine to complete its 15-second session probe. Engine tool calls use their own execution budgets.

## What it adds

- RPCs, tools, hooks: none (the setup RPCs and the engine tool handler call it).
- Events emitted: none. Listens to: none.

## Front door

`backend.broker`: `ensure_broker`, `try_connect`, `request_shutdown`, `BrokerUnavailable` and its subclasses `BrokerNotRunning` and `OtherCopyBusy`. `BrokerNotRunning` means the socket was missing or refused the connection. The broker itself imports other features only through their front doors (`backend.library`, `backend.setup`), which therefore stay stdlib-only. Read `tests/backend/broker/test_broker_socket.py` before changing the socket protocol.

## Tests

`tests/backend/broker/`; the real-engine run: `tests/acceptance/`.

## Adding here

The broker declares no RPCs, tools, hooks, events or listeners (it stays standard library only, outside Hermes);
the gateway's features reach it only through this front door.

- an RPC, a tool or an event that needs the broker: declare it in a gateway-side feature (`backend/setup/`,
  `backend/library/`, or the one it belongs to),
  and have its handler call the broker through `backend.broker` (`ensure_broker`, `try_connect`).
- a new broker operation: add it on the broker side and a client function in `client.py`, export that from this
  front door, and cover it in `tests/backend/broker/` (read `test_broker_socket.py` first).
