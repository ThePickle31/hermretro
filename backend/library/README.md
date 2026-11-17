# backend/library

The games library: the user's games (`games.py`, `games.json` under the hermretro home), each game's card (`game_card.py`: `game.json` + `cover.png`), the Build page's game ↔ conversation binding, the Games/Build/Emulator page RPCs (`rpcs.py`) and the plugin's game tools (`tools.py`).

## What it adds

- RPCs (`rpcs.py`): `games`, `game_thumb`, `player`, `presentations`, `captures`, `capture_image`, `build`.
- Tools (`tools.py`): `chromatic_present_game`, `chromatic_game_info`, `chromatic_build_report`.
- Hooks (`hooks.py`): `pre_llm_call` — tells a game's Build conversation which game it works on.
- Events emitted: `library.build_reported` (assets keeps the images a build card shows), `library.game_presented`. Listens to: none.

## Front door

`backend.library`: `Registry`, `game_id`, `valid_id`, `cover_path`, `project_file`, `has_web_export`, `web_dir`, `web_rom`, `file_sha256`, `read_json`, `SELECTORS`, `PNG_MAGIC`. Standard library only (the broker and the player import it).

## Tests

`tests/backend/library/`.

## Adding here

- an RPC: a factory `@rpc("name") def rpc_name(ctx)` in `rpcs.py` (returns the handler `(params, **kwargs)` answering `{ok, ...}`, never raising); then name it in `page/app/rpc.js` and describe it in `docs/dev/CONTRACT.md`, and refresh `tests/repo/registration.json` (`python tests/repo/test_registration_snapshot.py --write`).
- a tool: a schema dict and a handler in `tools.py`, added to `TOOLS` as `Tool(SCHEMA, handler, step_words=(running, done))` (`None` hides the step); then list it under `provides_tools` in `plugin.yaml`, give it the same words in `page/pages/build/transcript/step-words.js`, describe it in `docs/dev/CONTRACT.md` and refresh `tests/repo/registration.json`.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
- an event: declare it in this front door's `EVENTS` (`"<feature>.<what happened>": "payload"`), call `emit("<feature>.<what happened>", **payload)` where it happens; other features react in their own `listeners.py` with `@on(...)`.
