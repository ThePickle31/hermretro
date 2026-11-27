# ModRetro Chromatic: setup

hermretro can author, build, and
directly playtest games without the GB Studio desktop editor. The plugin ships
installers and a shared dependency catalog, not every third-party binary.
Necessary dependency preparation is part of an authorized request to create,
build, or preview a game, unless the user limits downloads or changes. Hermes
performs that setup in hermretro's own folder (`~/.hermes/hermretro/.cache/`) and asks only for
missing scope or required platform permission.

The plugin does not include the standalone GB Studio compiler or PyBoy
emulator. Setup installs the pinned GB Studio 4.3.2 compiler and PyBoy 2.7.0
separately when the requested components need them. ModRetro's Chromatic
device CLI is a separate supplier component, installed on request with
`chromatic_studio_device_cli`; its embedded Binjgb runtime and
required third-party notices remain intact.

Ask Hermes for the work you want to do:

> Use the hermretro plugin to make a small playable game and show me
> its browser preview. Prepare any missing dependencies in a dedicated tools
> folder.

The [setup skill](../SKILL.md) carries this through with
`chromatic_toolchain_prepare`. The commands below are reference material for the agent;
users do not need to copy them into a terminal. hermretro itself needs
Node.js 22 or newer.

## Choose capabilities, not a desktop application

Pass `--components` explicitly rather than relying on the broader
`runtime,build,emulator` default. Use `runtime` for source inspection or edits
without a build, or Chromatic device tools with an existing ROM;
`runtime,build` to create or iterate a playable game, compile it, or show an
official browser preview; `runtime,emulator` to playtest an existing ROM;
and `runtime,build,emulator` for the edit/build/play loop. Add `desktop` only
when the user wants the visual editor. Use the same selection and `--root`
for plan, apply, and the follow-up doctor.

| Component group | What setup prepares | Required for |
| --- | --- | --- |
| `runtime` | Compiled plugin and locked production npm dependencies | Project inspection/authoring, ROM inspection, and Chromatic device tools through MCP |
| `build` | Official GB Studio CLI and GBDK | Native game project builds and official browser exports |
| `emulator` | Isolated Python, PyBoy, and Pillow; managed uv when needed | Direct stepped play and real-frame observation |
| `desktop` | Optional official GB Studio editor distribution | Visual editing in the desktop application |

Node is the prerequisite for the shared setup manager and MCP runtime. A
standalone C build needs GBDK but does not establish project-build readiness.
The doctor task `play` describes the complete edit/build/play path, including
the build dependencies; emulator-only setup does not make that whole path ready.
Official browser playback uses Binjgb from the CLI export, not PyBoy.
The public Chromatic `chromatic_setup` tool handles driver installation and cartridge
detection; it does not prepare the plugin's dependencies. Device actions keep
their own [selection and consent requirements](../../deployment/references/chromatic-device-testing.md).

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
`chromatic_toolchain_doctor` use the same dependency definitions. After the launcher has a
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
sh "/absolute/path/to/plugin/scripts/setup.sh" doctor --root "$HOME/chromatic-tools" --components runtime,build,emulator --probes cli-version,gbdk-version,emulator-import
```

Or, once MCP is running:

```text
chromatic_toolchain_doctor {"tasks":["authoring","projectBuild","play"]}
chromatic_toolchain_doctor {"tasks":["play"],"probes":["cli-version","gbdk-version","emulator-import"]}
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

Choose an absolute, dedicated `--root` outside the plugin package and immutable
cache. It must not enclose the plugin either, except for passive doctor above.
Setup accepts a new/empty directory or one carrying its ownership marker.
It refuses nonempty unowned roots and redirected setup paths; do not use a game
directory or select an existing shared toolchain for
adoption. `GB_STUDIO_SETUP_ROOT` selects the managed root; hermretro sets it to
`~/.hermes/hermretro/.cache/toolchain` for every engine worker.

The root contains separate `node`, `runtime`, `toolchain`, staging/cache, and
receipt locations. Yarn uses one archive cache inside this root;
separate setup roots remain isolated. Each toolchain still needs its own
`node_modules`. Setup does not migrate or delete older caches.

Setup does not change global Python, shell
profiles, `PATH`, OS application registration, marketplaces, installed plugin
bindings, or active MCP sessions. Keep prepared dependency paths available if
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

Preparing dependencies does not install, replace, enable, or refresh the plugin:
Hermes installs and updates hermretro itself. A request only to prepare
dependencies is not authority for anything else.

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
