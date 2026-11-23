# backend/history

Build history: after each successful build of a library game, a snapshot of its files (`snapshots.py`, pure functions over paths), listed and restored from the Build page.

Only successful builds are kept here; whether each build passed is recorded by the library (`games.json` `lastBuild.ok`, `backend/library/README.md`).

## What it adds

- RPCs (`rpcs.py`): `builds`, `build_restore`.
- Tools: none.
- Hooks (`hooks.py`): `post_tool_call` — after a successful `chromatic_rom_build` of a library game, keeps a snapshot (chained after assets' `post_tool_call`).
- Events emitted: `history.build_kept`. Listens to: none.

- Snapshots live in `<plugin data dir>/snapshots/<game>/<ms>/`, under the profile's Hermes plugin data folder
  (`host._data_dir()`). Numeric snapshot folders use Unix milliseconds and are pruned to the newest 30, with
  the selected snapshot and backup protected during restore. In tests, `isolated_home(self)` from
  `tests/support.py` moves this folder.

A successful ROM build's tool result carries a unique `buildRef`. The history hook adds it to the kept
snapshot's `buildRefs`, including when unchanged files reuse an existing snapshot. The page can match
resumed and live builds exactly. Older records use the actual build times in `builds` and require an
unambiguous occurrence inside the turn.

## What `build_restore` answers

- `NO_GAME`, `MISSING`, `INVALID_SNAPSHOT`, `TOO_LARGE` and `BACKUP_FAILED` are preflight failures. The project
  is untouched. A restore checks the selected build reference or historical occurrence, validates the
  saved file count, bytes and fingerprint, and completes the current project's backup while holding
  the per-game lock through restore and pruning.
- A complete restore returns `{ok: true, restored, backup, changed, removed}`. `PARTIAL` returns
  `ok: false` with those snapshot IDs and counts plus the first 20 file problems. The backed-up files
  remain available. Unexpected errors return `ERROR` and are logged.
- The Build page shows the first file problem for an incomplete restore. It asks the agent to rebuild
  after a complete restore and reports a rebuild submission failure separately.

## Front door

`backend.history` exports nothing.

## Tests

`tests/backend/history/` covers snapshots and builds, restore preflight and partial failures, snapshot
limits, and the `history.build_kept` event.

## Adding here

- an RPC: add the `@rpc("<name>")` handler in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `.agents/skills/hermretro-dev-architecture/references/contract.md` section and this README's line, then run `node tools/bundle/bundle.mjs` (it regenerates `page/app/rpc-names.js`). RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses. An RPC about one game takes `game` (its library id) and answers `{ok: false, code: "NO_GAME"}` when `host._game_root(game)` is `None`, as `builds` does; its test gets a game from `make_library_game(isolated_home(self))` (`tests/support.py`).
- a tool: add the schema, handler and `Tool(...)` entry (with its `step_words`) in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, a `.agents/skills/hermretro-dev-architecture/references/contract.md` line and this README's line (`tests/repo/test_lockstep.py`'s opening comment lists what must agree). A tool about the selected game takes a `project` argument and resolves it with `tool_project` from `backend/hermes/tool_args.py` (test it with a temp project and a missing one).
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`. On `post_tool_call`, assets' `keep_inspected_images` must run before history's `snapshot_after_build` (the images a build looked at are kept before the snapshot): that relative order is the rule, pinned by `tests/backend/history/test_snapshots.py`, and a callback added before, between or after them keeps it. A hook reads an engine tool's result with `host.tool_result_payload(result)` and finds the library game it touched with `host.library_game_for(paths)` (`backend/hermes/host.py`).
- an event: declare `"history.<name>"` in this front door's `EVENTS` and a function in `emits.py` that emits it (call it where it happens), its test, the `.agents/skills/hermretro-dev-architecture/references/contract.md` row and this README's line.
- changing an event's payload: edit `emits.py`'s function (and its call in `hooks.py`), the `EVENTS` description in `__init__.py` (each key with what it holds and its type, e.g. `root=<the real project folder, pathlib.Path>`), the `.agents/skills/hermretro-dev-architecture/references/contract.md` events row and `tests/backend/history/test_event_<name>.py`.
- a listener (reacting to another feature's event): add the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `.agents/skills/hermretro-dev-architecture/references/contract.md` row's "Heard by" cell and the feature's row in `.agents/skills/hermretro-dev-architecture/references/architecture.md`. A listener logs with `host.logger` (`from ..hermes import host`), in every feature: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`); what stays standard library only is a front door the broker imports (`backend.library`, `backend.setup`: their `__init__.py` and what it imports), which never imports `listeners.py` or `backend.hermes`. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`), not in module state.
