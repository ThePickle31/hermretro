# Engine setup

In hermretro, setup runs from the hermretro page, or the agent's
`chromatic_toolchain_prepare` and `chromatic_toolchain_doctor`, into hermretro's
own folder (`~/.hermes/hermretro/.cache/` by default). The engine runs inside
hermretro; running it on its own is not supported. This guide covers the setup
manager underneath: its components, pins, readiness and recovery, and the
commands a maintainer can use to inspect or repair a setup root by hand.

The engine can author, build, and directly playtest games without the GB Studio
desktop editor. It ships installers and a shared dependency catalog, not every
third-party binary. Necessary dependency preparation is part of an authorized
request to create, build, or preview a game, unless the user limits downloads or
changes. The agent performs that setup in a separate owned dependency directory
and asks only for missing scope or required platform permission.

The plugin does not include the standalone GB Studio compiler or PyBoy
emulator. Setup installs the pinned GB Studio 4.3.2 compiler and PyBoy 2.7.0
separately when the requested components need them. The Chromatic device CLI
is a separate supplier component, installed only for hardware; its embedded
Binjgb runtime and required third-party notices remain intact.

Ask Hermes for the work you want to do:

> Make a small playable game and show it to me. Prepare any missing
> dependencies.

[hermretro's setup skill](../../skills/setup/SKILL.md) prepares the
dependencies and checks readiness. The commands below are reference
instructions for the agent and maintainers; users do not need to copy them into
a terminal. No manual Node/npm installation is required: the OS-shell setup
entrypoint can prepare the pinned runtime.

## Where the engine comes from

hermretro ships this engine inside the plugin and runs it from there; installing
the Chromatic CLI for hardware prepares a copy of it in hermretro's own folder
(see the [engine's README](../README.md)). There is no separate compiled release
to obtain or add.

## Preview an existing project

In hermretro, each game is opened and edited in its own conversation, from the
Build page. Selecting, building and showing it follow
[hermretro's authoring skill](../../skills/authoring/SKILL.md#select-the-intended-project).
Keep custom launchers such as `tools/preview.mjs` and project scripts intact;
the engine does not need to rewrite them to preview your game.

The engine tools involved (hermretro names each `chromatic_<name>`):

| Tool | Role |
| --- | --- |
| `session_status`, `project_select`, `project_inspect` | The current selection, selecting a project, and its resources |
| `toolchain_doctor {"tasks":["projectBuild"]}` | A passive check of the build dependencies; `toolchain_prepare {"components":["build"]}` or the hermretro page prepares missing ones, never the shell commands below |
| `rom_build` | The ROM (`make:rom`) |
| `web_build` | Builds or reuses the web export (`make:web`) |
| `web_preview` | Serves that export as the engine's own preview; hermretro shows the game with its own `chromatic_present_game` instead |

The web copy uses the official GB Studio `make:web` compiler and the engine's
player controls. It does not run your npm scripts or import behavior from a
custom preview launcher. Keep the launcher and game source unchanged; any
custom behavior still needs a separate review. For a physical Chromatic feed,
follow the [capture steps](chromatic-device-testing.md#capture-the-physical-device)
instead of modifying a browser launcher.

## The setup manager by hand

These commands are a maintainer's way into the setup manager, for inspecting or
repairing a setup root. They work on the root you name; hermretro reads only its
own (`GB_STUDIO_SETUP_ROOT`, `~/.hermes/hermretro/.cache/toolchain` by default).
Hermes installs and updates the plugin; that is separate from dependency setup.
The setup scripts are in the engine's `scripts/` folder inside the installed
plugin. Do not run `npm install` or `npm run setup` in the plugin folder.

Name the root hermretro actually uses: `toolchain_doctor` reports it as
`roots.setupRoot`. The shell launcher finds Node in that root or on `PATH`, not
in Hermes's own tool store; when the only Node is Hermes's, put the folder of
the Node executable the doctor reports first on `PATH`. On macOS/Linux, start
with the POSIX-shell entrypoint:

```sh
root="<roots.setupRoot from toolchain_doctor>"
sh "/absolute/path/to/engine/scripts/setup.sh" doctor --root "$root" --components build
sh "/absolute/path/to/engine/scripts/setup.sh" plan --root "$root" --components build
```

On Windows x64, use PowerShell 5.1+; see [Windows setup](windows-setup.md):

```powershell
powershell.exe -NoProfile -File "C:\path\to\engine\scripts\setup.ps1" doctor --components build
powershell.exe -NoProfile -File "C:\path\to\engine\scripts\setup.ps1" plan --root "C:\chromatic-tools" --components build
```

The OS shell and its download/archive facilities must be available. The launchers
do not assume a Node runtime inherited by MCP. They check
an available Node with `--version`; this bootstrap-prerequisite check is disclosed
separately from component probes. If no compatible Node is available, the result
is **bootstrap-only**, showing the pinned official Node download and destination,
not a complete dependency diagnosis. `doctor` and `plan` never install Node.

These examples prepare a playable game and its browser preview. Choose the
components below for other work. Review the plan against the user's request;
necessary setup does not require a fresh confirmation at every step. Keep
doctor and plan passive, then apply the authorized plan. For example, on
macOS/Linux:

```sh
sh "/absolute/path/to/engine/scripts/setup.sh" apply --root "$root" --components build --yes
sh "/absolute/path/to/engine/scripts/setup.sh" doctor --root "$root" --components build --json
```

PowerShell accepts the same positional commands and `--options`. `--yes` records
the caller's explicit setup choice; it must not be inferred from a lifecycle
hook, a connected MCP server, or whether a shell approval prompt appears.

## Choose capabilities, not a desktop application

Pass `--components` explicitly rather than relying on the broader
`runtime,build,emulator` default. hermretro's engine is bundled, so it needs no
`runtime` component: source inspection, edits without a build, and Chromatic
device tools with an existing ROM need no build dependencies (device tools need
the [Chromatic CLI](chromatic-device-testing.md) instead). Use `build` to create or
iterate a playable game, compile it, or show an official browser preview;
`emulator` to playtest an existing ROM; and `build,emulator` for the
edit/build/play loop. Add `desktop` only when the user wants the visual editor. Use the same selection and `--root`
for plan, apply, and the follow-up doctor.

| Component group | What setup prepares | Required for |
| --- | --- | --- |
| `runtime` | Compiled engine and locked production npm dependencies (an unbundled engine only) | Nothing in hermretro: its engine is bundled |
| `build` | Official GB Studio CLI and GBDK | Native game project builds and official browser exports |
| `emulator` | Isolated Python, PyBoy, and Pillow; managed uv when needed | Direct stepped play and real-frame observation |
| `desktop` | Optional official GB Studio editor distribution | Visual editing in the desktop application |

Node is the prerequisite for the shared setup manager and MCP runtime. A
standalone C build needs GBDK but does not establish project-build readiness.
The doctor task `play` describes the complete edit/build/play path, including
the build dependencies; emulator-only setup does not make that whole path ready.
Official browser playback uses Binjgb from the CLI export, not PyBoy.
The public Chromatic `setup` tool handles driver installation and cartridge
detection; it does not prepare the plugin's dependencies. Device actions keep
their own [selection and consent requirements](chromatic-device-testing.md).

New installs use the catalog pins below. Compatible healthy dependencies in the
owned root can be reused; install pins and compatibility requirements are not
the same claim.

| Dependency | New-install version | Compatibility requirement |
| --- | --- | --- |
| Node.js | 24.15.0, with its npm | Node 22+; runtime preparation also needs a compatible sibling npm |
| GB Studio CLI / optional editor | 4.3.2 | 4.3.2 |
| GBDK | 4.5.0 | 4.5.0 |
| Python | Managed CPython 3.13.12 | Isolated Python 3.13 |
| PyBoy | 2.7.0 | 2.7.0 |
| Pillow | 12.3.0 | 11.x or 12.x |
| uv | 0.12.6 | Installer-only; unnecessary when the emulator is already healthy |

The CLI is built from pinned official GB Studio and GBVM source archives with
pinned Yarn 4.4.1. This path does not require Git, Corepack, or a global Yarn
installation. Source archive hashes and build provenance are retained; no
game-engine patch is part of setup. Runtime npm installation uses the packaged
public-registry production lock with lifecycle scripts disabled. This is not a
claim that every downloaded dependency or reused installation is byte-identical.

## Read doctor results correctly

The shell entrypoints, `scripts/doctor.mjs`, setup planning, and MCP
`toolchain_doctor` use the same dependency definitions. After the launcher has a
Node runtime, default detection reads bounded files and version metadata; it
does not run compilers, import Python packages, load a ROM, or install anything.

Each component reports `ready`, `missing`, `broken`, `incompatible`, or
`unsupported`, its required and detected version, selected path, provenance,
evidence, and next steps. `ready` means **compatible metadata**, not executable
health or a successful game build. Missing version evidence is not silently
treated as readiness.

Task readiness is separate for `authoring`, `projectBuild`, `cBuild`, `play`, and
`desktop`. Overall `ready` requires every requested task, not “CLI or GBDK.” The
optional editor and installer-only uv do not block tasks that do not need them.

When executable checks are wanted, name them explicitly:

```sh
sh "/absolute/path/to/engine/scripts/setup.sh" doctor --root "$root" --components build,emulator --probes cli-version,gbdk-version,emulator-import
```

Or, once MCP is running:

```text
toolchain_doctor {"tasks":["authoring","projectBuild","play"]}
toolchain_doctor {"tasks":["play"],"probes":["cli-version","gbdk-version","emulator-import"]}
```

These bounded probes execute only CLI `--version`, GBDK `-v`, and isolated
Python imports respectively. Their results and `probesPassed` remain separate
from metadata readiness. They do not build a project or boot an emulator ROM.
`plan` and `--dry-run` reject probes and perform no installation or component
probe; `--dry-run` selects the passive plan even when supplied with `apply`.

## Roots and immutable packages

Without `--root`, doctor inspects configured runtime/toolchain bindings. That is
inspection, not permission to repair those locations. With `--root`, doctor
inspects that managed target instead.
Plan/apply always target the owned setup root, not an existing bound toolchain.

The passive shell doctor can also run from `<root>/runtime` with the enclosing
`--root`. It still requires the setup ownership marker and never changes that
root. Use the original compiled package outside the managed root for plan,
apply, or doctor with executable `--probes`.

Choose an absolute, dedicated `--root` outside the plugin. It must not enclose
the plugin either, except for passive doctor above.
Setup accepts a new/empty directory or one carrying its ownership marker.
It refuses nonempty unowned roots and redirected setup paths; do not use a game
directory or select an existing shared toolchain for
adoption. `GB_STUDIO_SETUP_ROOT` selects the default managed root. Otherwise:

| Platform | Default dependency root |
| --- | --- |
| macOS | `~/Library/Application Support/modretro-chromatic` |
| Linux | `$XDG_DATA_HOME/modretro-chromatic`, or `~/.local/share/modretro-chromatic` |
| Windows | `%LOCALAPPDATA%\modretro-chromatic` |

The root contains separate `node`, `runtime`, `toolchain`, staging/cache, and
receipt locations. Yarn uses one archive cache inside this root;
separate setup roots remain isolated. Each toolchain still needs its own
`node_modules`. Setup does not migrate or delete older caches.

Setup does not change global Python, shell
profiles, `PATH`, OS application registration, the installed plugin, or active
MCP sessions. Keep prepared dependency paths available if
a later installation binds to them.

## Failure, retry, and cancellation

Apply serializes work through the selected root's `.setup-lock`. A second apply
fails with the lock information; it never steals the lock or kills its owner.
After a crash, verify that the recorded process has ended before preserving or
moving the stale lock. Do not remove a lock just to make another run proceed.

Per-component outcomes and errors remain in `runs/<run-id>.json` and
`last-run.json`; component receipts record owned destinations and preparation
state. Successful earlier components remain available after another component
fails. Inspect the error, resolve its cause, then repeat the same explicit apply
command. Healthy tools are checked and reused. Known-owned partial destinations
are preserved in quarantine before repair; unowned occupied paths are not
overwritten. Damaged/partial downloads must pass pinned verification before use.

Cancel with the normal terminal interrupt. Setup stops its owned subprocesses,
retains completed/partial outcomes, and releases its own lock when possible.
Read any cleanup error separately: cancellation is not a rollback of everything
already installed. After a forced process exit, inspect retained state before
retrying. Never stop unrelated Node, Python, compiler, or game processes.

Some optional desktop archives contain links that the bounded extractor will
not materialize. Such a result is `manual-step-required` or
`downloaded-not-installed`, with the retained archive and next steps—not a ready
editor. Setup never launches the desktop application.

## Preparation is not activation or gameplay acceptance

Setup prepares dependencies; it does not change the engine hermretro runs. In
hermretro, check read-only `chromatic_session_status` and the relevant
`chromatic_toolchain_doctor` tasks in the conversation, then make a real build
with `chromatic_rom_build` and play it: metadata readiness, probe
results, an official build and actual gameplay are separate evidence.

Packaged targets are macOS and Linux x64/arm64, plus experimental Windows x64.
Windows ARM64 is unsupported. A targeted `linux-*-gnu` distribution requires
glibc 2.39+ during runtime preparation and MCP startup, even for
`--components runtime` and authoring-only use. A universal distribution leaves
non-hardware authoring startup available without that vendor libc gate;
Chromatic device commands retain their supported-target checks. This does not
extend the setup platforms listed above.

Source tests, stubbed platform tests, a clean
dependency root on a prepared host, and a clean-machine native installation are
different evidence. A doctor probe is not an official build, and a build is not
direct gameplay acceptance. Report the actual platform and checks performed.

Existing checkout-oriented `setup:compiler` and `setup:emulator` scripts remain
advanced compatibility paths, not the primary setup workflow. Their `--dry-run`
is detection/planning only; `--use-existing` on a legacy sub-installer does not
make every surrounding preparation step read-only.
