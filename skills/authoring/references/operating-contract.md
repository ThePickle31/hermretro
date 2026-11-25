# Operating contract and evidence

Use the hermretro plugin to author, compile,
and playtest the user's actual native game project. Its authoring, pixel-art, and
ROM-debugging skills share the local MCP server and the operating contract on
this page. Use the [setup skill](../../setup/SKILL.md) for first
installation, updates, or missing dependencies, including before MCP can start.

## Operating contract

GB Studio remains the editor and owns its normal project format. The plugin
provides focused, game-neutral tools for engine operations and efficient
iteration. Express gameplay, story, progression, interactions, and other
game-specific behavior through native project resources, visual-script events,
or project-owned extensions; do not invent game-specific MCP capabilities.

hermretro exposes each engine tool as `chromatic_<name>`:
`chromatic_project_select`, `chromatic_scene_apply`, and `chromatic_emulator_observe` for project work;
`chromatic_device`, `chromatic_setup`, `chromatic_play`, and `chromatic_flash` for physical Chromatic use. See the [device workflow](../../deployment/references/chromatic-device-testing.md)
for explicit selection, driver setup, timed live demos, exact-ROM writes, and operation recovery.

Treat these as separate kinds of evidence:

- Focused project inspection establishes authored source state.
- A source-art preview establishes only a static projection.
- An official GB Studio build establishes that the native project compiled.
- An official GB Studio web export provides a real Binjgb browser player and
  its own genuine cartridge; it is distinct from a native ROM-build result.
- A standalone GBDK C build establishes only that its C source compiled.
- A real emulator capture establishes only the observed ROM, inputs, and frames.
- A vendor live demo emulates on the computer and streams to the Chromatic;
  it does not establish native cartridge performance.

Never substitute a mock cartridge, fabricated browser player, unrelated sample
project, or generated image for the user's actual project or running game.

## Evidence and safety

Keep all project edits, builds, captures, and emulator artifacts inside their
explicitly authorized roots. Preserve authored scenes, events, assets, unknown
fields, custom extensions, compatibility modes, and existing tracked ROMs.
Never replace a tracked cartridge or change another project without permission.

`GB_STUDIO_MCP_PATH_VISIBILITY=workspace-only` preserves usable authorized
project, ROM, and capture paths while redacting unrelated developer-home,
runtime, toolchain, and Python locations from tool responses. Redaction does
not grant additional filesystem authority.

Reinspect changed focused resources before reporting success. Build the actual
project when compilation matters; repeat bounded emulator steps and inspect the
resulting framebuffer when gameplay behavior matters. State exactly which
project, ROM, compiler, input sequence, and frames were verified, and identify
missing compiler, optional emulator, or hardware evidence honestly.

## Domain references

- [Plugin setup skill](../../setup/SKILL.md) and [platform and setup boundaries](platform-and-setup.md)
- [ModRetro project authoring skill](../SKILL.md)
- [Game Boy pixel art skill](../../pixel-art/SKILL.md)
- [ROM build and debugging skill](../../rom-debugging/SKILL.md)
- [Chromatic device and deployment skill](../../deployment/SKILL.md)
