# hermretro's engine

The local MCP server behind hermretro's game tools. It edits GB Studio projects, builds ROMs with GB Studio's CLI and
GBDK, runs them in PyBoy for stepped playtesting and recordings, serves the browser preview, and reaches a ModRetro
Chromatic through ModRetro's Chromatic CLI.

It started from ModRetro's Chromatic plugin for Codex, release 1.0.34 (MIT, see [License](#license)). hermretro
maintains it as `hermretro-engine`, from version 2.0.0: every change since 1.0.34 is listed in
[`CHANGES.md`](CHANGES.md), and the tag `engine-upstream-1.0.34` holds that release as published.

## How hermretro runs it

- **The launcher.** hermretro's broker starts one engine per conversation with `scripts/start-mcp.mjs`, which checks
  the platform `package.json` names and starts `dist/server.js`. It runs from this folder in the plugin, or, once
  the Chromatic CLI is installed for hardware (`chromatic_studio_device_cli`), from a prepared copy under
  `~/.hermes/hermretro/.cache/engine-<version>-<digest>/` (by default) that also holds the CLI build for the computer.
- **Setup.** The hermretro page installs the toolchain through the engine's `toolchain_prepare` tool, with the `build`
  and `emulator` components: the pinned GB Studio CLI and GBDK, and an isolated Python with PyBoy, under hermretro's
  own folder. The Chromatic CLI is a separate install, for hardware only.
- **The manifest.** The plugin starts only an engine whose files match `contract/manifest.json`. The record
  (`contract/` and `CHANGES.md`) is not part of it.
- **Tool names.** The guides use the engine's own tool names; hermretro's agent calls each one `chromatic_<name>`.

## Layout

| Path | What it is |
|---|---|
| `src/` | The server's source: one module per file, `entry.js` the server's own, and the player's browser files (`web-annotations/`, `device-capture/`) |
| `dist/server.js` | The bundle, generated from `src/` by `tools/engine/bundle.mjs`; never edited by hand |
| `contract/` | hermretro's record of the engine: its tool contracts and file manifest |
| `CHANGES.md` | Also part of the record: every change hermretro made since ModRetro's 1.0.34, under the version that has it |
| `scripts/` | The launcher, setup and doctor, the emulator worker and the Chromatic CLI runtime, used as they are (the bundle imports some of them) |
| `skills/` | ModRetro's original agent skills, archived as published: they describe ModRetro's plugin, including parts this engine no longer has (Wrecklight, `native_graphics_update`). The ones hermretro gives its agent are adapted from them, in the repository's `skills/` |
| `docs/` | Guides to the tools, setup, playtesting and the device |
| `examples/` | The starter every new game is made from, the `hello-color` demo ROM, and ModRetro's samples |
| `assets/music/` | The bundled music tracks |
| `native/capture/` | The macOS and Linux helpers that capture a Chromatic's video |
| `native-game-plugin/` | An optional GB Studio plugin with a hardware-profile event |
| `third-party/chromatic-cli/` | The provenance, SBOM and notice of ModRetro's Chromatic CLI, which setup downloads |
| `licenses/`, `LICENSE`, `THIRD_PARTY_NOTICES.md` | The licence and the notices of everything the engine includes |

## Modules

`src/` by area: what each part of the engine is, and where its code lives. The engine's reorganization moves each area
into a folder of that name.

| Area | Modules |
|---|---|
| The server | `entry.js` (the server and the tools it registers itself), `tool-domains/` (the other tools, by domain), `engine-root.js` (paths to the engine's own files) |
| The project | `project.js`, `project-files.js`, `project-access.js`, `project-snapshot.js`, `project-session.js`, `project-revision.js`, `project-error.js`, `project-tree-watcher.js`, `native-import-files.js`, `resource-codec.js`, `legacy-project-assets.js` |
| The world index and queries | `project-world-index.js`, `world-queries.js`, `world-script-graph.js`, `custom-event-dependencies.js` |
| Editing a game | `scene-batch.js`, `actors.js`, `triggers.js`, `collisions.js`, `dialogue.js`, `dialogue-preview.js`, `game-scripts.js`, `game-variables.js`, `engine-fields.js` |
| Events | `event-catalog.js`, `native-script-events.js`, `gb-studio-events.json` |
| Building | `build.js`, `build-provenance.js`, `web-build.js`, `compiler-selection.js`, `reviewed-compiler.js`, `toolchain-prepare.js` |
| Debugging a build | `debug-symbols.js`, `source-debug.js` |
| The emulator | `emulator.js` (it drives `scripts/emulator_worker.py`), `playtest-errors.js` |
| Recordings | `recording-common.js`, `recording-archive.js`, `recording-location.js`, `recording-maintenance.js` |
| The browser preview | `web-preview.js`, `web-preview-*.js`, `loopback-listener.js`, `mcp-path-privacy.js` |
| Graphics | `graphics.js`, `graphics-palette-packing.js`, `palettes.js`, `sprites.js`, `scene-graphics.js`, `contact-sheet.js`, `native-sprite-metadata.js` |
| Assets and music | `assets.js`, `audio.js` |
| Tilemaps | `tilemaps.js`, `tilemap-compose.js`, `tilemap-schema.js` |
| The Chromatic | `chromatic.js`, `chromatic-journal.js`, `chromatic-failure-diagnostics.js`, `native-device-capture.js` and the server's side of `device-capture/` (its capture helpers, protocol and schemas) |
| Shared | `platform.js` (paths and the environment on each system) |
| The browser's files | `web-annotations/` (the player page's scripts, served flat by name); in `device-capture/`, the capture page's scripts (`native-client.js`, `native-entry.js`, `device-picker.js`, `native-timing-diagnostics.js`), served with the helpers they import |

Three rules keep it that way, each checked by a test:

- **Paths from `engine-root.js`.** A module that runs in Node takes a path to the engine's own files from
  `engine-root.js` (`enginePath`, `engineUrl`, `ENGINE_ROOT`), never from its own location: in the tests a module runs
  from `src/`, in production from `dist/server.js` (`tests/engine/engine-root.test.mjs`).
- **No import cycles** but the known ones, which the reorganization takes off one by one
  (`tests/engine/imports.test.mjs`).
- **600 lines at most** per module; the files over it when the rule came in are listed in `tools/layout.toml`
  (`tests/repo/test_layout.py`).

## Changing it

The commands run from the hermretro repository root.

1. Change the module in `src/` (or a file in `scripts/`, `skills/` or `docs/` in place).
2. Rebuild the bundle with `node tools/engine/bundle.mjs`; `python tools/check.py engine` fails when it is stale.
3. Raise `version` in `package.json`, the engine's only record of its version, usually by one patch (2.0.0 to
   2.0.1): every change to the engine raises it, and CI fails one that does not (`tools/engine/version.py`).
4. Add the change's line to [`CHANGES.md`](CHANGES.md) under a heading for the new version, and write a fresh
   manifest with `python tools/engine/manifest.py write`.
5. Run `python tools/check.py full`, which includes the real-engine acceptance run.

## Names kept

The engine is hermretro's, but some names from ModRetro's plugin for Codex stay, because games, setup folders or
browsers already hold them: renaming one would break what was made before.

| Name | What holds it | What renaming it would break |
|---|---|---|
| `.codex-rom-build.json`, `.codex-web-build.json` | A game's receipt for its ROM (`build/`) and its web export's record | Every game's ROM and export would be distrusted and built again |
| `.codex-live-demo.json` | The marker of a live-demo save folder | Live-demo saves made before would no longer be found |
| `.codex-setup-*`, `.codex-web-cache/` and the owner `codex-gb-studio-setup` | The setup root's receipts and its marker `.gb-studio-setup.json`, which names that owner (`scripts/setup.*`, `scripts/dependency-doctor.mjs`), and the toolchain's key for signing web exports (on Windows under `%LOCALAPPDATA%\Codex\GBStudio\WebPreview\`) | Setup would no longer recognise its own toolchain, and no export signed before would verify |
| `codex-gb-studio` and the `codex-gb-studio-*` owners and formats | The labels in the engine's stored digests and signatures, its save-state format, and the owners of its journals, locks and saves | No stored revision, receipt, signature or save state would match again |
| `~/.codex-gb-studio/chromatic/` | The device operations journal's default folder (`src/chromatic-journal.js`) | An unfinished device operation would be forgotten |
| `modretro-preview-capture`, `modretro-physical-capture` | The format named in each capture's record, from the preview or a Chromatic (`src/web-preview-captures.js`) | Captures saved before would be refused |
| `codex-captures/` | The preview's URL for recordings, kept in each recording's record; hermretro's player serves the same | Saved recordings would link to nothing |
| `codex-gb-studio:device-color:v1`, `codex-preview-fresh:…`, `codex-preview-flash:…` | The browser's storage | The chosen finish and the preview's state would reset |
| `codex` | The DevDay Edition finish (`player/skins/codex/`), kept as the chosen finish | The finish a player picked would be lost |
| `modretro-chromatic` | The engine's own default setup folder when hermretro does not set one (`scripts/setup.*`, `scripts/start-mcp.mjs`, `scripts/dependency-doctor.mjs`), and the owner in the Chromatic CLI's verified cache marker | A setup made there would no longer be found, and the cache would be refused |
| `~/.modretro-chromatic-runtime/` | The Chromatic CLI's verified cache (`scripts/chromatic-runtime.mjs`) | The CLI would be unpacked and verified again |
| `plugins/modretro-chromatic/` and `EVENT_CODEX_HARDWARE_PROFILE` | The optional GB Studio plugin's folder, copied into a game (`native-game-plugin/`), and its event's id, which a game's scripts name | A game that has it would hold a second copy, and its scripts would name an event that no longer exists |

Names nothing stores or shows stay too: the preview's other URL paths (`codex-states/` and the rest) and its
`X-Codex-*` headers, page element names such as `codex-game-view`, and `codex-chromatic-uac` in the Windows elevation
helper. hermretro's player and page share several of them.

## Checking setup

In hermretro, the agent's `chromatic_toolchain_doctor` reports the toolchain without changing anything, and the page or
`chromatic_toolchain_prepare` repairs it. [docs/setup.md](docs/setup.md) explains the components, their pins, readiness
and recovery, and the setup manager's own commands for inspecting or repairing a setup root by hand.

## Developer Mode activation

Use the official [ModRetro Updater](https://support.modretro.com/en_us/articles/chromatic-firmware-updater-ryhoYnzCx)
for Developer Mode activation. The engine does not collect activation codes or manage activation. After completing
the updater workflow, return for fresh device selection and the normal flash confirmation. An earlier failed or
uncertain write is not retried automatically.

## License

The engine is available under the [MIT license](LICENSE). Included examples and cartridge-runtime components retain
their [third-party notices](THIRD_PARTY_NOTICES.md). GB Studio, GBDK, and the separately installed PyBoy emulator
retain their respective licenses; PyBoy is LGPL-3.0-only. Do not redistribute commercial game ROMs or proprietary boot
ROMs.
