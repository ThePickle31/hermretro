# backend/history

Build history: after each successful build of a library game, a snapshot of its files (`snapshots.py`, pure functions over paths), listed and restored from the Build page.

Only successful builds are kept here; whether each build passed is recorded by the library (`games.json` `lastBuild.ok`, `backend/library/README.md`).

## What it adds

- RPCs (`rpcs.py`): `builds`, `build_restore`.
- Tools: none.
- Hooks (`hooks.py`): `post_tool_call` — after a successful `chromatic_rom_build` of a library game, keeps a snapshot (chained after assets' `post_tool_call`).
- Events emitted: `history.build_kept`. Listens to: none.

- Data: `<plugin data dir>/snapshots/<game>/<ms>/` (`host._data_dir()`, the profile's Hermes plugin data folder, not the hermretro home; `<ms>` is the build's time in Unix milliseconds). Only folders whose names are all digits are listed and pruned (the newest 30 are kept); other per-game files may sit beside them. In tests, `isolated_home(self)` from `tests/support.py` moves this folder.

## What `build_restore` answers

- `ok: false` with a `code`: `NO_GAME` (not a library game, or its folder is gone), `MISSING` (that build is no longer
  kept) or `TOO_LARGE` (the current files could not be kept first) mean nothing was restored. `ERROR` is an
  unexpected failure (logged); it can come after files were already changed.
- `ok: true` means the restore ran: the current files were kept as the `before-restore` snapshot `backup`, then
  `removed` files the build lacked were deleted and `changed` files were written back (`restored` is the build's id).
  It does not mean every file came back: `problems`, present only when something was skipped, lists the first 20
  `"<relative path>: <reason>"` lines for files that could not be deleted or written (a link or a file in the way, an
  OS error). Those files are as they were before the restore; the rest are restored.
- The Build page treats any `ok: true` as restored (it does not show `problems`) and asks the agent to build again.
  `snapshots.restore` (`snapshots.py`) makes this answer and `tests/backend/history/test_snapshots.py` tests it; its
  `docs/dev/CONTRACT.md` table row lists the same keys ("Build history (snapshots)" there says how files come back).

## Front door

`backend.history` exports nothing.

## Tests

`tests/backend/history/`: `test_snapshots.py` (the snapshots, the `post_tool_call` hook, and the `builds` / `build_restore` RPC tests), `test_snapshot_limits.py` (the limits `docs/dev/CONTRACT.md` states are the ones enforced), `test_event_build_kept.py` (the event).

## Adding here

- an RPC: add the `@rpc("<name>")` handler in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `docs/dev/CONTRACT.md` section and this README's line, then run `node tools/bundle/bundle.mjs` (it regenerates `page/app/rpc-names.js`). RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses. An RPC about one game takes `game` (its library id) and answers `{ok: false, code: "NO_GAME"}` when `host._game_root(game)` is `None`, as `builds` does; its test gets a game from `make_library_game(isolated_home(self))` (`tests/support.py`).
- a tool: add the schema, handler and `Tool(...)` entry (with its `step_words`) in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, a `docs/dev/CONTRACT.md` line and this README's line (`tests/repo/test_lockstep.py`'s opening comment lists what must agree). A tool about the selected game takes a `project` argument and resolves it with `tool_project` from `backend/hermes/tool_args.py` (test it with a temp project and a missing one).
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`. On `post_tool_call`, assets' `keep_inspected_images` must run before history's `snapshot_after_build` (the images a build looked at are kept before the snapshot): that relative order is the rule, pinned by `tests/backend/history/test_snapshots.py`, and a callback added before, between or after them keeps it. A hook reads an engine tool's result with `host.tool_result_payload(result)` and finds the library game it touched with `host.library_game_for(paths)` (`backend/hermes/host.py`).
- an event: declare `"history.<name>"` in this front door's `EVENTS` and a function in `emits.py` that emits it (call it where it happens), its test, the `docs/dev/CONTRACT.md` row and this README's line.
- changing an event's payload: edit `emits.py`'s function (and its call in `hooks.py`), the `EVENTS` description in `__init__.py` (each key with what it holds and its type, e.g. `root=<the real project folder, pathlib.Path>`), the `docs/dev/CONTRACT.md` events row and `tests/backend/history/test_event_<name>.py`.
- a listener (reacting to another feature's event): add the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `docs/dev/CONTRACT.md` row's "Heard by" cell and the feature's row in `docs/dev/ARCHITECTURE.md`. A listener logs with `host.logger` (`from ..hermes import host`), in every feature: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`); what stays standard library only is a front door the broker imports (`backend.library`, `backend.setup`: their `__init__.py` and what it imports), which never imports `listeners.py` or `backend.hermes`. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`), not in module state.
