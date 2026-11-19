# backend/history

Build history: after each successful build of a library game, a snapshot of its files (`snapshots.py`, pure functions over paths), listed and restored from the Build page.

## What it adds

- RPCs (`rpcs.py`): `builds`, `build_restore`.
- Tools: none.
- Hooks (`hooks.py`): `post_tool_call` — after a successful `chromatic_rom_build` of a library game, keeps a snapshot (chained after assets' `post_tool_call`).
- Events emitted: `history.build_kept`. Listens to: none.

- Data: `<plugin data dir>/snapshots/<game>/<ms>/` (`host._data_dir()`, the profile's Hermes plugin data folder, not the hermretro home; `<ms>` is the build's time in Unix milliseconds). Only folders whose names are all digits are listed and pruned (the newest 30 are kept); other per-game files may sit beside them. In tests, `isolated_home(self)` from `tests/support.py` moves this folder.

## Front door

`backend.history` exports nothing.

## Tests

`tests/backend/history/`.

## Adding here

- an RPC: `python tools/retrodev new rpc history <name>` writes the `@rpc("<name>")` stub in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `docs/dev/CONTRACT.md` section and this README's line, then regenerates `page/app/rpc-names.js` and `tests/repo/registration.json`. RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses.
- a tool: `python tools/retrodev new tool history <name> --step "<while it runs>" "<once done>"` writes the schema, handler and `Tool(...)` entry in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, the `docs/dev/CONTRACT.md` line and counts and this README's line, then refreshes the snapshot.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: `python tools/retrodev new event history <name> --payload "..."` declares `"history.<name>"` in this front door's `EVENTS`, writes the function in `emits.py` that emits it (call it where it happens), its test, the `docs/dev/CONTRACT.md` row and this README's line.
- a listener (reacting to another feature's event): `python tools/retrodev new listener history <feature>.<event>` writes the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `docs/dev/CONTRACT.md` row's "Heard by" cell and the feature's row in `docs/dev/ARCHITECTURE.md`. A listener logs with `host.logger` (`from ..hermes import host`): listeners run only in the gateway, where Hermes is loaded (the broker never loads them; only a standard-library-only feature such as `library` uses `logging.getLogger(__name__)` instead).
