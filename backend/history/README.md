# backend/history

Build history: after each successful build of a library game, a snapshot of its files (`snapshots.py`, pure functions over paths), listed and restored from the Build page.

## What it adds

- RPCs (`rpcs.py`): `builds`, `build_restore`.
- Tools: none.
- Hooks (`hooks.py`): `post_tool_call` — after a successful `chromatic_rom_build` of a library game, keeps a snapshot (chained after assets' `post_tool_call`).
- Events emitted: `history.build_kept`. Listens to: none.

## Front door

`backend.history` exports nothing.

## Tests

`tests/backend/history/`.

## Adding here

- an RPC: a factory `@rpc("name") def rpc_name(ctx)` in `rpcs.py` (returns the handler `(params, **kwargs)` answering `{ok, ...}`, never raising); then name it in `page/app/rpc.js` and describe it in `docs/dev/CONTRACT.md`, and refresh `tests/repo/registration.json` (`python tests/repo/test_registration_snapshot.py --write`).
- a tool: a schema dict and a handler in `tools.py`, added to `TOOLS` as `Tool(SCHEMA, handler, step_words=(running, done))` (`None` hides the step); then list it under `provides_tools` in `plugin.yaml`, give it the same words in `page/pages/build/transcript/step-words.js`, describe it in `docs/dev/CONTRACT.md` and refresh `tests/repo/registration.json`.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: declare it in this front door's `EVENTS` (`"<feature>.<what happened>": "payload"`), call `emit("<feature>.<what happened>", **payload)` where it happens; other features react in their own `listeners.py` with `@on(...)`.
