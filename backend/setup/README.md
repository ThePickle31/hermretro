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

- an RPC: `python tools/retrodev new rpc setup <name>` writes the `@rpc("<name>")` stub in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `docs/dev/CONTRACT.md` section and this README's line, then regenerates `page/app/rpc-names.js` and `tests/repo/registration.json`. RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses.
- a tool: `python tools/retrodev new tool setup <name> --step "<while it runs>" "<once done>"` writes the schema, handler and `Tool(...)` entry in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, the `docs/dev/CONTRACT.md` line and counts and this README's line, then refreshes the snapshot. For a tool about the selected game add `--project` (a `project` argument, the handler resolving it with `tool_project` from `backend/hermes/tool_args.py`, a test with a temp project and a missing one; `tools/retrodev/README.md`).
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: `python tools/retrodev new event setup <name> --payload "..."` declares `"setup.<name>"` in this front door's `EVENTS`, writes the function in `emits.py` that emits it (call it where it happens), its test, the `docs/dev/CONTRACT.md` row and this README's line.
- a listener (reacting to another feature's event): `python tools/retrodev new listener setup <feature>.<event>` writes the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `docs/dev/CONTRACT.md` row's "Heard by" cell and the feature's row in `docs/dev/ARCHITECTURE.md`. A listener logs with `host.logger` (`from ..hermes import host`), in every feature: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`); what stays standard library only is a front door the broker imports (`backend.library`, `backend.setup`: their `__init__.py` and what it imports), which never imports `listeners.py` or `backend.hermes`. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`), not in module state.
