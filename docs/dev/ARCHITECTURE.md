# How hermretro is built

hermretro is one Hermes plugin with two halves. The **agent half** (Python, `__init__.py` + `adapter/`) gives
the agent the game-making tools; the **page half** (`desktop/plugin.js`, built from `desktop-src/`) is the
hermretro page in Hermes Desktop. Underneath both is the **engine**: ModRetro's own Chromatic MCP server,
vendored unchanged under `engine/modretro-chromatic/` (one recorded patch, see `ENGINE-UPDATE.md`).

```
Hermes gateway (one process, every profile)                 per user, ~/.hermes/hermretro/
 ├─ __init__.register()  tools / skills / hooks / prompt     ├─ games/      the user's projects
 │   (only in the "hermretro" profile)  + page RPCs          ├─ library/    the Games shelf
 └─ adapter/hermes_host  ── Unix socket ──►  broker ─────────┼─ .cache/    toolchain + prepared engine
                                              (one per user) └─ run/       socket, token, lock, logs
                                               ├─ engine worker (Node) per conversation lane
                                               └─ player server (loopback) for the page's emulator
```

## The agent half

| Module | Job |
|---|---|
| `__init__.py` | `register()`: the page's RPCs everywhere; tools, skills, hooks and the prompt section only in the `hermretro` profile |
| `adapter/hermes_host.py` | Everything that touches Hermes: tool handlers, RPC methods, hooks, the prompt section |
| `adapter/contracts.py` | The engine's pinned tool contracts (`schemas/upstream/<v>/tools.json`) turned into Hermes schemas (`chromatic_*`) |
| `adapter/results.py` | A broker answer turned into a Hermes tool result without losing what the engine said (images saved, content-addressed) |
| `adapter/client.py` | Finds or starts the broker; refuses a stale one (code fingerprint) |
| `adapter/broker.py` | The single authority on the machine: the `Broker`, identity, admission and the `call` op (the hardware gate, the setup lock); `python -m adapter.broker` |
| `adapter/broker_lane.py` | A conversation's lane: its engine worker (start, restart, idle close), writer leases per project, project selection and the one-game-per-conversation guard |
| `adapter/broker_control.py` | Control ops (`install_*`, `stats`, `shutdown`, `doctor`, `activity`, `lane_status`, leases and lanes), the page's toolchain install, housekeeping |
| `adapter/broker_server.py` | The broker's user-only Unix socket server (handshake, one JSON line per request) and `main()`: election lock, token, signals, the housekeeping tick |
| `adapter/engine.py` | Lossless stdio MCP client for one engine worker |
| `adapter/paths.py` | Every location (`hermretro_home()`), engine verification, the code fingerprint, the version (from `plugin.yaml`) |
| `adapter/host_os.py` | Every Linux/macOS difference (peer credentials, Rosetta, architecture) and the Windows refusal |
| `adapter/provision.py` | ModRetro's CLI for this computer (from npm, pinned SHA-256), the prepared engine copy, removing downloads |
| `adapter/onboarding.py` | The page's toolchain install: what gets downloaded and how far it got |
| `adapter/games.py`, `game_card.py`, `snapshots.py` | The library, each game's card (`game.json` + cover), build history |
| `adapter/player_server.py`, `leases.py` | The page's emulator (ModRetro's real web player), engine lease recovery |
| `adapter/studio_profile.py` | Creating and finishing the `hermretro` profile |

Modules the broker imports stay standard-library only: the broker runs as `python -m adapter.broker` with a
minimal environment and no Hermes on its path.

**Why a broker.** Engine workers are expensive (about 300 MB each), a project may only have one writer, and
Hermes runs many chats (and profiles) in one gateway process. One broker per user owns all of that; the
gateway talks to it over a private Unix socket with a token. It replaces itself when the adapter's code on disk
changes and it is idle (the fingerprint covers every adapter file and `plugin.yaml`).

## The page half

`desktop-src/` is the source, one folder per feature (rules in `STUDIO-PAGES.md`, "The page's source");
`tools/bundle.mjs` builds it into two committed files: `desktop/plugin.js` (the page, one ESM file, because
Hermes's loader evaluates exactly one file that may import only the SDK and React) and `player/frame-shim.js`
(injected into the emulator frame). Installs run no build step, so the built files are committed and CI proves
they match the source.

The page talks to the backend only through `plugin.hermretro.*` RPCs (names in `desktop-src/core/rpc.js`,
shapes in `CONTRACT.md`). Build chats are ordinary Hermes sessions in the `hermretro` profile, driven through
the gateway (`desktop-src/build-chat/`), never in another profile (`core/routing.js` `studioTarget()`).

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
