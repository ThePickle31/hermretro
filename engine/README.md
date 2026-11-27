# hermretro's engine

The local MCP server behind hermretro's game tools. It edits GB Studio projects, builds ROMs with GB Studio's CLI and
GBDK, runs them in PyBoy for stepped playtesting and recordings, serves the browser preview, and reaches a ModRetro
Chromatic through ModRetro's Chromatic CLI.

It started from ModRetro's Chromatic plugin for Codex, release 1.0.34 (MIT, see [License](#license)). hermretro
maintains it: every change since is listed in [`CHANGES.md`](CHANGES.md), and the tag `engine-upstream-1.0.34`
holds that release as published.

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
| `CHANGES.md` | Also part of the record: every change hermretro made since ModRetro's 1.0.34 |
| `scripts/` | The launcher, setup and doctor, the emulator worker and the Chromatic CLI runtime, used as they are (the bundle imports some of them) |
| `skills/` | ModRetro's original agent skills, archived as published: they describe ModRetro's plugin, including parts this engine no longer has (Wrecklight, `native_graphics_update`). The ones hermretro gives its agent are adapted from them, in the repository's `skills/` |
| `docs/` | Guides to the tools, setup, playtesting and the device |
| `examples/` | The starter every new game is made from, the `hello-color` demo ROM, and ModRetro's samples |
| `assets/music/` | The bundled music tracks |
| `native/capture/` | The macOS and Linux helpers that capture a Chromatic's video |
| `native-game-plugin/` | An optional GB Studio plugin with a hardware-profile event |
| `third-party/chromatic-cli/` | The provenance, SBOM and notice of ModRetro's Chromatic CLI, which setup downloads |
| `licenses/`, `LICENSE`, `THIRD_PARTY_NOTICES.md` | The licence and the notices of everything the engine includes |

## Changing it

The commands run from the hermretro repository root.

1. Change the module in `src/` (or a file in `scripts/`, `skills/` or `docs/` in place).
2. Rebuild the bundle with `node tools/engine/bundle.mjs`; `python tools/check.py engine` fails when it is stale.
3. Add the change's line to [`CHANGES.md`](CHANGES.md) and write a fresh manifest with
   `python tools/engine/manifest.py write`.
4. Run `python tools/check.py full`, which includes the real-engine acceptance run.

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
