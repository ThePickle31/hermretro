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

- an RPC: `python tools/retrodev new rpc history <name>` writes the `@rpc("<name>")` stub in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `docs/dev/CONTRACT.md` section and this README's line, then regenerates `page/app/rpc-names.js` and `tests/repo/registration.json`. RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses.
- a tool: `python tools/retrodev new tool history <name> --step "<while it runs>" "<once done>"` writes the schema, handler and `Tool(...)` entry in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, the `docs/dev/CONTRACT.md` line and counts and this README's line, then refreshes the snapshot.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: `python tools/retrodev new event history <name> --payload "..."` declares `"history.<name>"` in this front door's `EVENTS`, writes the function in `emits.py` that emits it (call it where it happens), its test, the `docs/dev/CONTRACT.md` row and this README's line.
- a listener (reacting to another feature's event): `@on("<feature>.<event>")` on a function in this feature's `listeners.py` (`backend/system/events.py`), by hand: `retrodev new` has no listener kind yet.
