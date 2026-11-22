# backend/player

The browser player: ModRetro's real web player served from a loopback server in the gateway process (`server.py`), for the page's emulator and `chromatic_present_game`; game captures and the demo cartridge.

## What it adds

- RPCs, tools, hooks: none (the library's `player`, `captures` and `capture_image` RPCs use it).
- Events emitted: none. Listens to: none.

## Front door

`backend.player`: `get_server`, `game_build`, `demo_build`, `DEMO`, `DEMO_ID`, `is_demo`, `demo_captures_root`, `capture_root`, `list_captures`, `save_capture`, `PlayerError`. Standard library only.

## Tests

`tests/backend/player/`.

## Adding here

- an RPC: add the `@rpc("<name>")` handler in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `docs/dev/CONTRACT.md` section and this README's line, then run `node tools/bundle/bundle.mjs` (it regenerates `page/app/rpc-names.js`) and `python tests/repo/test_registration_snapshot.py --write`. RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses.
- a tool: add the schema, handler and `Tool(...)` entry (with its `step_words`) in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, the `docs/dev/CONTRACT.md` line and counts and this README's line, then refresh the snapshot (`python tests/repo/test_registration_snapshot.py --write`; `tests/repo/test_lockstep.py`'s opening comment lists every place). A tool about the selected game takes a `project` argument and resolves it with `tool_project` from `backend/hermes/tool_args.py` (test it with a temp project and a missing one).
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: declare `"player.<name>"` in this front door's `EVENTS` and a function in `emits.py` that emits it (call it where it happens), its test, the `docs/dev/CONTRACT.md` row and this README's line.
- a listener (reacting to another feature's event): add the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `docs/dev/CONTRACT.md` row's "Heard by" cell and the feature's row in `docs/dev/ARCHITECTURE.md`. A listener logs with `host.logger` (`from ..hermes import host`), in every feature: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`); what stays standard library only is a front door the broker imports (`backend.library`, `backend.setup`: their `__init__.py` and what it imports), which never imports `listeners.py` or `backend.hermes`. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`), not in module state.
