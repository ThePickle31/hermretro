# How hermretro is built

hermretro is one Hermes plugin with two halves. The **agent half** (Python, `__init__.py` + `backend/`) gives
the agent the game-making tools; the **page half** (`desktop/plugin.js`, built from `page/`) is the
hermretro page in Hermes Desktop. Underneath both is the **engine**, hermretro's own Chromatic MCP server under
`engine/`, started from ModRetro's 1.0.34 (its changes: `engine/CHANGES.md`; what was left out:
`THIRD_PARTY_NOTICES.md`; the files: `engine/contract/manifest.json`).

```
Hermes gateway (one process, every profile)                 per user, ~/.hermes/hermretro/
 ├─ __init__.register()  tools / skills / hooks / prompt     ├─ games/      the user's projects
 │   (only in the "hermretro" profile)  + page RPCs          ├─ library/    the Games shelf
 └─ backend/hermes/host  ── Unix socket ──►  broker ─────────┼─ .cache/    toolchain + prepared engine
                                              (one per user) └─ run/       socket, token, lock, logs
                                               ├─ engine worker (Node) per conversation lane
                                               └─ player server (loopback) for the page's emulator
```

## Map

Every folder in the repository.

| Folder | What it holds |
|---|---|
| `backend/` | Python backend, one folder per feature |
| `backend/system/` | Locations and every Linux/macOS difference (stdlib only) |
| `backend/hermes/` | Everything that touches Hermes: tools, hooks, prompt, contracts, results |
| `backend/broker/` | The per-user broker process and its engine workers (stdlib only) |
| `backend/setup/` | Setup page RPCs: toolchain install, removal, the studio profile |
| `backend/library/` | Games, Build and Emulator RPCs, the library, game cards, the game tools |
| `backend/assets/` | Game images for the Build page and their kept versions |
| `backend/history/` | Build history: a snapshot of a game after each build, and restoring one |
| `backend/player/` | The loopback server for the page's emulator |
| `page/` | Source of the Hermes Desktop page and the player frame script |
| `page/app/` | The page shell and page-wide plumbing (registry, page events and slots, RPC names, routing) |
| `page/pages/` | One folder per page, its tabs and areas inside |
| `page/shared/` | UI parts, styles, art and player helpers every page uses (imports no app/ or pages/) |
| `page/frame/` | The script injected into the emulator frame |
| `page/backgrounds/` | What pages draw behind them, one folder each (`hermretro-dev-backgrounds`) |
| `desktop/` | Generated page bundle (plugin.js) that Hermes Desktop loads |
| `player/` | The browser player served to the page, its device art and the generated frame script |
| `player/web/` | ModRetro's web player (vendored) |
| `player/skins/` | The emulator's device skins, one folder each (`skin.webp`, `skin.json`) (`hermretro-dev-skins`) |
| `engine/` | hermretro's engine, started from ModRetro's; changed in its `src/` modules (`src/entry.js` is the server's own), each change in `engine/CHANGES.md`; `dist/server.js` is built from them (`node tools/engine/bundle.mjs`) |
| `engine/CHANGES.md` | hermretro's changes to the engine, one line each |
| `engine/contract/` | The engine's tool contracts and file manifest; with `engine/CHANGES.md`, the record of the engine, outside its manifest and copies |
| `skills/` | Skills the plugin gives the agent |
| `skills/authoring/` | Making a game project |
| `skills/deployment/` | Getting a game onto a Chromatic |
| `skills/game-planning/` | Planning a game |
| `skills/pixel-art/` | Drawing sprites and backgrounds |
| `skills/rom-debugging/` | Finding faults in a built ROM |
| `skills/setup/` | Setting up the toolchain and device |
| `profile/` | Files for the hermretro studio profile |
| `tests/` | Tests, mirroring the code layout; support.py holds the shared temp-folder helpers |
| `tests/backend/` | Python unit tests, one folder per backend feature |
| `tests/page/` | Page tests in jsdom, their harness and the browser preview |
| `tests/repo/` | Repository-wide checks: names in lock step, version, file sizes, portability, bundle, scan |
| `tests/acceptance/` | The real-engine run through the broker |
| `tests/dev/` | Tests for the development loop (tools/dev) |
| `tools/` | Developer tools; check.py runs every check |
| `tools/bundle/` | Builds page/ into the generated files and lints it (ESLint config and the boundary rules) |
| `tools/ci/` | Clean install, toolchain preparation and Hermes API checks used by CI |
| `tools/engine/` | Engine helpers: manifest, schema reconciliation, the event catalog, the bundle built from the engine's modules (`bundle.mjs`) and the module-by-module comparison of two bundles (`compare_bundles.mjs`) |
| `tools/engine/npm/` | Pinned npm tools for building and comparing the engine's bundle: its esbuild, the packages it includes, and acorn and eslint-scope |
| `tools/debug/` | Debugging helpers for a running gateway |
| `tools/dev/` | The development loop against the local Hermes: live checkout, plugin reload, page watch and live preview, and the sandbox (a private Hermes with a scripted model and a headless browser) (python tools/dev) |
| `tools/npm/` | Pinned npm tools for development only |
| `tools/py/` | Pinned Python tools for development only (ruff), their settings, and check.py's helpers |
| `.agents/skills/` | The development skills: how to work on hermretro (`.claude/skills` links here) |
| `.github/` | CI workflows, templates and community files |
| `.github/workflows/` | CI, integration and nightly workflows |
| `.github/actions/` | Shared workflow steps |
| `.github/ISSUE_TEMPLATE/` | Issue forms |

## The agent half

The backend is one folder per feature (`backend/features.py` lists them in registration order). Each feature
**declares** what it adds to Hermes in its own folder, **exposes** what other features may use in its front door
(`__init__.py`: `__all__`, and the events it emits in `EVENTS`), and **reacts** to other features in
`listeners.py`. `backend/system/` (the machine) and `backend/hermes/` (everything that touches Hermes) are shared
layers. Each feature's `README.md` lists its RPCs, tools, hooks and events.

| Feature | Declares | Front door / events |
|---|---|---|
| `backend/hermes/` | the 85 engine tools (`tools.py`), `pre_tool_call` (hardware approvals), `subagent_start`, `subagent_stop`, `post_tool_call`, `post_compaction` (where a chat stands after a compaction, `chat_state.py`, carried by the next engine result) (`hooks.py`), the skills and the `hermretro.guide` section (`prompt.py`) | `host.py` (shared helpers: data folder, profile, library, the chat's project, broker client, and for a hook `tool_result_payload` and `library_game_for`), `declare.py`; `api.py` is the one door to Hermes |
| `backend/setup/` | RPCs `status`, `doctor`, `activity`, `studio_profile`, `studio_claude_sign_in`, `install`, `remove_tools`, `releases`, `reset_plan`, `reset`; tool `chromatic_studio_device_cli`; `pre_tool_call` (the CLI download's approval) | the broker's install helpers; `setup.tools_removed`, `setup.studio_profile_ready` |
| `backend/library/` | RPCs `games`, `game_build_status`, `game_thumb`, `player`, `presentations`, `captures`, `capture_image`, `build`; tools `chromatic_present_game`, `chromatic_game_info`, `chromatic_playtest`, `chromatic_build_report`; `pre_llm_call` (the Build conversation's context), `pre_tool_call` (Hermes's file tools kept out of a game's `.hermretro/`, and out of a library game's folder except from its own conversation) | the library (`Registry`, `game_id`, `canonical_rom`, `plays_game_rom`, `installed_rom`, `folder_lock`, `cover_path`, `engine_path`, `after_build`, …); `library.build_reported`, `library.game_presented`, `library.game_moved` |
| `backend/assets/` | RPCs `asset`, `asset_info`, `asset_restore`, `assets`; `post_llm_call`, `post_tool_call` (kept image versions) | nothing; `assets.image_restored`; listens to `library.build_reported`, `library.game_moved` |
| `backend/history/` | RPCs `builds`, `build_restore`; `post_tool_call` (a snapshot after each build); listens to `library.game_moved` | nothing; `history.build_kept` |
| `backend/player/` | nothing | the loopback player server (`get_server`, `game_build`, …) |
| `backend/broker/` | nothing (a separate process) | the client (`ensure_broker`, `try_connect`, `game_hold`, `test_build`, `BrokerUnavailable`, `BrokerNotRunning`, `BrokerRestarting`, `OtherCopyBusy`) |
| `backend/system/` | nothing | a shared layer: `paths.py`, `host.py`, `events.py`, `hermes_home.py` |

`__init__.register()` collects every feature's declarations (`backend/hermes/declare.py`) in `features.py` order:
the page's RPCs in every profile; tools, skills, hooks and the prompt section only in the `hermretro` profile. A
hook several features declare is registered once and calls each in feature order (`declare.chain`).
`tests/backend/hermes/test_registration.py` checks what each profile gets and that what Hermes runs is usable
(callable handlers, each hook once, skills under their folder names, the guide within its limit);
`tests/repo/test_lockstep.py` checks the manifest names the tools and hooks that register.

How features may connect is checked by `tests/repo/test_boundaries.py`: a module imports the standard library,
its own feature, the shared layers, and another feature only through its front door's `__all__`;
`backend/system/` imports nothing above it (Hermes's answer for its home is handed down through
`system/hermes_home.py` when `backend.hermes` is imported); events are declared once by their owner, emitted only
by it, and listened to from `listeners.py`. A deliberate exception is a line comment
`hermretro: allow <rule> — <reason>`, listed as a warning on every run.

So a value (a constant, a function, a class) that another feature reads is imported into the owner's front door
`backend/<owner>/__init__.py` and listed in its `__all__`, and the reader writes `from ..<owner> import NAME` (inside
the owner, `from .module import NAME`). Importing it from the module that defines it
(`from ..<owner>.module import NAME`) fails the boundary test, even when the module is public-looking.

### Adding things

| To add | Touch |
|---|---|
| an RPC | `backend/<feature>/rpcs.py`: `@rpc("name") def rpc_name(ctx)`, and a section in `.agents/skills/hermretro-dev-architecture/references/contract.md`. Then `node tools/bundle/bundle.mjs` (regenerates the page's names, `RPC_<NAME>` in `page/app/rpc-names.js`). |
| a plugin tool | `backend/<feature>/tools.py`: schema, handler, `Tool(SCHEMA, handler, step_words=(…))` in `TOOLS`; `plugin.yaml` `provides_tools`. Then the page's `step-words.js` (checked against `step_words`), `.agents/skills/hermretro-dev-architecture/references/contract.md`. A tool about the selected game resolves the project with `tool_project(tool, args, kwargs)`, then its library game with `host.library_game_for([root])`, and answers failures with `tool_error(message, code, next_step)` (`from ..hermes.tool_args import tool_error, tool_project`); `tool_project` keeps a game's Build conversation to its own game. A tool that calls engine tools does so as the chat with `host.engine_call(tool, args, kwargs)` (the broker's response and the chat's note after a compaction; `backend/library/playtest_tools.py`) |
| a split of a big `rpcs.py` | move each handler factory into `backend/<feature>/<topic>_rpcs.py` as `def rpc_<name>(ctx)`; `rpcs.py` keeps every `@rpc("<name>")` declaration, now `def rpc_<name>(ctx): return _<topic>_rpcs_mod.rpc_<name>(ctx)` after `from . import <topic>_rpcs as _<topic>_rpcs_mod` (the page's names and the lock-step test read only `rpcs.py`) |
| a hook | `backend/<feature>/hooks.py`: `@hook("name")`; a name no feature hooked before also goes in `plugin.yaml` `provides_hooks`. A `post_tool_call` hook reads an engine tool's result with `host.tool_result_payload(result)` (the JSON text or the multimodal envelope's summary, as a dict) and finds its library game with `host.library_game_for(paths)` (`(game id, root)` of the game containing the first matching path; `backend/history/hooks.py` passes the result's `projectRoot`, the `projectPath` argument and the chat's project). A test of a chained hook asserts only the relative order it needs, so a feature's new callback does not break it |
| an event | the owner's front door `EVENTS` + `emit(...)` where it happens: something the broker does is announced from the gateway side (the broker stays standard library only and emits nothing), in the RPC or hook that first learns of it, once per occurrence; listeners in `backend/<other>/listeners.py` with `@on(...)`. A listener goes in each feature that reacts (not `broker` or `system`, which stay standard library only) |
| state a listener keeps | a module-level value in the feature's own module (where the listener lives, or the module it calls), with a reader function beside it (listeners run in the emitting process, so this value is per process: the gateway, a plugin host and a turn process each hold their own); export the reader in the front door's `__all__` only when another feature reads it (then as the row below). Not on `host` or another feature's module. State another process must read (the broker, the player, another Hermes process) is a file under `backend.system.paths.hermretro_home()`, written atomically with `paths.write_json_atomic(path, data)` (a temp file beside it, then `os.replace`), not module state |
| a name exported from a feature's front door (a value other features read) | import it in the owner's `backend/<owner>/__init__.py` and add it to `__all__` (`tests/repo/test_boundaries.py` checks only these two); by hand also: that docstring's "Front door:" line when it says nothing is exported, the owner README's `## Front door` line, and the owner's "Front door / events" cell in the table above. Readers import `from ..<owner> import NAME` |
| a module split or renamed inside a feature | as "Splitting a module" below: the feature README's module list (its opening paragraph) and any mention in `.agents/skills/hermretro-dev-architecture/references/architecture.md`; `tests/repo/test_doc_pointers.py` fails on a backtick-quoted `backend/` or `page/` path that no longer exists |
| a feature | `backend/<name>/` with `__init__.py` (docstring, `__all__`, `EVENTS`), `README.md` and its declaration files; one line in `backend/features.py`; its line in the Map above; tests in `tests/backend/<name>/`. |

Each feature's row in the table above lists what it registers: a new RPC or tool goes in its Declares cell and a new
event in its Front door / events cell, along with the feature's README.

**Splitting a module.** The new module goes next to the old one in the same feature folder
(`backend/<feature>/<new>.py`). Update every caller to import from it, or, when tests or other features still use the
moved names through the old module, import them back there with `# noqa: F401 - re-exported`. Move the moved code's
tests to `tests/backend/<feature>/test_<new>.py`. Then change the feature README's module list and any doc that
names the old module for the moved code (`tests/repo/test_doc_pointers.py` checks the paths they name); `git grep`
the old module's path too, for comments and docs that name it without backticks. Splitting or renaming, the new
module's name can shadow a local or parameter of the same name in its users (`from . import progress` in a function
with a `progress` variable): `git grep -w <new>` across `backend/`, `tools/` and `tests/`
and rename those locals first. A split can rename log lines: the
modules that log with `logging.getLogger(__name__)` (`backend/player/server.py`, `backend/system/events.py`,
`backend/hermes/host.py`) name their logger after the module, so moved code logs under the new name; say so in the
pull request body. The rest log through `host.logger` and keep its name.

Other modules worth knowing: `backend/hermes/contracts.py` (pinned tool contracts → Hermes schemas),
`backend/hermes/results.py` (a broker answer → a tool result, images saved), `backend/setup/provision.py`
(ModRetro's CLI, pinned SHA-256; removing downloads), `backend/broker/broker.py` (the single authority: identity,
admission, the hardware gate), `lane.py` (a conversation's engine worker and writer leases), `selection.py` (which projects it may open, ownership), `installed.py` (installed games' conversations, `test_build`), `control.py`
(control ops, the page's install), `lifecycle.py` (admission, shutdown, retirement, notices), `server.py` (the user-only Unix socket), `client.py` (finds or starts the
broker; refuses a stale one), `backend/system/paths.py` (every location, the code fingerprint, the version).

Modules the broker imports stay standard-library only: the broker runs as `python -m backend.broker` with a
minimal environment and no Hermes on its path, so nothing it reaches may import `backend/hermes/`, a feature's
`rpcs.py`, `tools.py`, `hooks.py` or `listeners.py`, or emit events (`tests/repo/test_broker_imports.py` walks its
imports; there are no exceptions).

**Why a broker.** Engine workers are expensive (about 300 MB each), a project may only have one writer, and
Hermes runs many chats (and profiles) in one gateway process. One broker per user owns all of that; the
gateway talks to it over a private Unix socket with a token. A client replaces it when the backend's code on disk
changes (the fingerprint covers every file under `backend/`, `__init__.py`, `plugin.yaml` and the pinned
`tools.json`: what the plugin reads as it loads), and likewise when
its handshake shows its new workers cannot start (its `node` was removed, or `temp_ok` is false while the
client's TMPDIR would work): it asks `{"op": "shutdown", "replace": true}`. The broker's life is one state under its
table lock (`backend/broker/lifecycle.py`): serving, retiring, stopping. Work (a call, the page's install start,
doctor) is admitted under that lock and counted until its answer has been written. Retiring, it admits nothing
(`RESTARTING`) and answers `RETIRING` (the client raises `BrokerRestarting`; an engine tool call waits for the new
broker up to two minutes in all, `backend/hermes/host.py`) until nothing it must finish runs: admitted work, the
page's install, and for up to 15 minutes engine work whose outcome is unknown (a call that timed out), a recording a
call started and a browser preview someone records or saves in (it asks the engine to close each preview itself
first). Idle workers do not keep it (a worker it started would run the new engine against the contracts it loaded,
`ENGINE_PIN_MISMATCH`): they close with it, and each of their conversations is told on its first call to a later
broker (`notices.json` in the run folder, kept until a call's answer has carried it). A plain shutdown (Setup's
removal, another copy) is decided under the same lock and refused while anything runs or a worker lives. A broker
from before `replace` answers it busy and is never dispatched to (`BrokerRestarting` that does not wait). The broker
reads its fingerprint once, at start, and its handshake names it as `loaded_code_fingerprint`; the client compares
that with the files on disk now, so a broker an update rewrote underneath is told apart from a new one. The
handshake's `loaded_fingerprint` is the same code by the releases' rule (`paths.release_fingerprint`: `backend/` and
`plugin.yaml` only), the field their clients compare: a gateway of a release, not yet restarted after an update, keeps
the broker the new files start instead of shutting each one down.

## The page half

`page/` is the source: `app/` (shell and the page-wide plumbing), one folder per page under `pages/` with its
tabs and areas inside, `shared/` and `frame/`, joined by import aliases (rules in `.agents/skills/hermretro-dev-page/references/source.md`, "The page's source");
`tools/bundle/bundle.mjs` builds it into two committed files: `desktop/plugin.js` (the page, one ESM file, because
Hermes's loader evaluates exactly one file that may import only the SDK and React) and `player/frame-shim.js`
(injected into the emulator frame). Installs run no build step, so the built files are committed and CI proves
they match the source.

Pages declare themselves: `page/pages/index.js` lists them (one line each), each page's `index.js` is its
descriptor and front door, and the shell (`page/app/`) builds the nav, routing, tab bars and stylesheet from
that list. Pages connect only through what another page exposes: its front door's exports, page events
(`app/events.js`) and UI slots (`app/slots.js`); ESLint (`python tools/check.py lint`) enforces the import
boundaries. How to add a page, tab, event or slot: `.agents/skills/hermretro-dev-page/references/adding.md`, "Adding to the page".

The page talks to the backend only through `plugin.hermretro.*` RPCs (names in `page/app/rpc.js`, generated
from the backend's `@rpc` declarations; shapes in `.agents/skills/hermretro-dev-architecture/references/contract.md`). Build chats are ordinary Hermes sessions in the `hermretro` profile, driven through
the gateway (`page/pages/build/chat/`), never in another profile (`app/routing.js` `studioTarget()`).

## Where state lives

All of hermretro's own per-user state is in `~/.hermes/hermretro/` (see the README), shared by every profile and
left alone by plugin updates and removal. The engine adds one folder of its own once a Chromatic is used:
`~/.codex-gb-studio/chromatic/` (device-operation journal). The device CLI is unpacked in the prepared engine copy
(`.cache/engine-<version>-<digest>/`), whose `package.json` names no packed format, so the engine never unpacks
it into `~/.modretro-chromatic-runtime/` as ModRetro's packed plugin does. Per-profile state (saved frames, asset versions) is in that profile's
`plugin-data/hermretro/`. Nothing is written into the plugin folder.

## What runs where

| Process | Started by | Lives |
|---|---|---|
| Gateway | Hermes | The plugin's Python is imported here |
| Broker | first tool call or page install | Until idle 10 min; own systemd scope on Linux when the gateway is a service |
| Engine workers | the broker, per conversation lane | Until the lane is idle 30 min |
| Player server | the broker's lane / the page | With its lane |
