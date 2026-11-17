# backend/player

The browser player: ModRetro's real web player served from a loopback server in the gateway process (`server.py`), for the page's emulator and `chromatic_present_game`; game captures and the demo cartridge.

## What it adds

- RPCs, tools, hooks: none (the library's `player`, `captures` and `capture_image` RPCs use it).
- Events emitted: none. Listens to: none.

## Front door

`backend.player`: `get_server`, `game_build`, `demo_build`, `DEMO`, `DEMO_ID`, `is_demo`, `demo_captures_root`, `list_captures`, `save_capture`, `PlayerError`. Standard library only.

## Tests

`tests/backend/player/`.

## Adding here

- an RPC: a factory `@rpc("name") def rpc_name(ctx)` in `rpcs.py` (returns the handler `(params, **kwargs)` answering `{ok, ...}`, never raising); then name it in `page/app/rpc.js` and describe it in `docs/dev/CONTRACT.md`, and refresh `tests/repo/registration.json` (`python tests/repo/test_registration_snapshot.py --write`).
- a tool: a schema dict and a handler in `tools.py`, added to `TOOLS` as `Tool(SCHEMA, handler, step_words=(running, done))` (`None` hides the step); then list it under `provides_tools` in `plugin.yaml`, give it the same words in `page/pages/build/transcript/step-words.js`, describe it in `docs/dev/CONTRACT.md` and refresh `tests/repo/registration.json`.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: declare it in this front door's `EVENTS` (`"<feature>.<what happened>": "payload"`), call `emit("<feature>.<what happened>", **payload)` where it happens; other features react in their own `listeners.py` with `@on(...)`.
