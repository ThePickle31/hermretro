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

- an RPC: a factory `@rpc("name") def rpc_name(ctx)` in `rpcs.py` (returns the handler `(params, **kwargs)` answering `{ok, ...}`, never raising); then name it in `page/app/rpc.js` and describe it in `docs/dev/CONTRACT.md`, and refresh `tests/repo/registration.json` (`python tests/repo/test_registration_snapshot.py --write`).
- a tool: a schema dict and a handler in `tools.py`, added to `TOOLS` as `Tool(SCHEMA, handler, step_words=(running, done))` (`None` hides the step); then list it under `provides_tools` in `plugin.yaml`, give it the same words in `page/pages/build/transcript/step-words.js`, describe it in `docs/dev/CONTRACT.md` and refresh `tests/repo/registration.json`.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: declare it in this front door's `EVENTS` (`"<feature>.<what happened>": "payload"`), call `emit("<feature>.<what happened>", **payload)` where it happens; other features react in their own `listeners.py` with `@on(...)`.
