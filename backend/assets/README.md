# backend/assets

Game images for the Build page: the asset viewer's RPCs (`rpcs.py`), how a project shows a sprite or background (`sprites.py`), and the kept versions of each image (`versions.py`), so a reply keeps showing the image it showed even after the file is rewritten.

## What it adds

- RPCs (`rpcs.py`): `asset`, `asset_info`, `asset_restore`, `assets`.
- Tools: none.
- Hooks (`hooks.py`): `post_llm_call` — keeps images a reply delivered; `post_tool_call` — keeps images a tool looked at (runs before build history's snapshot).
- Events emitted: `assets.image_restored`. Listens to (`listeners.py`): `library.build_reported` — keeps the images a build card shows.

## Front door

`backend.assets` exports nothing; other features reach it through events.

## Tests

`tests/backend/assets/`.

## Adding here

- an RPC: `python tools/retrodev new rpc assets <name>` writes the `@rpc("<name>")` stub in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `docs/dev/CONTRACT.md` section and this README's line, then regenerates `page/app/rpc-names.js` and `tests/repo/registration.json`. RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses.
- a tool: `python tools/retrodev new tool assets <name> --step "<while it runs>" "<once done>"` writes the schema, handler and `Tool(...)` entry in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, the `docs/dev/CONTRACT.md` line and counts and this README's line, then refreshes the snapshot.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: `python tools/retrodev new event assets <name> --payload "..."` declares `"assets.<name>"` in this front door's `EVENTS`, writes the function in `emits.py` that emits it (call it where it happens), its test, the `docs/dev/CONTRACT.md` row and this README's line.
- a listener (reacting to another feature's event): `python tools/retrodev new listener assets <feature>.<event>` writes the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `docs/dev/CONTRACT.md` row's "Heard by" cell and the feature's row in `docs/dev/ARCHITECTURE.md`. A listener logs with `host.logger` (`from ..hermes import host`): listeners run only in the gateway, where Hermes is loaded (the broker never loads them; only a standard-library-only feature such as `library` uses `logging.getLogger(__name__)` instead).
