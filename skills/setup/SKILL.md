---
name: setup
description: "Prepare missing game compiler or emulator dependencies for an installed hermretro plugin, or diagnose tools that cannot start."
version: 1.0.34
license: MIT
metadata:
  hermes:
    tags: [chromatic, modretro, game-boy, gb-studio, setup]
    related_skills: [hermretro:authoring, hermretro:rom-debugging, hermretro:deployment]
---

# Prepare game dependencies

Follow the shared [agent guide](../authoring/references/agent-guide.md).

Hermes manages plugin installation and updates. A working plugin must not be
recreated, registered in another marketplace, or reinstalled to obtain a compiler.
Never edit the plugin's files, its manifest, Hermes configuration or the receipts
under hermretro's `.cache/` folder. Do not run `hermes plugins install` or `hermes plugins update` during
game dependency setup.

## Diagnose the failed step

Call `chromatic_toolchain_doctor` when available. Authoring/device tools, compiler dependencies,
emulator dependencies, project selection and Developer Mode are separate.
For PROJECT_SELECTION_REQUIRED select the intended project; do not reinstall.
For missing compiler/emulator dependencies use `chromatic_toolchain_prepare` below.
If the Chromatic tools cannot start, report the concrete error; do not manufacture a
replacement plugin. The tools need Node.js 22 or newer; Hermes installs its own, which hermretro uses, so a
missing Node.js usually means Hermes's own tools are incomplete (https://nodejs.org/ otherwise).

## Install only missing dependencies

Prefer `chromatic_toolchain_prepare {"components":["build"]}` for missing compiler tools,
or `["emulator"]` for local play, or both. It plans and prepares dependencies
without replacing the plugin. Show one concise progress update, then continue
the original build/preview after success. Inspect incomplete results before any
retry; a refusal is not permission to switch callers.

Use only this tool. Do not run the engine's setup scripts, or download, unpack or
`pip`/`npm` install these dependencies by hand: the tool verifies every download
against pinned SHA-256 digests, and a manual install is not recognised. If the tool
is unavailable or refused, report it.

- Build or preview a game: `["build"]`.
- Play an existing ROM: `["emulator"]`.
- Build and playtest: `["build","emulator"]`.
- Add `desktop` only when the visual editor is requested.
- Source editing or flashing an existing ROM needs no compiler setup.

Then verify with `chromatic_toolchain_doctor {"tasks":["projectBuild"],"probes":["cli-version","gbdk-version"]}`
(add the `play` task and the `emulator-import` probe for the emulator).
A request to build/play includes necessary dependency setup; do not create an
extra approval step. Preserve real access refusals and unresolved installer locks.

Everything is installed in hermretro's own folder in the Hermes home: every engine
worker gets `GB_STUDIO_SETUP_ROOT` = `~/.hermes/hermretro/.cache/toolchain`, which
`chromatic_toolchain_doctor` reports as `roots.setupRoot`. If it points anywhere else (other
than a root the user configured), stop and report it.
Do not silently repoint or overwrite an independently configured toolchain.
Reuse setup-owned components; never take over an unowned nonempty directory.

After setup, continue the actual requested build in the same installed plugin.
Do not follow legacy docs into local-payload generation or marketplace registration.
When the request includes a build, verify that real project build; metadata readiness alone is not
completion. For a setup-only request, the doctor probes are the verification (see below).

## Device activation and playtesting

Activation is external: link to the official
[ModRetro Updater](https://support.modretro.com/en_us/articles/chromatic-firmware-updater-ryhoYnzCx).
Never collect activation codes or infer code validity from a generic write failure.
Use the deployment skill for installation confirmation and unknown-write recovery.

Show previews in the hermretro emulator with `chromatic_present_game` unless the
user explicitly selects another browser. When browser play is unavailable, use the exact ROM with the supported
local emulator; see [stepped playtesting](../rom-debugging/references/stepped-playtesting.md).

## In hermretro

Everything is installed in `~/.hermes/hermretro/.cache/`, which plugin updates and removal leave alone
(the user's games are beside it in `games/`).

| What | Where (in `~/.hermes/hermretro/.cache/`) | Installed by |
| --- | --- | --- |
| GB Studio CLI, GBDK, uv, Python, PyBoy, Pillow | `toolchain/` | `chromatic_toolchain_prepare` |
| ModRetro's Chromatic CLI (hardware only) | `engine-<engine version>/` | `chromatic_studio_device_cli` |

- For the whole picture call `chromatic_toolchain_doctor {"tasks":["authoring","projectBuild","cBuild","play"]}`;
  add `"probes":["cli-version","gbdk-version","emulator-import"]` to actually run the compiler and import
  the emulator. The hermretro page's Setup steps in Hermes Desktop read the same state and move on by
  themselves once an install verifies.
- When the user only asked for setup, verify with those probes (they run the GB Studio CLI and GBDK and
  import the emulator) and stop there. Do not create a test project to prove it: every project you create
  or select appears on the user's Games shelf, and this chat would stay bound to it, so their first real
  game would need a new chat. Their first game build is the end-to-end check.
- A first toolchain install downloads about 0.7 GB and takes about 2.3 GB on disk on Linux x64; space and time
  vary by system. GB Studio's local build can keep progress on one step for several minutes. If another supported
  installation already downloaded the same files on this computer, the first
  install starts from that download cache (hashes are checked again); the toolchain still goes into
  hermretro's own folder. Tell the user once that it is running and do not call it again meanwhile: a second
  setup or hardware call gets `OPERATION_IN_PROGRESS`.
- The Studio page's first setup step can create a dedicated `hermretro` Hermes profile with this
  plugin and its skills. It links the same plugin folder, and every profile shares hermretro's folder (tools and games).
- **Physical Chromatic only.** Creating, building and emulator-testing games never need ModRetro's CLI.
  When the user wants hardware, call `chromatic_studio_device_cli {"action":"status"}`: `installed` or
  `bundled` needs nothing more; `unsupported` means ModRetro publishes no CLI for this computer. For
  `missing`, tell the user it is ModRetro's proprietary software, downloaded from ModRetro's own npm
  package, and give them the terms link from the status result; then call it with
  `{"action":"install","acceptVendorTerms":true}`. Hermes asks the user to approve the download (approving
  accepts ModRetro's terms) unless they turned Approvals off. If it comes back denied or blocked, stop:
  never fetch or unpack the CLI another way. The install touches no USB port or device; hardware tools use
  it from the next new chat.
- Hardware tools also need **Chromatic hardware tools** turned on by the user in Settings > Plugins >
  hermretro. Drivers and cartridge detection use `chromatic_setup`: load `hermretro:deployment`.
- When done, report what was installed and its versions, `roots.setupRoot`, what was already there and
  what is left for the user, then suggest a first game.

| Result | What it means here |
| --- | --- |
| `UNAVAILABLE` | The game tools cannot run right now. Do what its `nextStep` says: when another copy of hermretro is still running games, tell the user and stop; otherwise the background service could not start (often Node.js 22+ is missing), so report the error. Never build, play or edit the game outside the `chromatic_*` tools instead. |
| `IDENTITY_REQUIRED` | The call came from inside `execute_code`. Call `chromatic_*` tools directly. |
| `PARENT_ONLY`, `LEASE_REQUIRED` | A delegated subagent can only inspect; setup, project selection, edits, emulator and hardware run in the main conversation. |
| `PATH_OUTSIDE_PROJECT` | This chat's engine worker is bound to another project folder: use a new chat. |
| `NEW_GAME_ONLY`, `INSIDE_ANOTHER_GAME` | A New Game chat makes its own project and opens or names no other game; a new project never goes inside another game's folder. Leave `destinationPath` out and create the project. |
| `PROJECT_WRITER_BUSY` | Another chat is editing or building this project right now: wait, or continue there. |
| `HARDWARE_DISABLED` | Hardware tools are off: tell the user where to turn them on; do not retry. |
| `ENGINE_NOT_VERIFIED` | The plugin's engine files were changed: tell the user to reinstall the plugin. |
| `NODE_MISSING` | The Node.js the background service started with was removed while other chats still run games: ask the user to finish or close those chats, then retry. |
