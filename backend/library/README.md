# backend/library

- `games.py` owns registry storage, file locking and broker observations. `bindings.py` handles Build conversation
  ownership, session aliases, pending New Game records and the game's linked chat.
- `thumbnails.py` reads title-screen thumbnails and decodes PNG uploads.
- `project.py` handles game IDs, reads project titles, settings, the game's ROM and build files. `freshness.py` says
  whether the playable copy is the current game (`export_freshness`, `source_digest`, `sources_newer_than`).
- `shelf.py` assembles shelf entries and the smaller game object used by the emulator.
- `game_card.py` reads and writes `game.json`. `game_cover.py` validates `cover.png`.
- `rpcs.py`, `hooks.py` and `tools.py` connect the library to the page and Hermes.

## What it adds

- RPCs (`rpcs.py`): `games`, `game_build_status`, `game_thumb`, `player`, `presentations`, `captures`, `capture_image`, `build`.
- Tools (`tools.py`): `chromatic_present_game`, `chromatic_game_info`, `chromatic_build_report`.
- Hooks (`hooks.py`): `pre_llm_call` — tells a game's Build conversation which game it works on.
- Events emitted: `library.build_reported` (`game`: the game's id, `None` when the chat has no project; `assets`: the images the card shows, which assets keeps), `library.game_presented`. Listens to: none.

## Front door

`backend.library`: `Registry`, `game_id`, `valid_id`, `cover_path`, `project_file`, `has_web_export`, `web_dir`, `web_rom`, `file_sha256`, `read_json`, `SELECTORS`, `PNG_MAGIC`. Standard library only (the broker and the player import it).

## Tests

`tests/backend/library/`.

Read-only paths use `host.try_connect` to reach an already running broker. The tests use
`FakeBrokerClient` from `tests/support.py` and guard against starting the broker or invoking the engine.

## games.json

`<hermretro home>/library/games.json` (`paths.library_dir()`, `HERMRETRO_LIBRARY_DIR` overrides; `Registry`), written under `games.lock` and replaced atomically. Unknown top-level keys are kept. Times are Unix seconds (floats). An absent file starts an empty registry. A read or parse failure prevents replacement.

- `version`: `1`.
- `games`: game id (`game_id(root)`: the first 12 hex digits of SHA-1 over the real project path; `valid_id` accepts exactly that) → entry:
  - `id`, `projectRoot` (the real path), `title` (the `.gbsproj` name, else the web export's, else the folder name), `kind` (`gbstudio` with a `.gbsproj`, else `gbdk`).
  - `addedAt`: when the library first recorded the game. Never changes.
  - `updatedAt`: the last time the library recorded something about the game: the broker saw it created or selected (`project_create`, `project_create_blank`, `project_select`), built (`rom_build`) or exported (`web_preview` open), or `chromatic_present_game` showed it (`Registry.upsert` and `Registry.present`; each `games` RPC also adds projects the running broker has selected that the library lacks, setting it only for those). Binding a conversation, editing the game card or a thumbnail does not change it. The Games page lists games newest `updatedAt` first: this is what "recent" means. Nothing records when the user opened a game.
  - `chat`: `{conversationId, sessionId, profile}` of the chat that last selected, created (with `select`), built, exported or presented it (the seeded entries carry only `sessionId`).
  - `lastBuild`: the last `rom_build` the broker saw: `{t, ok, rom (path or null), sha256 (or null), error (`games.ERROR_CHARS`, 240, characters at most, or null)}`.
  - `lastWebExport`: `{t, sources}` of the last successful `web_preview` open into the game's own `build/web` (the engine may reuse an export without rewriting it); `sources` is `project.source_digest` of the `.gbsproj`, `project/`, `assets/` and `plugins/` at that moment, which `export_freshness` compares with the current one.
  - `presented`: `{t, note}` of the last `chromatic_present_game` (`note` may be null).
  - `initialPlan`: the mode recorded when New Game first bound the project. True for Plan first, false for Build it.
    Kept across conversation changes. An older entry can still carry the mode in its session. For an older
    conversation without a saved mode, Studio looks for planning files written after it was bound and checks
    for activity that predates it.
  - `session`: the game's Build conversation, `{storedId, profile, createdAt, aliases, plan?, edit?}` (`aliases`:
    up to 16 later session ids of it, since compression rotates them, `plan`: true when it began with Plan first,
    `edit`: true when Edit opened a game with no recorded New Game mode). Absent when the game has none.
- `presentations`: the last 100 presentations, oldest first: `{gameId, t, note, title, sessionId, conversationId, profile}`.
- `pending`: pending builds, the Build page's New Game conversations whose project does not exist yet, stored id → `{storedId, profile, createdAt, name, plan}` (the newest `games.MAX_PENDING` are kept). Written by the `build` RPC's `start` (`Registry.build_start`) and removed by its `cancel` (`Registry.build_cancel`) or when the conversation's first project claims it (`claim_pending`).

`Registry.load()["games"]` holds raw entries, including games whose folders are gone. The registry key determines
the game id used by the shelf, chat bindings, and thumbnails. The `games` RPC reads one snapshot for seeding,
the games, pending conversations, and chat ownership. It skips registered broker lane roots and rereads the
snapshot after attempting to register a missing root under lock. `Registry.library_listing()` returns the games
described through `shelf.describe` in descending `updatedAt` order and the IDs of unreadable entries.
The emulator checks one game through `game_build_status`, including whether its project is unavailable or gone.
That RPC reads the build files and chat link, while shelf descriptions also inspect source timestamps and card
files. A recorded native ROM path that cannot be read does not invalidate a healthy web ROM. The shelf keeps a
game whose web ROM cannot be read, with `web: null`, and `game_build_status` reports `UNAVAILABLE` if the export
exists but its ROM cannot be read. Card display validation and image encoding share a cache based on the cover file's identity. Presentation
validates the current cover and checks for copies from `assets/` on every call.

Automatic capture fills a missing thumbnail once. Thumbnails are `<library>/thumbs/<id>.png`; the card is the project's own `game.json` and `cover.png` (`game_card.py`).

Which title the user sees: the card's `title` (the project's `game.json`, set by `chromatic_game_info`; `game_card.scaffold` writes a starter card with the project's name), which the `games` RPC answers as `displayTitle` and the pages show (`game.displayTitle || game.title`). The registry's and the RPC's `title` is the project's own name (`project.project_title`: the `.gbsproj` name, else the web export's, else the stored title or folder name).

## The game's ROM

Every build of a project writes one ROM, `project.canonical_rom(root)` (front door `canonical_rom`): `build/game.gbc`,
or `build/game.gb` when `project/settings.gbsres` says `colorMode: "mono"`. The broker sets `chromatic_rom_build`'s
`outputPath` to it and refuses any other (`game_rom_arguments` in `backend/broker/broker.py`, code `ROM_PATH`); a
standalone C build (`sourcePath`) is not a project build. The engine writes that ROM's bytes into the web export of the
same sources (`engine/CHANGES.md`), so `export_freshness` counts a copy that plays other bytes as stale, except in a
project with batteryless saves on, whose web copy GB Studio compiles without them. The shelf's
`rom` is that file; a game last built before it existed falls back to `lastBuild.rom`, then to the web export's ROM.
Other ROMs left in `build/` are never the game.

## Captures

Screenshots and videos saved from the player live in `<project>/captures/` (the demo cartridge's in `<library>/captures/demo`): `captures_dir(root, game_id)` in `backend/player/captures.py` (not in the player's front door) names the folder, and `player.list_captures(root, game_id)` (`from ..player import list_captures`) lists its media files newest first as `{id, path, kind, createdAt, file}` (`kind` from the `.json` sidecar, else `screenshot` for a PNG and `video` otherwise; `createdAt` an ISO time; there is no size field: `stat` the `path`). The `captures` RPC (`rpcs.py`) reads them through `list_captures` and answers `{path, kind, createdAt, url}` for each. Writes go through `save_capture`: the `capture_image` RPC saves a page-sent game-screen PNG there as an `annotation` capture, and the player server's `codex-captures` POST saves the player's own.

## Save states

The player's save states live in `<project>/save-states/<build digest>/<id>.gbstate.json`, written by the engine's
web preview (`engine/modretro-chromatic/dist/web-preview-states.js`, `PreviewStateStore`); the plugin only keeps them
out of source checks and snapshots (`project.NOT_SOURCE`, `backend/history/snapshots.py`). `<build digest>` is the
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
- Captures (screenshots, recordings, the page's annotated images; the plugin writes these, not the engine): media files directly in `<root>/captures/`, listed newest first by `player.list_captures(root, game_id)` and saved by `player.save_capture` (`backend/player/captures.py`). The demo cartridge has no project, so its captures live in `<library>/captures/demo/`. Get the right `root` for any game id with `player.capture_root(game_id, host._game_root)` (None for an unknown game), as the `captures` and `capture_image` RPCs and the player server do.
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
- splitting `tools.py` past 400 lines: each `<name>_tools.py` holds its schemas, handlers and its own `TOOLS = (Tool(...), ...)`, and `tools.py` takes them in with `from . import game_tools`. The `TOOLS` order is the order Hermes registers them in: existing tools moved out keep their places (put `*game_tools.TOOLS` where the moved `Tool(...)` entries were: moving `chromatic_game_info` gives `TOOLS = (Tool(PRESENT_TOOL, ...), *game_tools.TOOLS, Tool(BUILD_REPORT_TOOL, ...))`), and a new tool goes last. A tool module imports `tool_error` and `tool_project` from `tool_args.py`; a name a handler still uses is imported in the module that uses it. Patch dependencies in the module that defines the handler (for example, `mock.patch.object(game_tools, "emit")`).
- an event: declare `"library.<what happened>"` in `EVENTS` (`__init__.py`) with a function in `emits.py` that emits it, and call `emits.<what happened>(...)` (`from . import emits`) where it happens.
- changing an event's payload: edit the `emit("library.<name>", ...)` call in `tools.py` (or `emits.py`'s function, when it has one), the `EVENTS` description in `__init__.py` (each key with what it holds and its type, e.g. `root=<the project folder, str>`), the `.agents/skills/hermretro-dev-architecture/references/contract.md` events row and its test (`tests/backend/library/test_build_report.py` for `library.build_reported`; `tests/backend/library/test_event_<name>.py` for one `new event` wrote), and every listener that reads the key (`backend/assets/listeners.py` hears `library.build_reported`).
- a listener: an `@on("<feature>.<event>")` function taking `**_payload` (so a new payload field never breaks it) in this folder's `listeners.py`, its test, "Listens to" above and the CONTRACT events row's "Heard by". A listener reaches the library with `host._registry()` and logs with `host.logger` (`from ..hermes import host`), as a tool does: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`). What stays standard library only is the front door, `__init__.py` and the modules it imports (the broker imports it): never import `listeners.py`, `tools.py` or `backend.hermes` there. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`, as `games.json` is), not in module state.
- a field in the games RPC answer: `Registry.describe` (`games.py`), the key set pinned by
  `tests/backend/library/test_games.py` (its failure message names these places), the `.agents/skills/hermretro-dev-architecture/references/contract.md` games row
  and the `.agents/skills/hermretro-dev-page/references/player.md` games JSON. `rpcs.py` drops `updatedAt` before answering.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
