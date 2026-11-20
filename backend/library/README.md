# backend/library

The games library: the user's games (`games.py`, `games.json` under the hermretro home), each game's card (`game_card.py`: `game.json` + `cover.png`), the Build page's game ↔ conversation binding, the Games/Build/Emulator page RPCs (`rpcs.py`), the plugin's game tools (`tools.py`) and the helpers every tool shares (`tool_args.py`).

## What it adds

- RPCs (`rpcs.py`): `games`, `game_thumb`, `player`, `presentations`, `captures`, `capture_image`, `build`.
- Tools (`tools.py`): `chromatic_present_game`, `chromatic_game_info`, `chromatic_build_report`.
- Hooks (`hooks.py`): `pre_llm_call` — tells a game's Build conversation which game it works on.
- Events emitted: `library.build_reported` (`game`: the game's id, `None` when the chat has no project; `assets`: the images the card shows, which assets keeps), `library.game_presented`. Listens to: none.

## Front door

`backend.library`: `Registry`, `game_id`, `valid_id`, `cover_path`, `project_file`, `has_web_export`, `web_dir`, `web_rom`, `file_sha256`, `read_json`, `SELECTORS`, `PNG_MAGIC`. Standard library only (the broker and the player import it).

## Tests

`tests/backend/library/`.

## games.json

`<hermretro home>/library/games.json` (`paths.library_dir()`, `HERMRETRO_LIBRARY_DIR` overrides; `Registry`), written under `games.lock` and replaced atomically. Unknown top-level keys are kept. Times are Unix seconds (floats).

- `version`: `1`.
- `games`: game id (`game_id(root)`: the first 12 hex digits of SHA-1 over the real project path; `valid_id` accepts exactly that) → entry:
  - `id`, `projectRoot` (the real path), `title` (the `.gbsproj` name, else the web export's, else the folder name), `kind` (`gbstudio` with a `.gbsproj`, else `gbdk`).
  - `addedAt`: when the library first recorded the game. Never changes.
  - `updatedAt`: the last time the library recorded something about the game: the broker saw it created or selected (`project_create`, `project_create_blank`, `project_select`), built (`rom_build`) or exported (`web_preview` open), or `chromatic_present_game` showed it (`Registry.upsert` and `Registry.present`; each `games` RPC also adds projects the running broker has selected that the library lacks, setting it only for those). Binding a conversation, editing the game card or a thumbnail does not change it. The Games page lists games newest `updatedAt` first: this is what "recent" means. Nothing records when the user opened a game.
  - `chat`: `{conversationId, sessionId, profile}` of the chat that last selected, created (with `select`), built, exported or presented it (the seeded entries carry only `sessionId`).
  - `lastBuild`: the last `rom_build` the broker saw: `{t, ok, rom (path or null), sha256 (or null), error (240 characters at most, or null)}`.
  - `lastWebExport`: `{t}` of the last successful `web_preview` open (the engine may reuse an export without rewriting it).
  - `presented`: `{t, note}` of the last `chromatic_present_game` (`note` may be null).
  - `session`: the game's Build conversation, `{storedId, profile, createdAt, aliases}` (`aliases`: up to 16 later session ids of it, since compression rotates them). Absent when the game has none.
- `presentations`: the last 100 presentations, oldest first: `{gameId, t, note, title, sessionId, conversationId, profile}`.
- `pending`: pending builds, the Build page's New Game conversations whose project does not exist yet, stored id → `{storedId, profile, createdAt, name, plan}` (the newest 50 are kept: `games.MAX_PENDING`; `docs/dev/STUDIO-PAGES.md`, "Binding (`games.json`)", states it too, and `tests/repo/test_lockstep.py` keeps both in step with it). Written by the `build` RPC's `start` (`Registry.build_start`) and removed by its `cancel` (`Registry.build_cancel`) or when the conversation's first project claims it (`claim_pending`).

Thumbnails are `<library>/thumbs/<id>.png`; the card is the project's own `game.json` and `cover.png` (`game_card.py`).

## Project files

What the plugin reads from a GB Studio project (the engine writes them; `backend/assets/sprites.py` `_project_index` reads them for the Build page's assets):

- `<root>/project/scenes/<folder>/scene.gbsres`: one scene, a JSON object with its `name` and `id` (and `_index`, its order); its actors are `<root>/project/scenes/<folder>/actors/*.gbsres`.
- `<root>/project/settings.gbsres`: the project's settings (JSON).
- `<root>/project/palettes/*.gbsres` (`id`, `colors`) and the sidecars `<root>/assets/sprites/*.gbsres` and `<root>/assets/backgrounds/*.gbsres` (`id`; the image is the same name without `.gbsres`).

## Adding here

Use `python tools/retrodev new <kind> library <name>`: it writes the stub, its test, the docs and the registry lines, rebuilds the generated files and runs the checks; there are no hand steps.

- an RPC: `python tools/retrodev new rpc library <name>`.
- card state: `game_card.status(root, strict=True)` answers `{complete, missing, problems, cover}` and
  `game_card.next_step(missing)` the sentence telling the agent what to fill in. `game_card.scaffold(root, title)` writes a
  starter card (title only) when there is none; every other card change is saved by `game_card.update(root, fields,
  cover_source=..., build_sha=..., default_title=...)`, called only by `chromatic_game_info` (`tools.py`).
- a tool: `python tools/retrodev new tool library <name> --step "<running>" "<done>"`. A tool that acts on the current game takes the project from `tool_args.tool_project(tool, args, kwargs)` (the `project` argument, else this chat's), answers failures with `tool_args.tool_error(message, code)` and reads the library with `host._registry()` (`from ..hermes import host`, looked up at call time so tests can patch it). Import them from `tool_args.py`, never from `tools.py` (they live in `backend/hermes/tool_args.py`, which other features' tools import).
- an event: `python tools/retrodev new event library <what happened> --payload "<keyword arguments>"`, then call `emits.<what happened>(...)` (`from . import emits`: the function it writes in `emits.py`) where it happens.
- a listener: `python tools/retrodev new listener library <feature>.<event>`: an `@on("<feature>.<event>")` stub taking `**_payload` (so a new payload field never breaks it) in this folder's `listeners.py`, its test, "Listens to" above and the CONTRACT events row's "Heard by". A listener reaches the library with `host._registry()` and logs with `host.logger` (`from ..hermes import host`), as a tool does: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`). What stays standard library only is the front door, `__init__.py` and the modules it imports (the broker imports it): never import `listeners.py`, `tools.py` or `backend.hermes` there. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`, as `games.json` is), not in module state.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
