# hermretro for Hermes

Working, unofficial name. A Hermes plugin for making Game Boy and Game Boy Color games for the ModRetro
Chromatic: plan a game, build it as a real GB Studio project, compile a genuine ROM, playtest it in an
emulator, and (with hardware turned on) stream it to or flash it onto a Chromatic.

**Status: early build** (the version is in `plugin.yaml`; see the releases). The agent tools, private per-chat engine workers, skills and the Chromatic
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

Update later with `hermes plugins update hermretro` (or Capabilities → Plugins), in the profile you installed it
into. The hermretro profile holds a link to that copy, so it follows; Hermes refuses an update run from inside
the hermretro profile. Then restart Hermes (quit and reopen the app): until then it keeps running the old code,
and the hermretro page says so.

For development, link a checkout instead:

```sh
ln -s /path/to/hermretro "$HERMES_HOME/plugins/hermretro"   # ~/.hermes by default
hermes plugins enable hermretro
```

Then, in Hermes Desktop, turn on **hermretro** under Capabilities → Plugins and open the
**hermretro** page from the sidebar. The page checks your setup and has copyable prompts for every step.

The first step on that page creates a dedicated **hermretro** profile: it shares your sign-in, has the
plugin and its skills turned on, and leaves the profile you installed into unchanged. Chromatic chats open
in that profile and nowhere else: the plugin's tools, skills and system-prompt text exist only there, and the
Build page, "Use in chat" prompts and game chats never fall back to another profile (the Build page offers
Repair instead). In the profile you installed into, only the page's own setup and library calls answer.
For plugin development, `HERMRETRO_EVERY_PROFILE=1` in the gateway's environment loads the agent side
(tools, skills, hooks, prompt) in every profile that has the plugin on, so agents can test the tools there; the
Build page still uses only the `hermretro` profile. Its personality is `profile/SOUL.md`. The profile links to the plugin you installed rather
than copying it, so both profiles share one plugin folder; every profile shares hermretro's own folder
(below).

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

Tested so far on Linux x64; macOS (Apple Silicon and Intel) runs the unit tests and a real broker in CI.

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
  `remove_tools`, `studio_profile`, `activity`, `games`, `game_thumb`, `player`, `presentations`, `captures`,
  `capture_image`, `build`, `builds`, `build_restore`, `asset`, `asset_info`, `asset_restore`, `assets`;
  see `docs/dev/CONTRACT.md`). The plugin's own agent tool `chromatic_present_game` shows a
  finished game to the user in the emulator beside the chat; builds open nothing by themselves.
- `skills/` — agent skills.
- `schemas/`, `release/` — pinned contracts, engine manifest and test evidence.

## Supported systems

Linux and macOS, on Apple Silicon (arm64) and Intel (x64), with the same features on both. Windows is not
supported: there the plugin loads nothing and `hermes plugins list` says why. On a Mac, run the Apple Silicon
build of Hermes; under Rosetta everything works but builds are slower.

## Where your games and downloads live

Nothing hermretro makes or downloads is kept in the plugin folder. It all lives in one folder in the Hermes
home, shared by every profile: `~/.hermes/hermretro/` (or `hermretro/` inside `$HERMES_HOME`'s root).

| Folder | What |
|---|---|
| `games/` | The games you make. `chromatic_project_create` puts a new game here unless you name another folder |
| `library/` | The Games shelf: which projects it lists, their thumbnails and chats |
| `.cache/` | Downloaded tools (GB Studio, GBDK, the emulator, about 2.4 GB) and ModRetro's CLI (`engine-<version>/`); safe to delete, setup downloads them again |
| `run/` | The background broker's socket, logs and lock |

Removing or updating the plugin leaves this folder alone, so your games stay. A full `hermes uninstall`
removes the whole Hermes home, this folder included: copy `games/` somewhere first. `HERMRETRO_HOME` moves
the whole folder; `HERMRETRO_GAMES_DIR` moves just the games.

ModRetro's engine keeps two small folders of its own in your home folder, outside the Hermes home, only once a
physical Chromatic is used: `~/.codex-gb-studio/chromatic/` (its record of device operations such as flashing)
and `~/.modretro-chromatic-runtime/` (the unpacked device CLI, about 16 MB). "Remove downloaded tools" and
uninstalling leave them; delete them by hand if you no longer use a Chromatic.

Upgrading from 0.0.4 or older: those kept downloads in `deps/` and games in `games/` inside the plugin folder,
and the shelf in `~/.local/state/chromatic-studio/`. Copy any games you want out of `games/`, then delete
both folders before updating (Hermes refuses to update a plugin folder holding the old 2.4 GB `deps/`),
and set up again from the hermretro page; nothing is moved for you.

## Test

`python tools/check.py` runs the fast checks the same way CI does (`full` adds the acceptance run; see
`AGENTS.md`). Page work needs the pinned dev tools once: `npm ci --prefix tools/dev --ignore-scripts`.
The individual commands:

```sh
python -m unittest discover -s tests                     # fast unit tests (no Hermes needed)
node tools/bundle.mjs --check                            # the generated files match desktop-src/
node --test 'tests/desktop/**/*test*.mjs'                # page tests, including the built page in jsdom
python tests/acceptance/broker_acceptance.py             # real engine, compiler and emulator (~2 min)
python tools/prepare_toolchain.py                        # install the toolchain the acceptance run needs
python tools/clean_install_check.py                      # clean install into a throwaway Hermes home
hermes -p hermretro tools list                           # the chromatic toolset, only in that profile
```

`hermes plugins doctor` registers the plugin in a temporary Hermes home that is not the `hermretro` profile, so
it reports every tool and hook as "declared but not registered". That is expected; `clean_install_check.py`
checks registration where it matters.

The page test glob already includes `wizard_test.mjs`; run that file on its own only to read its full
output. Run the acceptance test through `python tools/check.py acceptance`, which picks a short temporary
folder: its Unix socket path must stay under 104 characters (macOS's limit; Linux allows 108).

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

Commit the sources and the rebuilt files together. The bundler and the page tests take esbuild,
TypeScript, jsdom and React from the pinned `tools/dev/` (or a Hermes Desktop checkout; `tools/node-modules.mjs`
has the search order). The plugin itself has no npm dependencies, and users never install `tools/dev/`. It also checks the source tree on every build: only `sdk.js` imports
packages, feature folders are one level deep, no import cycles, no file over 400 lines (three large components are
listed as exceptions in `tools/bundle_lint.mjs` until they are split). Where code goes
is described in `docs/dev/STUDIO-PAGES.md` ("The page's source").

## Contributing

Start with `CONTRIBUTING.md`; the developer docs are in `docs/dev/` (`ARCHITECTURE.md` first). Report security
problems privately (`SECURITY.md`).

## Licence

MIT for this repository's own code. The bundled engine and the proprietary ModRetro CLI inside it have their
own terms: see `THIRD_PARTY_NOTICES.md`. For original, user-created ROMs only.
