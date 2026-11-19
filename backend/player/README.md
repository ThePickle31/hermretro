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

- an RPC: `python tools/retrodev new rpc player <name>` writes the `@rpc("<name>")` stub in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `docs/dev/CONTRACT.md` section and this README's line, then regenerates `page/app/rpc-names.js` and `tests/repo/registration.json`. RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses.
- a tool: `python tools/retrodev new tool player <name> --step "<while it runs>" "<once done>"` writes the schema, handler and `Tool(...)` entry in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, the `docs/dev/CONTRACT.md` line and counts and this README's line, then refreshes the snapshot.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: `python tools/retrodev new event player <name> --payload "..."` declares `"player.<name>"` in this front door's `EVENTS`, writes the function in `emits.py` that emits it (call it where it happens), its test, the `docs/dev/CONTRACT.md` row and this README's line.
- a listener (reacting to another feature's event): `python tools/retrodev new listener player <feature>.<event>` writes the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `docs/dev/CONTRACT.md` row's "Heard by" cell and the feature's row in `docs/dev/ARCHITECTURE.md`. A listener logs with `host.logger` (`from ..hermes import host`): listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so state a listener keeps is per process (the broker never loads them; only a standard-library-only feature such as `library` uses `logging.getLogger(__name__)` instead).
