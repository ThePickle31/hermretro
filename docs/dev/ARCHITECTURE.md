# How hermretro is built

hermretro is one Hermes plugin with two halves. The **agent half** (Python, `__init__.py` + `backend/`) gives
the agent the game-making tools; the **page half** (`desktop/plugin.js`, built from `page/`) is the
hermretro page in Hermes Desktop. Underneath both is the **engine**: ModRetro's own Chromatic MCP server,
vendored unchanged under `engine/modretro-chromatic/` (one recorded patch, see `ENGINE-UPDATE.md`).

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

Every folder in the repository, from `tools/layout.toml` (`tests/repo/test_layout.py` keeps the two in
agreement and checks every tracked file sits in one of them).

| Folder | What it holds |
|---|---|
| `backend/` | Python backend, one folder per feature |
| `backend/system/` | Locations and every Linux/macOS difference (stdlib only) |
| `backend/hermes/` | Everything that touches Hermes: tools, hooks, prompt, contracts, results |
| `backend/broker/` | The per-user broker process and its engine workers (stdlib only) |
| `backend/setup/` | Setup page RPCs: toolchain install, removal, the studio profile |
| `backend/library/` | Games, Build and Emulator RPCs, the library, game cards, build history |
| `backend/assets/` | Game images for the Build page and their kept versions |
| `backend/player/` | The loopback server for the page's emulator |
| `page/` | Source of the Hermes Desktop page and the player frame script |
| `page/app/` | The page shell and page-wide plumbing (RPC names, routing, navigation) |
| `page/pages/` | One folder per page, its tabs and areas inside |
| `page/shared/` | UI parts, styles, art and player helpers used by several pages |
| `page/frame/` | The script injected into the emulator frame |
| `desktop/` | Generated page bundle (plugin.js) that Hermes Desktop loads |
| `player/` | The browser player served to the page, its device art and the generated frame script |
| `player/web/` | ModRetro's web player (vendored) |
| `player/devices/` | Device art for the player |
| `engine/` | The vendored ModRetro engine and its pins |
| `engine/modretro-chromatic/` | The vendored engine, unchanged outside a deliberate engine update |
| `engine/pins/` | Per engine version: tool contracts and file manifest |
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
| `tests/repo/` | Repository-wide checks: names in lock step, version, layout, portability, bundle, scan |
| `tests/acceptance/` | The real-engine run through the broker |
| `tools/` | Developer tools; check.py runs every check |
| `tools/bundle/` | Builds page/ into the generated files |
| `tools/ci/` | Clean install, toolchain preparation and Hermes API checks used by CI |
| `tools/engine/` | Engine update helpers: manifest, schema reconciliation |
| `tools/debug/` | Debugging helpers for a running gateway |
| `tools/npm/` | Pinned npm tools for development only |
| `docs/` | Documentation |
| `docs/dev/` | Developer references: architecture, testing, debugging, contract, pages, engine update |
| `.github/` | CI workflows, templates and community files |
| `.github/workflows/` | CI, integration and nightly workflows |
| `.github/actions/` | Shared workflow steps |
| `.github/ISSUE_TEMPLATE/` | Issue forms |

## The agent half

| Module | Job |
|---|---|
| `__init__.py` | `register()`: the page's RPCs everywhere; tools, skills, hooks and the prompt section only in the `hermretro` profile |
| `backend/hermes/host.py` | Everything that touches Hermes: engine tool handlers, hooks, the prompt section, the helpers the modules below share (data folder, profile, library, broker client); re-exports their names through `_MOVED`, so `host.<name>` reaches every RPC and tool |
| `backend/hermes/api.py` | The one door to Hermes itself: every Hermes name used, in `USED` (checked by `tools/ci/hermes_api_check.py`) |
| `backend/hermes/contracts.py` | The engine's pinned tool contracts (`engine/pins/<v>/tools.json`) turned into Hermes schemas (`chromatic_*`) |
| `backend/hermes/results.py` | A broker answer turned into a Hermes tool result without losing what the engine said (images saved, content-addressed) |
| `backend/setup/rpcs.py` | Setup page RPCs: `status`, `install`, `remove_tools`, `studio_profile`, `activity`, `doctor` |
| `backend/setup/provision.py` | ModRetro's CLI for this computer (from npm, pinned SHA-256), the prepared engine copy, removing downloads |
| `backend/setup/progress.py` | The page's toolchain install: what gets downloaded and how far it got |
| `backend/setup/studio_profile.py` | Creating and finishing the `hermretro` profile |
| `backend/library/rpcs.py` | Games, Build and Emulator page RPCs (library, game ↔ conversation binding, build history, player, captures), the Build conversation's context, the build snapshot hook |
| `backend/library/tools.py` | The plugin-owned tools: `chromatic_studio_device_cli`, `chromatic_present_game`, `chromatic_game_info`, `chromatic_build_report` |
| `backend/library/games.py`, `game_card.py`, `snapshots.py` | The library, each game's card (`game.json` + cover), build history |
| `backend/assets/rpcs.py` | Game images for the Build page: `asset`, `asset_info`, `asset_restore`, `assets` |
| `backend/assets/versions.py` | The kept versions of each image and the hooks that keep them (`MEDIA:` lines, inspected images) |
| `backend/assets/sprites.py` | How a project shows a sprite or background: animations, palettes, the scenes that use it |
| `backend/broker/broker.py` | The single authority on the machine: the `Broker`, identity, admission and the `call` op (the hardware gate, the setup lock); started as `python -m backend.broker` (`__main__.py`) |
| `backend/broker/lane.py` | A conversation's lane: its engine worker (start, restart, idle close), writer leases per project, project selection and the one-game-per-conversation guard |
| `backend/broker/control.py` | Control ops (`install_*`, `stats`, `shutdown`, `doctor`, `activity`, `lane_status`, leases and lanes), the page's toolchain install, housekeeping |
| `backend/broker/server.py` | The broker's user-only Unix socket server (handshake, one JSON line per request) and `main()`: election lock, token, signals, the housekeeping tick |
| `backend/broker/client.py` | Finds or starts the broker; refuses a stale one (code fingerprint) |
| `backend/broker/engine.py` | Lossless stdio MCP client for one engine worker |
| `backend/broker/leases.py` | Engine lease recovery |
| `backend/player/server.py` | The page's emulator (ModRetro's real web player) |
| `backend/system/paths.py` | Every location (`hermretro_home()`), engine verification, the code fingerprint, the version (from `plugin.yaml`) |
| `backend/system/host.py` | Every Linux/macOS difference (peer credentials, Rosetta, architecture) and the Windows refusal |

Modules the broker imports stay standard-library only: the broker runs as `python -m backend.broker` with a
minimal environment and no Hermes on its path, so nothing it reaches may import `backend/hermes/`, an `rpcs.py`
or `tools.py` (`tests/repo/test_broker_imports.py` walks its imports).

**Why a broker.** Engine workers are expensive (about 300 MB each), a project may only have one writer, and
Hermes runs many chats (and profiles) in one gateway process. One broker per user owns all of that; the
gateway talks to it over a private Unix socket with a token. It replaces itself when the backend's code on disk
changes and it is idle (the fingerprint covers every file under `backend/` and `plugin.yaml`).

## The page half

`page/` is the source: `app/` (shell and the page-wide plumbing), one folder per page under `pages/` with its
tabs and areas inside, `shared/` and `frame/`, joined by import aliases (rules in `STUDIO-PAGES.md`, "The page's source");
`tools/bundle/bundle.mjs` builds it into two committed files: `desktop/plugin.js` (the page, one ESM file, because
Hermes's loader evaluates exactly one file that may import only the SDK and React) and `player/frame-shim.js`
(injected into the emulator frame). Installs run no build step, so the built files are committed and CI proves
they match the source.

The page talks to the backend only through `plugin.hermretro.*` RPCs (names in `page/app/rpc.js`,
shapes in `CONTRACT.md`). Build chats are ordinary Hermes sessions in the `hermretro` profile, driven through
the gateway (`page/pages/build/chat/`), never in another profile (`app/routing.js` `studioTarget()`).

## Where state lives

All of hermretro's own per-user state is in `~/.hermes/hermretro/` (see the README), shared by every profile and
left alone by plugin updates and removal. The engine adds two folders of its own once a Chromatic is used:
`~/.codex-gb-studio/chromatic/` (device-operation journal) and `~/.modretro-chromatic-runtime/` (the unpacked
device CLI). Per-profile state (saved frames, asset versions) is in that profile's
`plugin-data/hermretro/`. Nothing is written into the plugin folder.

## What runs where

| Process | Started by | Lives |
|---|---|---|
| Gateway | Hermes | The plugin's Python is imported here |
| Broker | first tool call or page install | Until idle 10 min; own systemd scope on Linux when the gateway is a service |
| Engine workers | the broker, per conversation lane | Until the lane is idle 30 min |
| Player server | the broker's lane / the page | With its lane |
