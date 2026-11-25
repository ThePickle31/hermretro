# backend/setup

Preparing the machine and the studio profile: the page's toolchain install and its progress (`progress.py`), its
journal, failure hints, free-space check and cancel settling (`recovery.py`), ModRetro's CLI, the prepared engine copy (one per engine, never changed once made; made anew with no download when the bundled engine changes) and removing downloads (`provision.py`), reusing another install's toolchain cache (`seed.py`), the `hermretro` profile (`studio_profile.py`), keeping it on the installing profile's model providers (`provider_sync.py`, run after setup by `studio_providers.py`) and its Claude login for the DirectSDK provider (`claude_login.py`), and the Setup page's RPCs (`rpcs.py`).

## What it adds

- RPCs (`rpcs.py`): `status`, `doctor`, `activity`, `studio_profile`, `studio_claude_sign_in`, `install` (`status`, `start`, `cancel`), `remove_tools`.
- Tools (`tools.py`): `chromatic_studio_device_cli`.
- Hooks (`hooks.py`): `pre_tool_call` — asks before downloading ModRetro's CLI (chained after the Hermes layer's hardware approvals).
- Folder sizes: `download_bytes(root)` (`progress.py`) counts only the engine's `downloads/` and `cache/` under a
  toolchain root (the install's progress, polled by the broker); `folder_bytes(path)` (`provision.py`) counts a whole
  file or folder tree, links not followed (what removing the tools freed).
- Events emitted: `setup.tools_removed`, `setup.studio_profile_ready`. Listens to: none.

## Front door

`backend.setup`: `install_progress`, `download_bytes`, `folder_bytes`, `seed_toolchain_cache`, `select_engine` (the engine a new worker starts from, after rebuilding a stale prepared copy), and from `recovery.py`
`write_journal`, `read_journal`, `recovered_install`, `classify`, `explain`, `foreign_lock_hint`, `free_space`,
`settled`, `lock_path`, `lock_started`, `worker_left`, `activity_mark` (used by the broker). Standard library only: the broker imports it, so it never imports `rpcs.py`, `tools.py`, `hooks.py` or `studio_profile.py`.

## Tests

`tests/backend/setup/`. They reach into `provision.py` by these private names, so a split of `provision.py` keeps them on `provision` (imported back into it) or updates the tests in the same change: `provision._node_platform` (patched with `mock.patch.object(provision, "_node_platform", ...)` in `test_status_and_first_run.py` and `tests/backend/system/test_host_os.py`, and called), `provision.subprocess` (its `run` patched, so `provision.py` must keep calling `subprocess.run` through its own `subprocess` import), `provision._node`, `provision._platform_of` (its `cache_clear()`), `provision._pins` and `provision._RUST_TARGETS` (`test_provision.py`), `provision._prepare`, `provision._pins`, `provision._lock`, `provision._node` (patched) and `provision._NOT_REUSABLE` (its `clear()`) (`test_prepared_refresh.py`). `grep -rn "provision\._\|provision\.subprocess" tests/` lists them.

## Adding here

- an RPC: add the `@rpc("<name>")` handler in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `.agents/skills/hermretro-dev-architecture/references/contract.md` section and this README's line, then run `node tools/bundle/bundle.mjs` (it regenerates `page/app/rpc-names.js`). RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses.
- a tool: add the schema, handler and `Tool(...)` entry (with its `step_words`) in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, a `.agents/skills/hermretro-dev-architecture/references/contract.md` line and this README's line (`tests/repo/test_lockstep.py`'s opening comment lists what must agree). A tool about the selected game takes a `project` argument and resolves it with `tool_project` from `backend/hermes/tool_args.py` (test it with a temp project and a missing one).
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: declare `"setup.<name>"` in this front door's `EVENTS` and a function in `emits.py` that emits it (call it where it happens), its test, the `.agents/skills/hermretro-dev-architecture/references/contract.md` row and this README's line. Work that finishes in the broker (the toolchain install, `_run_install` in `backend/broker/install.py`) cannot emit, as the broker never emits: emit from the Hermes-side RPC that sees it finish (the `install` RPC's `status` answers `install.state` `done` with `started_at` and `finished_at`), once per install (keyed by its `started_at`), not on every poll.
- changing an event's payload: edit the `emit("setup.<name>", ...)` call in `rpcs.py` (or `emits.py`'s function, when it has one), the `EVENTS` description in `__init__.py` (each key with what it holds and its type), the `.agents/skills/hermretro-dev-architecture/references/contract.md` events row and `tests/backend/setup/test_event_<name>.py` when the event has one.
- a listener (reacting to another feature's event): add the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `.agents/skills/hermretro-dev-architecture/references/contract.md` row's "Heard by" cell and the feature's row in `.agents/skills/hermretro-dev-architecture/references/architecture.md`. A listener logs with `host.logger` (`from ..hermes import host`), in every feature: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`); what stays standard library only is a front door the broker imports (`backend.library`, `backend.setup`: their `__init__.py` and what it imports), which never imports `listeners.py` or `backend.hermes`. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`), not in module state.
