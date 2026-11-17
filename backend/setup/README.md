# backend/setup

Preparing the machine and the studio profile: the page's toolchain install and its progress (`progress.py`), ModRetro's CLI and removing downloads (`provision.py`), the `hermretro` profile (`studio_profile.py`) and the Setup page's RPCs (`rpcs.py`).

## What it adds

- RPCs (`rpcs.py`): `status`, `doctor`, `activity`, `studio_profile`, `install`, `remove_tools`.
- Tools (`tools.py`): `chromatic_studio_device_cli`.
- Hooks (`hooks.py`): `pre_tool_call` — asks before downloading ModRetro's CLI (chained after the Hermes layer's hardware approvals).
- Events emitted: `setup.tools_removed`, `setup.studio_profile_ready`. Listens to: none.

## Front door

`backend.setup`: `install_progress`, `directory_bytes`, `seed_toolchain_cache` (used by the broker). Standard library only: the broker imports it, so it never imports `rpcs.py`, `tools.py`, `hooks.py` or `studio_profile.py`.

## Tests

`tests/backend/setup/`.

## Adding here

- an RPC: a factory `@rpc("name") def rpc_name(ctx)` in `rpcs.py` (returns the handler `(params, **kwargs)` answering `{ok, ...}`, never raising); then name it in `page/app/rpc.js` and describe it in `docs/dev/CONTRACT.md`, and refresh `tests/repo/registration.json` (`python tests/repo/test_registration_snapshot.py --write`).
- a tool: a schema dict and a handler in `tools.py`, added to `TOOLS` as `Tool(SCHEMA, handler, step_words=(running, done))` (`None` hides the step); then list it under `provides_tools` in `plugin.yaml`, give it the same words in `page/pages/build/transcript/step-words.js`, describe it in `docs/dev/CONTRACT.md` and refresh `tests/repo/registration.json`.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: declare it in this front door's `EVENTS` (`"<feature>.<what happened>": "payload"`), call `emit("<feature>.<what happened>", **payload)` where it happens; other features react in their own `listeners.py` with `@on(...)`.
