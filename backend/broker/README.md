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

- an RPC: a factory `@rpc("name") def rpc_name(ctx)` in `rpcs.py` (returns the handler `(params, **kwargs)` answering `{ok, ...}`, never raising); then name it in `page/app/rpc.js` and describe it in `docs/dev/CONTRACT.md`, and refresh `tests/repo/registration.json` (`python tests/repo/test_registration_snapshot.py --write`).
- a tool: a schema dict and a handler in `tools.py`, added to `TOOLS` as `Tool(SCHEMA, handler, step_words=(running, done))` (`None` hides the step); then list it under `provides_tools` in `plugin.yaml`, give it the same words in `page/pages/build/transcript/step-words.js`, describe it in `docs/dev/CONTRACT.md` and refresh `tests/repo/registration.json`.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: declare it in this front door's `EVENTS` (`"<feature>.<what happened>": "payload"`), call `emit("<feature>.<what happened>", **payload)` where it happens; other features react in their own `listeners.py` with `@on(...)`.

The broker declares no RPCs, tools or hooks itself; expose a client function in the front door instead.
