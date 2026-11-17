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
| `backend/library/` | Games, Build and Emulator RPCs, the library, game cards, the game tools |
| `backend/assets/` | Game images for the Build page and their kept versions |
| `backend/history/` | Build history: a snapshot of a game after each build, and restoring one |
| `backend/player/` | The loopback server for the page's emulator |
| `page/` | Source of the Hermes Desktop page and the player frame script |
| `page/app/` | The page shell and page-wide plumbing (registry, page events and slots, RPC names, routing) |
| `page/pages/` | One folder per page, its tabs and areas inside |
| `page/shared/` | UI parts, styles, art and player helpers every page uses (imports no app/ or pages/) |
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
| `tools/bundle/` | Builds page/ into the generated files and lints it (ESLint config and the boundary rules) |
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

The backend is one folder per feature (`backend/features.py` lists them in registration order). Each feature
**declares** what it adds to Hermes in its own folder, **exposes** what other features may use in its front door
(`__init__.py`: `__all__`, and the events it emits in `EVENTS`), and **reacts** to other features in
`listeners.py`. `backend/system/` (the machine) and `backend/hermes/` (everything that touches Hermes) are shared
layers. Each feature's `README.md` lists its RPCs, tools, hooks and events.

| Feature | Declares | Front door / events |
|---|---|---|
| `backend/hermes/` | the 81 engine tools (`tools.py`), `pre_tool_call` (hardware approvals), `subagent_start`, `subagent_stop` (`hooks.py`), the skills and the `hermretro.guide` section (`prompt.py`) | `host.py` (shared helpers: data folder, profile, library, the chat's project, broker client), `declare.py`; `api.py` is the one door to Hermes |
| `backend/setup/` | RPCs `status`, `doctor`, `activity`, `studio_profile`, `install`, `remove_tools`; tool `chromatic_studio_device_cli`; `pre_tool_call` (the CLI download's approval) | the broker's install helpers; `setup.tools_removed`, `setup.studio_profile_ready` |
| `backend/library/` | RPCs `games`, `game_thumb`, `player`, `presentations`, `captures`, `capture_image`, `build`; tools `chromatic_present_game`, `chromatic_game_info`, `chromatic_build_report`; `pre_llm_call` (the Build conversation's context) | the library (`Registry`, `game_id`, `cover_path`, …); `library.build_reported`, `library.game_presented` |
| `backend/assets/` | RPCs `asset`, `asset_info`, `asset_restore`, `assets`; `post_llm_call`, `post_tool_call` (kept image versions) | nothing; `assets.image_restored`; listens to `library.build_reported` |
| `backend/history/` | RPCs `builds`, `build_restore`; `post_tool_call` (a snapshot after each build) | nothing; `history.build_kept` |
| `backend/player/` | nothing | the loopback player server (`get_server`, `game_build`, …) |
| `backend/broker/` | nothing (a separate process) | the client (`ensure_broker`, `try_connect`, `BrokerUnavailable`) |
| `backend/system/` | nothing | a shared layer: `paths.py`, `host.py`, `events.py`, `hermes_home.py` |

`__init__.register()` collects every feature's declarations (`backend/hermes/declare.py`) in `features.py` order:
the page's RPCs in every profile; tools, skills, hooks and the prompt section only in the `hermretro` profile. A
hook several features declare is registered once and calls each in feature order (`declare.chain`). The full list
of registrations, in order, is pinned by `tests/repo/test_registration_snapshot.py`.

How features may connect is checked by `tests/repo/test_boundaries.py`: a module imports the standard library,
its own feature, the shared layers, and another feature only through its front door's `__all__`;
`backend/system/` imports nothing above it (Hermes's answer for its home is handed down through
`system/hermes_home.py` when `backend.hermes` is imported); events are declared once by their owner, emitted only
by it, and listened to from `listeners.py`. A deliberate exception is a line comment
`retrodev: allow <rule> — <reason>`, listed as a warning on every run.

### Adding things

| To add | Touch |
|---|---|
| an RPC | `backend/<feature>/rpcs.py`: `@rpc("name") def rpc_name(ctx)`. Then the page's `page/app/rpc.js`, a section in `CONTRACT.md`, and `python tests/repo/test_registration_snapshot.py --write` |
| a plugin tool | `backend/<feature>/tools.py`: schema, handler, `Tool(SCHEMA, handler, step_words=(…))` in `TOOLS`; `plugin.yaml` `provides_tools`. Then the page's `step-words.js` (checked against `step_words`), `CONTRACT.md`, the snapshot |
| a hook | `backend/<feature>/hooks.py`: `@hook("name")`; a name no feature hooked before also goes in `plugin.yaml` `provides_hooks`; the snapshot |
| an event | the owner's front door `EVENTS` + `emit(...)` where it happens; listeners in `backend/<other>/listeners.py` with `@on(...)` |
| a feature | `backend/<name>/` with `__init__.py` (docstring, `__all__`, `EVENTS`), `README.md` and its declaration files; one line in `backend/features.py`; its area in `tools/layout.toml` and the Map above; tests in `tests/backend/<name>/` |

Other modules worth knowing: `backend/hermes/contracts.py` (pinned tool contracts → Hermes schemas),
`backend/hermes/results.py` (a broker answer → a tool result, images saved), `backend/setup/provision.py`
(ModRetro's CLI, pinned SHA-256; removing downloads), `backend/broker/broker.py` (the single authority: identity,
admission, the hardware gate), `lane.py` (a conversation's engine worker and writer leases), `control.py`
(control ops, the page's install), `server.py` (the user-only Unix socket), `client.py` (finds or starts the
broker; refuses a stale one), `backend/system/paths.py` (every location, the code fingerprint, the version).

Modules the broker imports stay standard-library only: the broker runs as `python -m backend.broker` with a
minimal environment and no Hermes on its path, so nothing it reaches may import `backend/hermes/`, a feature's
`rpcs.py`, `tools.py`, `hooks.py` or `listeners.py`, or emit events (`tests/repo/test_broker_imports.py` walks its
imports; there are no exceptions).

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

Pages declare themselves: `page/pages/index.js` lists them (one line each), each page's `index.js` is its
descriptor and front door, and the shell (`page/app/`) builds the nav, routing, tab bars and stylesheet from
that list. Pages connect only through what another page exposes: its front door's exports, page events
(`app/events.js`) and UI slots (`app/slots.js`); ESLint (`python tools/check.py lint`) enforces the import
boundaries. How to add a page, tab, event or slot: `STUDIO-PAGES.md`, "Adding to the page".

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
