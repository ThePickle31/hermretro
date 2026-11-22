# backend/library

The games library: the user's games (`games.py`, `games.json` under the hermretro home), each game's card (`game_card.py` for `game.json`, `game_cover.py` for reading and validating `cover.png`), the Build page's game ↔ conversation binding, the Games/Build/Emulator page RPCs (`rpcs.py`), the plugin's game tools (`tools.py`) and the helpers every tool shares (`tool_args.py`).

## What it adds

- RPCs (`rpcs.py`): `games`, `game_thumb`, `player`, `presentations`, `captures`, `capture_image`, `build`.
- Tools (`tools.py`): `chromatic_present_game`, `chromatic_game_info`, `chromatic_build_report`.
- Hooks (`hooks.py`): `pre_llm_call` — tells a game's Build conversation which game it works on.
- Events emitted: `library.build_reported` (`game`: the game's id, `None` when the chat has no project; `assets`: the images the card shows, which assets keeps), `library.game_presented`. Listens to: none.

## Front door

`backend.library`: `Registry`, `game_id`, `valid_id`, `cover_path`, `project_file`, `has_web_export`, `web_dir`, `web_rom`, `file_sha256`, `read_json`, `SELECTORS`, `PNG_MAGIC`. Standard library only (the broker and the player import it).

## Tests

`tests/backend/library/`.

A tool that only reads (no broker start, no engine call) is tested through the two broker seams the library really
uses; there is no `host._broker_call`. `host.try_connect(paths.runtime_dir())` finds a running broker without
starting one (`host._chat_project`, which `tool_project` calls for "this chat's project"; the `games` RPC's
`_seed_library`), and `host.ensure_broker()` starts one (on the library's paths only the engine tool handler,
`host.make_tool_handler`; the setup RPCs call it too).
Answer the first with `FakeBrokerClient` (`tests/support.py`) and make the second fail, as
`test_present_never_reaches_the_engine_or_a_device` (`tests/backend/library/test_games.py`) does:
`mock.patch.object(hermes_host, "try_connect", lambda _dir: (client, None))` and
`mock.patch.object(hermes_host, "ensure_broker", forbidden)`, then assert on `client.asked`. These patches see only
calls made through `backend.hermes.host`; code that imports `backend.broker` or its `client` itself is not covered
(`tests/backend/broker/test_broker_stats_tool.py` patches `backend.broker.client` for that).

## games.json

`<hermretro home>/library/games.json` (`paths.library_dir()`, `HERMRETRO_LIBRARY_DIR` overrides; `Registry`), written under `games.lock` and replaced atomically. Unknown top-level keys are kept. Times are Unix seconds (floats).

- `version`: `1`.
- `games`: game id (`game_id(root)`: the first 12 hex digits of SHA-1 over the real project path; `valid_id` accepts exactly that) → entry:
  - `id`, `projectRoot` (the real path), `title` (the `.gbsproj` name, else the web export's, else the folder name), `kind` (`gbstudio` with a `.gbsproj`, else `gbdk`).
  - `addedAt`: when the library first recorded the game. Never changes.
  - `updatedAt`: the last time the library recorded something about the game: the broker saw it created or selected (`project_create`, `project_create_blank`, `project_select`), built (`rom_build`) or exported (`web_preview` open), or `chromatic_present_game` showed it (`Registry.upsert` and `Registry.present`; each `games` RPC also adds projects the running broker has selected that the library lacks, setting it only for those). Binding a conversation, editing the game card or a thumbnail does not change it. The Games page lists games newest `updatedAt` first: this is what "recent" means. Nothing records when the user opened a game.
  - `chat`: `{conversationId, sessionId, profile}` of the chat that last selected, created (with `select`), built, exported or presented it (the seeded entries carry only `sessionId`).
  - `lastBuild`: the last `rom_build` the broker saw: `{t, ok, rom (path or null), sha256 (or null), error (`games.ERROR_CHARS`, 240, characters at most, or null)}`.
  - `lastWebExport`: `{t, sources}` of the last successful `web_preview` open into the game's own `build/web` (the engine may reuse an export without rewriting it); `sources` is `games.source_digest` of the `.gbsproj`, `project/`, `assets/` and `plugins/` at that moment, which `export_freshness` compares with the current one.
  - `presented`: `{t, note}` of the last `chromatic_present_game` (`note` may be null).
  - `session`: the game's Build conversation, `{storedId, profile, createdAt, aliases}` (`aliases`: up to 16 later session ids of it, since compression rotates them). Absent when the game has none.
- `presentations`: the last 100 presentations, oldest first: `{gameId, t, note, title, sessionId, conversationId, profile}`.
- `pending`: pending builds, the Build page's New Game conversations whose project does not exist yet, stored id → `{storedId, profile, createdAt, name, plan}` (the newest `games.MAX_PENDING` are kept). Written by the `build` RPC's `start` (`Registry.build_start`) and removed by its `cancel` (`Registry.build_cancel`) or when the conversation's first project claims it (`claim_pending`).

Reading it: `Registry.load()["games"]` is the raw entries above (game id → entry), including games whose folder is gone; `Registry.library()` answers the page's game objects (`Registry.describe` of each entry, newest `updatedAt` first), only games whose folder exists, and is slower: it hashes each ROM and web export and reads each card.

Thumbnails are `<library>/thumbs/<id>.png`; the card is the project's own `game.json` and `cover.png` (`game_card.py`).

Which title the user sees: the card's `title` (the project's `game.json`, set by `chromatic_game_info`; `game_card.scaffold` writes a starter card with the project's name), which the `games` RPC answers as `displayTitle` and the pages show (`game.displayTitle || game.title`). The registry's and the RPC's `title` is the project's own name (`games.project_title`: the `.gbsproj` name, else the web export's, else the folder name).

## Captures

Screenshots and videos saved from the player live in `<project>/captures/` (the demo cartridge's in `<library>/captures/demo`): `captures_dir(root, game_id)` in `backend/player/server.py` (not in the player's front door) names the folder, and `player.list_captures(root, game_id)` (`from ..player import list_captures`) lists its media files newest first as `{id, path, kind, createdAt, file}` (`kind` from the `.json` sidecar, else `screenshot` for a PNG and `video` otherwise; `createdAt` an ISO time; there is no size field: `stat` the `path`). The `captures` RPC (`rpcs.py`) reads them through `list_captures` and answers `{path, kind, createdAt, url}` for each. Writes go through `save_capture`: the `capture_image` RPC saves a page-sent game-screen PNG there as an `annotation` capture, and the player server's `codex-captures` POST saves the player's own.

## Save states

The player's save states live in `<project>/save-states/<build digest>/<id>.gbstate.json`, written by the engine's
web preview (`engine/modretro-chromatic/dist/web-preview-states.js`, `PreviewStateStore`); the plugin only keeps them
out of source checks and snapshots (`games.NOT_SOURCE`, `backend/history/snapshots.py`). `<build digest>` is the
SHA-256 of the JSON `{romSha256, runtimeSha256, sourceRevision, cartridgeType}` (so each build has its own folder) and
`<id>` the SHA-256 of the file's canonical text. Each file is one JSON object (`engine/modretro-chromatic/dist/web-annotations/save-state.js`):
`format` (`codex-gb-studio-save-state`), `version` (`1`), `identity` (that build identity), `frame`, `createdAt` (an
ISO time), `title` (160 characters at most), and `state`, `framebuffer`, `sgbFramebuffer`, each `{encoding: "base64",
byteLength, sha256, data}` (1 MiB decoded at most). Each build keeps its newest 8 (`MAX_PREVIEW_STATES`; a save
prunes older ones) and refuses a save once its folder holds 64 entries.

## Project files

What the plugin reads from a GB Studio project (the engine writes them; `backend/assets/sprites.py` `_project_index` reads them for the Build page's assets):

- `<root>/project/scenes/<folder>/scene.gbsres`: one scene, a JSON object with its `name` and `id` (and `_index`, its order); its actors are `<root>/project/scenes/<folder>/actors/*.gbsres`.
- `<root>/project/settings.gbsres`: the project's settings (JSON).
- Captures (screenshots, recordings, the page's annotated images; the plugin writes these, not the engine): media files directly in `<root>/captures/`, listed newest first by `player.list_captures(root, game_id)` and saved by `player.save_capture` (`backend/player/server.py`). The demo cartridge has no project, so its captures live in `<library>/captures/demo/`. Get the right `root` for any game id with `player.capture_root(game_id, host._game_root)` (None for an unknown game), as the `captures` and `capture_image` RPCs and the player server do.
- `<root>/project/palettes/*.gbsres` (`id`, `colors`) and the sidecars `<root>/assets/sprites/*.gbsres` and `<root>/assets/backgrounds/*.gbsres` (`id`; the image is the same name without `.gbsres`).

## Adding here

Every place each piece touches is in `.agents/skills/hermretro-dev-architecture/references/architecture.md`, "Adding things".

- an RPC: an `@rpc("<name>")` handler in `rpcs.py`; one about one game takes a `game` param and answers `NO_GAME` unless `host._game_root` finds it.
- card state: `game_card.status(root, strict=True)` answers `{complete, missing, problems, cover}`,
  `game_card.cover_problem(root, strict=True)` only the cover's problem text by the same rules (None when usable) and
  `game_card.next_step(missing)` the sentence telling the agent what to fill in. `game_card.scaffold(root, title)` writes a
  starter card (title only) when there is none; every other card change is saved by `game_card.update(root, fields,
  cover_source=..., build_sha=..., default_title=...)`, called only by `chromatic_game_info` (`tools.py`). Its result's `was_complete` is the strict completeness before
  the change: `result["status"]["complete"] and not result["was_complete"]` is the moment the card became complete.
- a tool: its schema, handler and `Tool(...)` entry in `tools.py`. A tool that acts on the current game takes the project from `tool_args.tool_project(tool, args, kwargs)` (the `project` argument, else this chat's; a game's Build conversation gets only its own game), answers failures with `tool_args.tool_error(message, code, next_step)` (the next step tells the agent what to do) and reads the library with `host._registry()` (`from ..hermes import host`, looked up at call time so tests can patch it). Import them from `tool_args.py`, never from `tools.py` (they live in `backend/hermes/tool_args.py`, which other features' tools import).
- a game in a test: `make_library_game(isolated_home(self), "<name>")` (`tests/support.py`) is ready to present (a
  ROM, a fresh web copy, a complete card); `web=False` gives one with no playable copy, `card=False` one with no card
  (`built=False` drops only the native ROM), and it answers `(game id, root)` either way
  (`tests/backend/library/test_library_fixture.py`). Pictures for the Assets panel: `add_images(root, count)` writes
  real PNGs into `<root>/assets/sprites/` (`folder="backgrounds"` etc.), as `tests/backend/assets/test_asset_list_limit.py` does.
- a game's `lastBuild` in a test: get the game from `make_library_game(isolated_home(self))` (`tests/support.py`), then record the build the way the broker does, `host._registry().upsert(str(root), build={"t": time.time(), "ok": True, "rom": None, "sha256": None, "error": None})` (`from backend.hermes import host`; `"ok": False` with an `"error"` message for a failed one; `games.Registry(paths.library_dir())` is the same file). `registry.get(game_id)["lastBuild"]` reads it back (`tests/backend/library/test_games.py` writes and reads builds this way with `games.Registry`).
- splitting `tools.py` past 400 lines: each `<name>_tools.py` holds its schemas, handlers and its own `TOOLS = (Tool(...), ...)`, and `tools.py` takes them in with `from . import game_tools`. The `TOOLS` order is the order Hermes registers them in: existing tools moved out keep their places (put `*game_tools.TOOLS` where the moved `Tool(...)` entries were: moving `chromatic_game_info` gives `TOOLS = (Tool(PRESENT_TOOL, ...), *game_tools.TOOLS, Tool(BUILD_REPORT_TOOL, ...))`), and a new tool goes last. A tool module imports `tool_error` and `tool_project` from `tool_args.py`; a name a handler still uses is imported in the module that uses it. A handler looks names up in its own module, so tests import it from there and patch names on that module (`mock.patch.object(game_tools, "emit")`, not on `tools`); its error codes still go in `tool_args.py`'s docstring (`tests/backend/library/test_tool_args.py` reads `tools.py` and every `*_tools.py`).
- an event: declare `"library.<what happened>"` in `EVENTS` (`__init__.py`) with a function in `emits.py` that emits it, and call `emits.<what happened>(...)` (`from . import emits`) where it happens.
- changing an event's payload: edit the `emit("library.<name>", ...)` call in `tools.py` (or `emits.py`'s function, when it has one), the `EVENTS` description in `__init__.py` (each key with what it holds and its type, e.g. `root=<the project folder, str>`), the `.agents/skills/hermretro-dev-architecture/references/contract.md` events row and its test (`tests/backend/library/test_build_report.py` for `library.build_reported`; `tests/backend/library/test_event_<name>.py` for one `new event` wrote), and every listener that reads the key (`backend/assets/listeners.py` hears `library.build_reported`).
- a listener: an `@on("<feature>.<event>")` function taking `**_payload` (so a new payload field never breaks it) in this folder's `listeners.py`, its test, "Listens to" above and the CONTRACT events row's "Heard by". A listener reaches the library with `host._registry()` and logs with `host.logger` (`from ..hermes import host`), as a tool does: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`). What stays standard library only is the front door, `__init__.py` and the modules it imports (the broker imports it): never import `listeners.py`, `tools.py` or `backend.hermes` there. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`, as `games.json` is), not in module state.
- a field in the games RPC answer: `Registry.describe` (`games.py`), the key set pinned by
  `tests/backend/library/test_games.py` (its failure message names these places), the `.agents/skills/hermretro-dev-architecture/references/contract.md` games row
  and the `.agents/skills/hermretro-dev-page/references/player.md` games JSON. `rpcs.py` drops `updatedAt` before answering.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
