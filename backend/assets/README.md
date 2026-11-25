# backend/assets

Game images for the Build page: the asset viewer's RPCs (`rpcs.py`), how a project shows a sprite or background (`sprites.py`), where a project keeps its images (`project_files.py`), and the kept versions of each image (`versions.py`), so a reply keeps showing the image it showed even after the file is rewritten.

## What it adds

- RPCs (`rpcs.py`): `asset`, `asset_info`, `asset_restore`, `assets`.
- Tools: none.
- Hooks (`hooks.py`): `post_llm_call` — keeps images a reply delivered; `post_tool_call` — keeps images a tool looked at (runs before build history's snapshot).
- Events emitted: `assets.image_restored`. Listens to (`listeners.py`): `library.build_reported` — keeps the images a build card shows; `library.game_moved` — an installed game's edited copy that became a game of its own takes its images' kept versions to its new folder (`moved.py`).

## Project files

A game's images live in `<root>/assets/<kind>/` (`sprites/`, `backgrounds/`, `ui/`, `fonts/`, subfolders included): mostly `*.png`, each beside its `<image>.gbsres` sidecar (JSON: `id`, `name`, and for a sprite its frame size and animations; `backend/library/README.md` "Project files"). To count or list them, use `project_images(root, kinds=None)` from `project_files.py`: it yields `(path, resolved path, kind)` for each image (`kind` is `sprite`, `background` or `ui`; `kinds={"sprite"}` keeps only sprites), never one outside `root`, e.g. `sum(1 for _ in project_images(root, kinds={"sprite"}))`. The `assets` RPC lists the game's pictures with it.
The walk sorts each directory and enters subdirectories as needed. The RPC loads one index of library folders per
request and matches each image to its deepest owner by filesystem identity, which also handles alternate case
spellings on case-insensitive disks. It stops after finding the first eligible image beyond the cap.

## Kept versions

`versions.py` keeps each version of a game image a reply showed or a step looked at, under the plugin data folder's
`asset-versions/`, filed under the game that owns the image (a folder that later becomes a game of its own starts
with none of the outer game's), up to `ASSET_KEEP_VERSIONS` per image, images up to `ASSET_MAX_BYTES` only.
Older path-only history is adopted when exactly one root owns the image. Version operations take a per-image
file lock across Hermes processes. Restore also uses the engine's project writer lock through Node.js. It keeps
the current bytes and checks the live file's identity, metadata and bytes again immediately before replacement.
A conflict leaves the other writer's work and the existing history in place. Editors that bypass the engine
lock can still write between that final check and rename because POSIX has no conditional rename against a file
revision. Restore protects both the selected version and the backup when applying the cap. Preview applies
the byte limit to the selected file, so a small kept version can still be shown after a larger live replacement.
To count an image's older versions,
use `older_versions(real, root)` (`real` the resolved path, `root` its game from `_image_root(real)`; the current
file is not counted).

## Front door

`backend.assets` exports nothing; other features reach it through events.

## Tests

`tests/backend/assets/test_asset_rpc.py` covers Build page previews, saved frames and nested-game ownership.
`tests/backend/assets/test_asset_restore.py` covers failed backups, the file lock and historical reads after a restore.
`tests/backend/assets/test_asset_list_limit.py` covers ownership, order and the listing cap.

## Adding here

- an RPC: add the `@rpc("<name>")` handler in `rpcs.py` (a factory returning the handler `(params, **kwargs)` that answers `{ok, ...}` and never raises), its test, its `.agents/skills/hermretro-dev-architecture/references/contract.md` section and this README's line, then run `node tools/bundle/bundle.mjs` (it regenerates `page/app/rpc-names.js`). RPC names are global and flat (`plugin.hermretro.<name>`): pick one no other feature uses. An RPC about one game, as `assets` is, takes `game` (the library id) and answers `NO_GAME` when the registry has no project folder for it.
- a tool: add the schema, handler and `Tool(...)` entry (with its `step_words`) in `tools.py`, its test, the `plugin.yaml` line, the Build page's step words, a `.agents/skills/hermretro-dev-architecture/references/contract.md` line and this README's line (`tests/repo/test_lockstep.py`'s opening comment lists what must agree). A tool about the selected game takes a `project` argument and resolves it with `tool_project` from `backend/hermes/tool_args.py` (test it with a temp project and a missing one).
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`. On `post_tool_call`, assets' `keep_inspected_images` must run before history's `snapshot_after_build` (the images a build looked at are kept before the snapshot): that relative order is the rule, pinned by `tests/backend/history/test_snapshots.py`, and a callback added before, between or after them keeps it. A hook reads an engine tool's result with `host.tool_result_payload(result)` and finds the library game it touched with `host.library_game_for(paths)` (`backend/hermes/host.py`).
- an event: declare `"assets.<name>"` in this front door's `EVENTS` and a function in `emits.py` that emits it (call it where it happens), its test, the `.agents/skills/hermretro-dev-architecture/references/contract.md` row and this README's line.
- changing an event's payload: edit the `emit("assets.<name>", ...)` call in `rpcs.py` (or `emits.py`'s function, when it has one), the `EVENTS` description in `__init__.py` (each key with what it holds and its type), the `.agents/skills/hermretro-dev-architecture/references/contract.md` events row and `tests/backend/assets/test_event_<name>.py` when the event has one.
- a listener (reacting to another feature's event): add the `@on("<feature>.<event>")` function in this feature's `listeners.py` (made when missing; `backend/system/events.py` imports it), its test, this README's "Listens to", the `.agents/skills/hermretro-dev-architecture/references/contract.md` row's "Heard by" cell and the feature's row in `.agents/skills/hermretro-dev-architecture/references/architecture.md`. A listener logs with `host.logger` (`from ..hermes import host`), in every feature: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`); what stays standard library only is a front door the broker imports (`backend.library`, `backend.setup`: their `__init__.py` and what it imports), which never imports `listeners.py` or `backend.hermes`. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`), not in module state.
