# Platform and setup boundaries

macOS and Linux support x64 and arm64. hermretro does not support Windows.

Targeted Linux distributions require GNU/Linux with glibc 2.39+ for runtime
preparation and MCP startup, including authoring-only use. Universal packages
do not impose that vendor libc gate on non-hardware authoring startup;
Chromatic device operations still require a supported target. Choose the
artifact accordingly and report only the platforms actually qualified.

If MCP cannot start, follow the [setup skill](../../setup/SKILL.md)
and [packaged setup reference](../../setup/references/setup.md). Do not loop on unavailable MCP calls.
Prepare dependencies with `chromatic_toolchain_prepare` in hermretro's own `.cache/`
folder (Node.js 22+ comes first, as a plugin requirement); do not shift runnable
setup commands to the user or assume a global Node/Python installation. Never
run npm setup inside an immutable cache. A launcher Node `--version` check is
disclosed separately from the full passive dependency report.

## Check readiness

Once MCP is available, `chromatic_toolchain_doctor {}` reads metadata without executing
compilers or Python. Inspect component states, required/detected versions,
provenance, roots, and readiness for the requested task. `ready` is compatible
metadata, not a successful build or emulator session. For explicit executable
checks, select only the needed named probes:

```text
chromatic_toolchain_doctor {"tasks":["authoring","projectBuild","play"]}
chromatic_toolchain_doctor {"tasks":["play"],"probes":["cli-version","gbdk-version","emulator-import"]}
```

## Prepare what the task needs

Doctor and plan never install. New or iterated playable games require
`runtime,build`, including browser previews. Use `runtime` alone for source
inspection, edits without a build, or device tools with an existing ROM; add
`emulator` for local stepped play and `desktop` only when requested. Use the same
root and selection for plan, `apply --yes`, and doctor. Carry necessary setup
through for the authorized game workflow unless the user limits downloads or
changes; ask only for missing scope or required platform approval. Preserve existing
bound toolchains, active games/previews, partial outcomes, and lock ownership.
`--use-existing` on a legacy sub-installer is not a promise that its whole front
door is read-only. The public Chromatic `chromatic_setup` tool handles device operations,
not dependency installation.

Hermes installs and updates the plugin itself; [preparation is not activation](../../setup/references/setup.md#preparation-is-not-activation-or-gameplay-acceptance).
After preparation, complete the requested real build or browser export. Do not stop at a
passive readiness report or give the user manual Node/npm installation work.
Do not infer local Git credentials from a
connected GitHub app, or treat a lifecycle hook/approval UI as installation
consent. On Windows use local paths, preferably short paths on `C:`; UNC/network
roots are unsupported and upstream GBDK has path limitations on other drives.
