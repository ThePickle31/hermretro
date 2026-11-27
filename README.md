# hermretro for Hermes

Working, unofficial name. A Hermes plugin for making Game Boy and Game Boy Color games for the ModRetro
Chromatic: plan a game, build it as a real GB Studio project, compile a genuine ROM, playtest it in an
emulator, and (with hardware turned on) stream it to or flash it onto a Chromatic.

**Status: early build** (the version is in `plugin.yaml`; see the releases). The agent tools, private per-chat engine workers, skills and the Chromatic
Studio page (with ModRetro's real player) exist. Annotations from the player and hardware qualification are
not verified yet. See [what works](#what-works-today).

## Install

1. In Hermes Desktop: Capabilities → Plugins → **Install from Git**, enter `https://github.com/ThePickle31/hermretro`,
   press **Review repository**, then **Install**. Or open the link `hermes://plugin/install?repo=ThePickle31/hermretro&enable=1`:
   the dialog opens already reviewing the repository, so press **Install**. This installs the latest release (`main`).
2. Open **HermRetro** from the sidebar (if it is not there, turn on **hermretro** under Capabilities → Plugins).
3. Press **Get started** to review what the game tools will download (version, source, size, purpose). The tools aren't downloaded
   until you press **Download and install**. The page then creates a dedicated **hermretro** profile and installs
   the game tools (GB Studio CLI, GBDK, PyBoy) itself, with live progress and checksums. No chat, prompt or model is
   needed for this.
4. Choose **Start making games** to use the emulator, or **Set up my Chromatic** if you want to use a device now.
   You can add a Chromatic later from Setup.
5. After **Start making games**, type a first game idea and press **Continue in Build** or **Plan it first**. Build
   opens with your idea in the New Game box, unsent. You can also choose **Skip, take me to the studio**. After
   **Set up my Chromatic**, Setup walks through the device steps; then start your first game from Build's New Game.

### What to expect

- **Size.** About 0.7 GB to download and about 2.3 GB on disk once installed (measured on Linux x64). Space used
  while installing has not been measured: leave room beyond that. The tools live in `~/.hermes/hermretro/.cache/`
  (see [where your downloads live](#where-your-games-and-downloads-live)).
- **Time.** It varies a lot with the machine and the connection, so the page shows progress, not a countdown. Most
  of the time goes into building GB Studio's command-line tool on your computer, and the percentage can stay on one
  number for several minutes while that runs: it is still working. You can leave the page; the install keeps going.
  Measured cold installs so far: about a minute and a half on a fast Linux desktop, and on CI's machines about 2.5
  minutes (Linux), 6 minutes (Apple Silicon Mac) and 14 minutes (Intel Mac). A MacBook desktop install has not been
  timed yet. Installing again with the tools already present takes seconds.
- **Node.js.** The tools need Node.js 22 or newer. Hermes installs its own Node.js and hermretro uses it, so this is
  normally already met; the download list says "Node.js not found" when it is not.
- **Sign-in for the model.** Installing and playing games need no model. Build needs a provider available in the
  **hermretro** profile; do not assume a provider set up elsewhere will carry over. Use **Open provider settings**
  and check that **Applies to** is set to `hermretro`, or run `hermes -p hermretro model` in a terminal.
- **Hardware is optional.** Device detection, streaming, flashing and capture stay off until you turn on
  **Chromatic hardware tools** in the plugin settings, and writing a cartridge, streaming and driver setup ask for your approval first (unless Approvals are
  turned off in Hermes). Firmware
  and activation stay in ModRetro's own Firmware Updater (the Setup page links its guide). ModRetro publishes its
  device software for macOS and for Linux on x64 and ARM64 (glibc 2.39 or newer). Capturing a real Chromatic's
  video works on macOS only: Linux device capture says it is unavailable. The hardware tools have not been tested on
  a device yet.

### The studio profile

The first setup step creates a dedicated **hermretro** profile: it has the plugin and its skills turned on and
leaves the profile you installed into unchanged. Chromatic chats open in that profile and nowhere else: the
plugin's tools, skills and system-prompt text exist only there, and Build and game chats never fall back to
another profile (the Build page offers **Repair** instead). In the profile you installed
into, only the page's own setup and library calls answer. Its personality is `profile/SOUL.md`. The profile links
to the plugin you installed rather than copying it, so both profiles share one plugin folder; every profile shares
hermretro's own folder (below).

### Updating

When a new release is out, a card in the corner of the HermRetro page shows what changed, and an **Update ready**
chip appears at the end of the header (the Setup page's hermretro row says so too). Press **Update**: Hermes updates
the copy in the profile you installed it into, the page reloads the plugin in the hermretro profile (which only links
that copy) and then refreshes itself. Normally no restart is needed; if the chip says **Restart to finish**, quit
and reopen Hermes. An update waits while a game is being built or the game tools are installing, then starts by
itself. An update made elsewhere (a terminal, Capabilities > Plugins) is loaded by the page on its own.

### If something goes wrong

- **The download list or tools check failed.** Use **Check again**. No new download starts without a list to review.
- **The install stopped.** Reopen HermRetro to see its state. **Cancel** stops an install running from the page;
  choose **Install again** after cancelling, or **Try again** after a failure. Finished parts are kept.
- **The install finished but the tools check failed.** Use **Check again**; when required tools are still missing,
  **Retry install**.
- **Ask Hermes to fix it** puts the error into a chat in the **hermretro** profile, not sent. When that profile is
  not set up yet, it copies the request to the clipboard instead and asks you to set the profile up first.
- **A step broke later.** The other pages show a Repair banner; the Setup page has one step per part, with
  **Check again** when the tools check fails, and once setup is done **Check everything again** checks it all again.
- **Start the tools over.** Setup's **Remove downloaded tools**, then install again. Your games are not touched.
- **From a terminal or a chat instead.** `hermes plugins install ThePickle31/hermretro --enable` installs the
  plugin; `hermes plugins update hermretro` (in the profile you installed it into, never inside the hermretro
  profile, which Hermes refuses) updates it, after which quit and reopen Hermes. The game tools can also be
  installed by asking Hermes in a hermretro chat: *"Set up hermretro so I can create games, build ROMs, and run
  automated playtests."*


## What works today

| Area | State |
|---|---|
| All 81 original tools, as `chromatic_*` | Registered with exact schemas; a real model turn has created, built and playtested a project |
| Real emulator frames reaching the model | Proven with a vision model |
| One private engine worker per conversation | Proven across separate chats, resumed chats, delegation and compaction |
| Skills (`hermretro:setup`, `game-planning`, `authoring`, `pixel-art`, `rom-debugging`, `deployment`) | Adapted from the originals |
| hermretro page: Build, Setup, Games, Emulator | Built; see below and `.agents/skills/hermretro-dev-page/SKILL.md` |
| Playing inside Hermes | The Emulator page runs ModRetro's own player with the game you pick on the Games page (a demo cartridge until you pick one). When a game is ready to try, the agent calls `chromatic_present_game` and the emulator opens in a tab beside the chat |
| Annotations from the player (Ask Hermes) | Built; not yet verified with a live agent |
| Hardware (discover, stream, capture, flash) | Off by default, behind a setting and Hermes's approval prompt. Not tested on a device |

Tested so far on Linux x64 (including the Desktop install above); macOS (Apple Silicon and Intel) runs the unit tests and a real broker in CI.

## How it is built

- `engine/` — hermretro's engine, started from ModRetro's Chromatic engine 1.0.34 (MIT; its
  changes are listed in `engine/CHANGES.md`) and verified against a manifest.
- `backend/` — the Hermes side, one folder per feature. `broker/` is the single authority on the machine: it gives each conversation
  its own engine worker, coordinates writers on the same project, and gates hardware. Tool handlers and the
  desktop page are its clients.
- `page/` — the Hermes Desktop page: `app/` (shell, routing, backend calls), one folder per page under
  `pages/` with its tabs and areas inside, `shared/` and `frame/`. `tools/bundle/bundle.mjs` bundles it into
  `desktop/plugin.js`, the single file the app loads (generated and committed, because installing a plugin
  runs no build). On first use the page shows only a guided setup: welcome, the full
  list of what gets downloaded (version, source, size, purpose), the install itself with live progress and
  checksums (run by the page, not a chat), whether you have a Chromatic, and your first game idea. After that,
  one segmented control for its pages (it opens on Build):
  - **Setup**: one step per page, advancing by itself as the backend verifies each step; a physical
    Chromatic is optional. A step that breaks later shows a Repair banner on the other pages.
  - **Games**: your library as cartridges: play, install on a Chromatic (through the chat's approval),
    open the game's chat, or start a new game on Build.
  - **Emulator**: ModRetro's real player, served by the plugin (`backend/player/server.py`).
    Personal finishes use the same `<id>/skin.webp` or `skin.png` and optional `skin.json` under `<hermretro home>/skins/`. A valid personal skin with the same ID overrides the bundled finish and survives plugin updates.
  - **Build**: one game, one conversation with HermRetro. Start with **Build it** or **Plan first**. When a turn has built the game, you play it
    right in that turn's build card, at a whole-number scale, with a play-test checklist from the build
    report beside it and Annotate to point HermRetro at sprites and tiles in the game.

  The page talks to the backend through `plugin.hermretro.*` RPCs, each declared by its backend feature
  (`backend/<feature>/rpcs.py`; every name and shape in `.agents/skills/hermretro-dev-architecture/references/contract.md`). The plugin's own agent tool `chromatic_present_game` shows a
  finished game to the user in the emulator beside the chat; builds open nothing by themselves.
- `skills/` — agent skills.
- `engine/contract/` — the engine's pinned tool contracts and file manifest.
- `tests/` — mirrors the code (`backend/<feature>/`, `page/`, `repo/`, `acceptance/`); the full folder map is in
  `.agents/skills/hermretro-dev-architecture/references/architecture.md`.

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
| `.cache/` | Downloaded tools (GB Studio, GBDK, the emulator, about 2.3 GB) and ModRetro's CLI (`engine-<version>/`); safe to delete, setup downloads them again |
| `run/` | The background broker's socket, logs and lock |

Removing or updating the plugin leaves this folder alone, so your games stay. A full `hermes uninstall`
removes the whole Hermes home, this folder included: copy `games/` somewhere first. `HERMRETRO_HOME` moves
the whole folder; `HERMRETRO_GAMES_DIR` moves just the games.

The engine keeps one small folder of its own in your home folder, outside the Hermes home, only once a physical
Chromatic is used: `~/.codex-gb-studio/chromatic/` (its record of device operations such as flashing). "Remove
downloaded tools" and uninstalling leave it; delete it by hand if you no longer use a Chromatic.

Upgrading from 0.0.4 or older: those kept downloads in `deps/` and games in `games/` inside the plugin folder,
and the shelf in `~/.local/state/chromatic-studio/`. Copy any games you want out of `games/`, then delete
both folders before updating (Hermes refuses to update a plugin folder holding the old 2.4 GB `deps/`),
and set up again from the hermretro page; nothing is moved for you.

## Test

`python tools/check.py` runs the fast checks the same way CI does (`full` adds the acceptance run; see
`AGENTS.md`). The pinned dev tools are set up once with `python tools/dev setup`: ruff (the Python linter and
formatter, into `.dev/py`), the page's npm tools and the engine's build tools. `python tools/check.py fix`
applies the automatic lint fixes (a bare `# noqa: E402` gets its standard reason) and the Python formatting.
The individual commands:

```sh
python -m unittest discover -s tests -t .                   # fast unit tests (no Hermes needed)
node tools/bundle/bundle.mjs --check                            # the generated files match page/
node tools/engine/bundle.mjs --check                            # the engine's dist/server.js matches its modules
node --test 'tests/page/**/*test*.mjs'                # page tests, including the built page in jsdom
HERMRETRO_DEPS_ROOT=<folder> python tools/ci/prepare_toolchain.py   # the toolchain the acceptance run needs, in <folder>
HERMRETRO_DEPS_ROOT=<folder> python tests/acceptance/broker_acceptance.py   # real engine, compiler and emulator (~2 min)
python tools/ci/clean_install_check.py                      # clean install into a throwaway Hermes home
python tools/ci/clean_install_check.py --update-from        # the newest release, updated to this commit
hermes -p hermretro tools list                           # the chromatic toolset, only in that profile
```

`hermes plugins doctor` registers the plugin in a temporary Hermes home that is not the `hermretro` profile, so
it reports every tool and hook as "declared but not registered". That is expected; `clean_install_check.py`
checks registration where it matters.

The page test glob already includes the page scenario files (`tests/page/page-*.test.mjs`, sharing
`tests/page/harness.mjs`); run one on its own only to read its full output. Run the acceptance test through `python tools/check.py acceptance`, which picks a short temporary
folder: its Unix socket path must stay under 104 characters (macOS's limit; Linux allows 108).

The acceptance run writes its evidence to `notes/evidence/` (git-ignored, like everything in `notes/`).

## Working on the page

Edit the modules in `page/`, never `desktop/plugin.js` or `player/frame-shim.js` (the script the
player frame runs first, from `page/frame/`): both are generated, and the tests fail when they do not
match their sources.

```sh
node tools/bundle/bundle.mjs                                    # build desktop/plugin.js and player/frame-shim.js
node tools/bundle/bundle.mjs --watch                            # rebuild on page/ or backend/hermes/workflow.py saves
node tools/bundle/bundle.mjs --report                           # lines per module
```

The bundler generates the Desktop's RPC names and Build fallback from the backend. Commit the sources and
the rebuilt files together. The bundler and the page tests take esbuild,
TypeScript, jsdom and React from the pinned `tools/npm/` (or a Hermes Desktop checkout; `tools/bundle/node-modules.mjs`
has the search order). The plugin itself has no npm dependencies, and users never install `tools/npm/`. It also checks the source tree on every build: only `sdk.js` imports
packages, imports across folders use the aliases (`#sdk`, `#app/`, `#pages/`, `#shared/`, `#frame/`, `#backgrounds/`) and none
climbs a folder, no import cycles, no file over 400 lines (three large components are
listed as exceptions in `tools/bundle/lint.mjs` until they are split). Where code goes
is described in `.agents/skills/hermretro-dev-page/references/source.md` ("The page's source").

## Contributing

For development, link a checkout instead of installing the plugin:

```sh
mkdir -p "${HERMES_HOME:-$HOME/.hermes}/plugins"
ln -s /path/to/hermretro "${HERMES_HOME:-$HOME/.hermes}/plugins/hermretro"
hermes plugins enable hermretro
```

Then turn on **hermretro** under Capabilities → Plugins and open **HermRetro** from the sidebar, as above. To try
the agent side from another profile, `HERMRETRO_EVERY_PROFILE=1` in the gateway's environment loads its tools,
skills, hooks and prompt in every profile that has the plugin on; the Build page still uses only the `hermretro`
profile.

Start with `.github/CONTRIBUTING.md`; the development skills are in `.agents/skills/` (AGENTS.md lists them). Report security
problems privately (`.github/SECURITY.md`).

## Licence

MIT for this repository's own code. The bundled engine and the proprietary ModRetro CLI inside it have their
own terms: see `THIRD_PARTY_NOTICES.md`. For original, user-created ROMs only.
