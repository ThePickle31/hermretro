# backend/hermes

The Hermes layer: the one door to Hermes itself (`api.py`, every Hermes name in `USED`), how features declare what they add (`declare.py`), the helpers every feature's Hermes side shares and the engine tool handler (`host.py`), the engine's pinned tool contracts (`contracts.py`) and result shaping (`results.py`). Importing it hands Hermes's answer for its home to `backend.system` (`__init__.py`).

## What it adds

- RPCs: none.
- Tools (`tools.py`): the 81 engine tools from `engine/pins/<version>/tools.json`, each as `chromatic_<name>`.
- Hooks (`hooks.py`): `pre_tool_call` (hardware approvals), `subagent_start`, `subagent_stop`.
- Skills and the prompt section (`prompt.py`): every `skills/<name>/SKILL.md`, the `hermretro.guide` section.
- Events: none.

## Front door

A shared layer: features import `backend.hermes.host` (shared helpers, called as `host.<name>` so one test patch reaches every module) and `backend.hermes.declare`. The layer itself reaches features only through their front doors. Hermes is imported only in `api.py`.

## Tests

`tests/backend/hermes/`; registration as a whole: `tests/repo/test_registration_snapshot.py`.

## Adding here

- an RPC: a factory `@rpc("name") def rpc_name(ctx)` in `rpcs.py` (returns the handler `(params, **kwargs)` answering `{ok, ...}`, never raising); then name it in `page/app/rpc.js` and describe it in `docs/dev/CONTRACT.md`, and refresh `tests/repo/registration.json` (`python tests/repo/test_registration_snapshot.py --write`).
- a tool: a schema dict and a handler in `tools.py`, added to `TOOLS` as `Tool(SCHEMA, handler, step_words=(running, done))` (`None` hides the step); then list it under `provides_tools` in `plugin.yaml`, give it the same words in `page/pages/build/transcript/step-words.js`, describe it in `docs/dev/CONTRACT.md` and refresh `tests/repo/registration.json`.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: declare it in this front door's `EVENTS` (`"<feature>.<what happened>": "payload"`), call `emit("<feature>.<what happened>", **payload)` where it happens; other features react in their own `listeners.py` with `@on(...)`.

Registration (`__init__.register` at the repository root) collects every feature's declarations in `backend/features.py` order: RPCs in every profile, the rest only in the `hermretro` profile.
