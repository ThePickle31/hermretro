# backend/hermes

The Hermes layer: the one door to Hermes itself (`api.py`, every Hermes name in `USED`), how features declare what they add (`declare.py`), the helpers every feature's Hermes side shares and the engine tool handler (`host.py`), the engine's pinned tool contracts (`contracts.py`), result shaping (`results.py`) and the helpers any feature's tool uses (`tool_args.py`: `tool_error`, `tool_project`). Importing it hands Hermes's answer for its home to `backend.system` (`__init__.py`).

Edit Build instructions in `workflow.py`. The system prompt, per-game hook and engine results share its wording. Bundling derives the Desktop fallback for older backends from its two start modes. The bundle watch rebuilds it when `workflow.py` changes. The studio personality lives in `profile/SOUL.md`.

## What it adds

- RPCs: none.
- Tools (`tools.py`): the 85 engine tools from `engine/pins/<version>/tools.json`, each as `chromatic_<name>`.
- Hooks (`hooks.py`): `pre_tool_call` (hardware approvals), `subagent_start`, `subagent_stop`.
- Skills and the prompt section (`prompt.py`): every `skills/<name>/SKILL.md`, the `hermretro.guide` section.
- Events: none.

## Front door

A shared layer: features import `backend.hermes.host` (shared helpers, called as `host.<name>` so one test patch reaches every module), `backend.hermes.declare` and `backend.hermes.tool_args`. The layer itself reaches features only through their front doors. Hermes is imported only in `api.py`.

## Tests

`tests/backend/hermes/`; registration as a whole: `tests/backend/hermes/test_registration.py`.

## Adding here

- an RPC: add the `@rpc("<name>")` handler in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `.agents/skills/hermretro-dev-architecture/references/contract.md` section and this README's line, then run `node tools/bundle/bundle.mjs` (it regenerates `page/app/rpc-names.js`). RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses.
- a tool: a plugin-owned tool belongs to the feature that does the work (for example `library`), not here. This layer's `TOOLS` is a function building the engine tools from the pin; a tool of this layer itself is a hand edit to `TOOLS()` in `backend/hermes/tools.py` (its `Tool(...)` in the list it returns), plus every place `tests/repo/test_lockstep.py`'s opening comment lists.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: this front door (`__init__.py`) has no `EVENTS` dict yet: add `EVENTS: dict[str, str] = {}` to `backend/hermes/__init__.py` first (as `backend/player/__init__.py` has it), then declare `"hermes.<name>"` there and a function in `emits.py` that emits it (call it where it happens), its test, the `.agents/skills/hermretro-dev-architecture/references/contract.md` row and this README's line.
- a listener (reacting to another feature's event): add the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `.agents/skills/hermretro-dev-architecture/references/contract.md` row's "Heard by" cell and the feature's row in `.agents/skills/hermretro-dev-architecture/references/architecture.md`. A listener logs with `host.logger` (`from . import host`), in every feature: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`); what stays standard library only is a front door the broker imports (`backend.library`, `backend.setup`: their `__init__.py` and what it imports), which never imports `listeners.py` or `backend.hermes`. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`), not in module state.

Registration (`__init__.register` at the repository root) collects every feature's declarations in `backend/features.py` order: RPCs in every profile, the rest only in the `hermretro` profile.
