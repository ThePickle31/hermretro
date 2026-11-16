# hermretro for Hermes

Working, unofficial name. A Hermes plugin for making Game Boy and Game Boy Color games for the ModRetro
Chromatic: plan a game, build it as a real GB Studio project, compile a genuine ROM, playtest it in an
emulator, and (with hardware turned on) stream it to or flash it onto a Chromatic.

**Status: early build, 0.0.4.** The agent tools, private per-chat engine workers, skills and the Chromatic
Studio page (with ModRetro's real player) exist. Annotations from the player and hardware qualification are
not verified yet. See [what works](#what-works-today).

## Install

From GitHub (installs the latest release on `main`). In Hermes Desktop: Capabilities → Plugins → **Install
from Git**, enter `https://github.com/ThePickle31/hermretro`, press **Review repository**, then **Install**.
The link `hermes://plugin/install?repo=ThePickle31/hermretro&enable=1` opens the same dialog.

From a terminal:

```sh
hermes plugins install ThePickle31/hermretro --enable
```

Update later with `hermes plugins update hermretro`.

For development, link a checkout instead:

```sh
ln -s /path/to/hermretro "$HERMES_HOME/plugins/hermretro"   # ~/.hermes by default
hermes plugins enable hermretro
```

Then, in Hermes Desktop, turn on **hermretro** under Capabilities → Plugins and open the
**hermretro** page from the sidebar. The page checks your setup and has copyable prompts for every step.

The first step on that page creates a dedicated **hermretro** profile: it shares your sign-in, has the
plugin and its skills turned on, and leaves the profile you installed into unchanged. Chromatic chats open
in that profile. Its personality is `profile/SOUL.md`. The profile links to the plugin you installed rather
than copying it, so both profiles share one plugin folder and one `games/` folder.

Requirements: Node.js 22 or newer. Hermes installs its own Node.js, which hermretro uses, so this is
normally already met. Everything else (GB Studio CLI, GBDK, PyBoy) is prepared on request by asking
Hermes: *"Set up hermretro so I can create games, build ROMs, and run automated playtests."*

## What works today

| Area | State |
|---|---|
| All 81 original tools, as `chromatic_*` | Registered with exact schemas; a real model turn has created, built and playtested a project |
| Real emulator frames reaching the model | Proven with a vision model |
| One private engine worker per conversation | Proven across separate chats, resumed chats, delegation and compaction |
| Skills (`hermretro:setup`, `game-planning`, `authoring`, `pixel-art`, `rom-debugging`, `deployment`) | Adapted from the originals |
| hermretro page: Home, Build, Setup, Prompts, Games, Emulator | Built; see below and `docs/dev/STUDIO-PAGES.md` |
| Playing inside Hermes | The Emulator page runs ModRetro's own player (with a demo cartridge when you have no games yet). When a game is ready to try, the agent calls `chromatic_present_game` and the emulator opens in a tab beside the chat |
| Annotations from the player (Ask Hermes) | Built; not yet verified with a live agent |
| Hardware (discover, stream, capture, flash) | Off by default, behind a setting and Hermes's approval prompt. Not tested on a device |

Qualified so far only on local Linux x64.

## How it is built

- `engine/modretro-chromatic/` — the original engine, bundled with one small path change (see
  `THIRD_PARTY_NOTICES.md`) and verified against a manifest.
- `adapter/` — the Hermes side. `broker.py` is the single authority on the machine: it gives each conversation
  its own engine worker, coordinates writers on the same project, and gates hardware. Tool handlers and the
  desktop page are its clients.
- `desktop-src/` — the Hermes Desktop page, one small module per feature. `tools/bundle.mjs` bundles it into
  `desktop/plugin.js`, the single file the app loads (generated and committed, because installing a plugin
  runs no build). On first use the page shows only a guided setup: welcome, the full
  list of what gets downloaded (version, source, size, purpose), the install itself with live progress and
  checksums (run by the page, not a chat), whether you have a Chromatic, and your first game idea. After that,
  one segmented control for its six pages:
  - **Home**: what to do next (continue setup or your last game), quick starts and studio status.
  - **Setup**: one step per page, advancing by itself as the backend verifies each step; a physical
    Chromatic is optional. A step that breaks later shows a Repair banner on the other pages.
  - **Prompts**: every prompt, editable, put into a new or the current chat (never sent for you).
  - **Games**: your library as cartridges: play, install on a Chromatic (through the chat's approval),
    open the game's chat.
  - **Emulator**: ModRetro's real player, served by the plugin (`adapter/player_server.py`).
  - **Build**: one game, one conversation with HermRetro. When a turn has built the game, you play it
    right in that turn's build card, at a whole-number scale, with a play-test checklist from the build
    report beside it and Annotate to point HermRetro at sprites and tiles in the game.

  The page talks to the backend through `plugin.hermretro.*` RPCs (`status`, `doctor`, `install`,
  `studio_profile`, `activity`, `games`, `game_thumb`, `player`, `presentations`, `captures`,
  `capture_image`, `build`, `builds`, `build_restore`, `asset`, `asset_info`, `asset_restore`, `assets`;
  see `docs/dev/CONTRACT.md`). The plugin's own agent tool `chromatic_present_game` shows a
  finished game to the user in the emulator beside the chat; builds open nothing by themselves.
- `games/` — the games you make (git-ignored). `chromatic_project_create` and
  `chromatic_project_create_blank` put a new game here unless you ask for another folder
  (`HERMRETRO_GAMES_DIR` moves it). The Games shelf itself is a list of project folders kept in
  `~/.local/state/chromatic-studio/games.json`. Uninstalling the plugin deletes its folder, games included:
  copy `games/` somewhere first.
- `skills/` — agent skills.
- `schemas/`, `release/` — pinned contracts, engine manifest and test evidence.

## Test

```sh
python -m unittest discover -s tests                     # fast unit tests
python tests/acceptance/broker_acceptance.py             # real engine, compiler and emulator (~20 s)
hermes plugins doctor .                                  # Hermes's own registration check
node tools/bundle.mjs --check                            # desktop/plugin.js matches desktop-src/
node tests/desktop/wizard_test.mjs                       # the built page, driven in jsdom
```

The acceptance run writes its evidence to `notes/evidence/` (git-ignored, like everything in `notes/`).

## Working on the page

Edit the modules in `desktop-src/`, never `desktop/plugin.js` or `player/frame-shim.js` (the script the
player frame runs first, from `desktop-src/frame/`): both are generated, and the tests fail when they do not
match their sources.

```sh
node tools/bundle.mjs                                    # build desktop/plugin.js and player/frame-shim.js
node tools/bundle.mjs --watch                            # rebuild on save; a linked checkout hot-reloads
node tools/bundle.mjs --report                           # lines per module
```

Commit the sources and the rebuilt files together. The bundler takes esbuild and TypeScript
from a Hermes Desktop checkout (`$HERMES_DESKTOP_DIR`, else `~/.hermes/hermes-agent/apps/desktop`), so the
repository has no npm dependencies. It also checks the source tree on every build: only `sdk.js` imports
packages, feature folders are one level deep, no import cycles, no file over 400 lines (three large components are
listed as exceptions in `tools/bundle_lint.mjs` until they are split). Where code goes
is described in `docs/dev/STUDIO-PAGES.md` ("The page's source").

## Licence

MIT for this repository's own code. The bundled engine and the proprietary ModRetro CLI inside it have their
own terms: see `THIRD_PARTY_NOTICES.md`. For original, user-created ROMs only.
