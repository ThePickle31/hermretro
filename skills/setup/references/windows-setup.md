# ModRetro Chromatic: Windows setup

This guide covers the hermretro plugin.

Windows x64 support is experimental. The plugin has portable setup and test
coverage, but a complete native Windows installation, official game build,
installed-plugin launch, and gameplay pass is still required. A successful
compiler check or tests run on macOS/Linux do not establish that whole Windows
workflow. Windows ARM64 is unsupported; Git Bash and WSL are not required.

## Use the packaged PowerShell entrypoint

Ask Hermes to use the [setup skill](../SKILL.md) and
[shared setup flow](setup.md); prefer `chromatic_toolchain_prepare`. The commands here are agent-run or advanced
reference examples, not terminal work required of every user.

Start with a trusted, readable compiled package and PowerShell 5.1+. The new
`scripts/setup.ps1` entrypoint works before MCP starts; it does not require Git
Bash, WSL, preinstalled Python/uv, or the optional GB Studio desktop editor.
Git and Corepack are not prerequisites for its pinned-source CLI build.
If organizational policy prevents running a local script, use the approved
policy/support route rather than changing global execution policy in setup.

Inspect the current bindings, then a dedicated target root:

```powershell
$gbStudioSetupRoot = '<plugin folder>\deps\toolchain'
powershell.exe -NoProfile -File "C:\path\to\plugin\scripts\setup.ps1" doctor --components runtime
powershell.exe -NoProfile -File "C:\path\to\plugin\scripts\setup.ps1" plan --root $gbStudioSetupRoot --components runtime
```

The launcher checks a selected Node executable with `--version`. Without a
compatible Node 22+, it reports only the bootstrap boundary and pinned official
Node source/destination. Doctor and plan do not download or create the root.
They do not claim complete dependency discovery before Node can run the shared
manager. The bootstrap version check is distinct from opt-in compiler/Python
probes.

Review versions, sources, components, and paths before explicitly applying:

```powershell
powershell.exe -NoProfile -File "C:\path\to\plugin\scripts\setup.ps1" apply --root $gbStudioSetupRoot --components runtime --yes
powershell.exe -NoProfile -File "C:\path\to\plugin\scripts\setup.ps1" doctor --root $gbStudioSetupRoot --components runtime --json
```

The examples select only `runtime` for authoring. Use `--components runtime,build`
for builds/browser export, add `emulator` for automatic playtesting, or explicitly
add `desktop` for the visual editor. Omitting the component list defaults to
`runtime,build,emulator`; always select what the user requested. Repeat the
selected `--components` and `--root` on plan,
apply, and doctor so verification checks the capabilities you chose.
`--dry-run` selects a passive plan; it never installs or
runs component probes. See [the shared setup contract](setup.md) for exact pins,
readiness meanings, and `--probes cli-version,gbdk-version,emulator-import`.

Setup prepares an external runtime, verified official CLI/GBDK, and isolated
Python environment in a new or setup-owned root. It never adopts a nonempty
unowned directory, edits `PATH` or profiles, registers an OS application, or
invokes Hermes. Use local drive paths, not UNC paths or network shares; prefer a
short `C:` path because upstream GBDK documents failures with spaces on other
drives. Existing shared toolchains and immutable caches are not repair targets.

The plugin cache deliberately has empty npm scripts. Run the packaged
PowerShell script directly; do not run npm installation/build commands in it.
A complete apply with a ready runtime returns a new future payload and writes
`prepared-mcp.json`. Registration, installation, and any active-session handoff
remain separate.

## What setup reuses and how it fails

The shared manager records component outcomes, rechecks compatible tools, and
retains successful stages when another fails. Downloads use pinned verification;
known-owned partial components are preserved before repair. Retry only after
reading the retained error and resolving its cause. A root lock serializes
installers; no stale lock is stolen and no process is killed merely because its
PID appears in a receipt. See [failure and recovery](setup.md#failure-retry-and-cancellation).

The optional editor may be retained as a verified archive with a manual extraction
step when its links cannot be safely materialized by the bounded extractor.
`downloaded-not-installed` is not desktop readiness; no editor is launched.
