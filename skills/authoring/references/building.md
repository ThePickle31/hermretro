# Build authentic cartridges

Use `chromatic_toolchain_doctor` when compiler readiness is uncertain. A headless Linux
host needs the official GB Studio CLI and GBDK, not a graphical desktop editor.

After selecting the intended native project, compile and inspect its cartridge:

```text
chromatic_toolchain_doctor {}
chromatic_rom_build {}
chromatic_rom_inspect {"romPath":"<returned ROM outputPath>"}
```

In hermretro every project build writes the game's one ROM, `build/game.gbc` (`build/game.gb` for a monochrome
project), and the playable copy plays that same file (unless batteryless saves are on: GB Studio then compiles
the playable copy without them). Leave `outputPath` out; any other path is refused.

`chromatic_rom_build` invokes the official native game project compiler and validates the
resulting cartridge header. The separate `sourcePath` option instead compiles a
standalone Game Boy C file with GBDK; that probe does not establish that the
native `.gbsproj` compiles.

## Debugging artifacts

Request authenticated same-build debugging artifacts only when required:

```text
chromatic_rom_build {"captureDebugArtifacts":true}
```

The successful native-build response includes compiler `symbols.noi` and
`globals.i` artifacts with SHA-256 evidence tying both files to the exact ROM
from the same build. Those artifacts are unavailable for standalone C builds.
They can authorize explicit source-aware debugging of that exact cartridge;
they do not authorize symbols from an unrelated build or guessed RAM layouts.

## Read the result

Keep original compiler stderr and process outcomes visible; a successful build
returns the end of stdout and keeps the whole output in `logPath`. A
`DEPRECATED_EVENT` diagnostic is a warning about a GB Studio event that still
compiles; nonzero exits, missing cartridges, invalid headers, or mismatched
debugging artifacts are never successful verification.
Use additive `diagnostics`, including any source path, line, and suggested
action, to choose the next focused resource inspection. Preserve the actual
compiler error when no specific diagnosis is supported. The official desktop
editor can [run a selected scene](extensions-and-build.md)
for a quicker local check; normal CLI builds retain the authored starting point.
