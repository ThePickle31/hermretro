# backend/broker

The per-user broker process (`python -m backend.broker`): the single authority over engine workers, project writers and the hardware gate (`broker.py`, `lane.py`, `control.py`, `server.py`, `engine.py`, `leases.py`), and the client the gateway uses to reach it (`client.py`). Standard library only, no Hermes: `tests/repo/test_broker_imports.py` walks everything it imports. The broker never emits events (their listeners live in the gateway).

## What it adds

- RPCs, tools, hooks: none (the setup RPCs and the engine tool handler call it).
- Events emitted: none. Listens to: none.

## Front door

`backend.broker`: `ensure_broker`, `try_connect`, `BrokerUnavailable`. The broker itself imports other features only through their front doors (`backend.library`, `backend.setup`), which therefore stay stdlib-only. Read `tests/backend/broker/test_broker_socket.py` before changing the socket protocol.

## Tests

`tests/backend/broker/`; the real-engine run: `tests/acceptance/`.

## Adding here

- an RPC: `python tools/retrodev new rpc broker <name>` writes the `@rpc("<name>")` stub in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `docs/dev/CONTRACT.md` section and this README's line, then regenerates `page/app/rpc-names.js` and `tests/repo/registration.json`. RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses.
- a tool: `python tools/retrodev new tool broker <name> --step "<while it runs>" "<once done>"` writes the schema, handler and `Tool(...)` entry in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, the `docs/dev/CONTRACT.md` line and counts and this README's line, then refreshes the snapshot.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: `python tools/retrodev new event broker <name> --payload "..."` declares `"broker.<name>"` in this front door's `EVENTS`, writes the function in `emits.py` that emits it (call it where it happens), its test, the `docs/dev/CONTRACT.md` row and this README's line.
- a listener (reacting to another feature's event): `@on("<feature>.<event>")` on a function in this feature's `listeners.py` (`backend/system/events.py`), by hand: `retrodev new` has no listener kind yet.

The broker declares no RPCs, tools or hooks itself; expose a client function in the front door instead.
