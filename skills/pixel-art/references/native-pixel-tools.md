# Manual pixel work with the native plugin

Use this route for a small exact repair, deliberate hand-placed frames, or a
room built from authored tiles. First check the tools exposed in the current
session. For project edits, select the intended `.gbsproj`; use `chromatic_project_inspect` and a focused
`chromatic_project_inventory` to identify the actual asset, scene, and color mode. Do not
change a different selected project or the bundled template. Standalone source
art can be authored in the workspace before project selection.

## Choose the operation that changes the right data

| Intent | Tool and boundary |
| --- | --- |
| Inspect sprite layout, frames, or bounds | `chromatic_sprite_inspect`, with `includeFrames:true` when needed. |
| Change speed, collision bounds, state animation type/flip behavior, or name | `chromatic_sprite_edit`; it updates native metadata, not pixels, frame drawings, or arbitrary metasprite placements. |
| Inspect an existing PNG or scene budgets | `chromatic_graphics_analyze` or `chromatic_graphics_analyze_scene`; both analyze authored data and do not draw. |
| Create/update a shared four-color palette or assign a scene slot | `chromatic_palette_create`, `chromatic_palette_update`, `chromatic_palette_assign`; background and sprite slots are separate. |
| Change palette slots on an unbound background region | `chromatic_palette_paint`; coordinates are 8 × 8 tiles. It changes native attributes, never the PNG pixels. |
| Replace room tiles in a bound native tilemap | `chromatic_tilemap_inspect`, then exclusive `chromatic_tilemap_edit` with `replace_cells`; it replaces whole 8 × 8 cells with registered atlas tiles, not arbitrary individual pixels. |
| Register finished sprite/background PNGs | `chromatic_asset_import` (one, or several with `assets`); it copies or registers already existing project-local PNGs, creates native metadata and returns the graphics analysis. It does not draw or replace existing assets. |

Do not assume a general PNG drawing tool from a tool's name or an unreleased
example. If the current tool list exposes no operation for individual sprite or
unbound-background pixels, the plugin alone cannot make that bitmap edit. If a
conversion tool is exposed, raster conversion still does not provide arbitrary
per-pixel painting.

## Existing sprite or unbound background

1. Inspect the native resource with `chromatic_asset_inspect`; use `chromatic_sprite_inspect` for
   frames and `chromatic_world_dependencies` when changing which asset a scene or actor
   references. Preserve the original PNG and editable source.
   Before replacing or removing shared art, inspect its dependencies and use
   `chromatic_project_refresh {"mode":"strong"}` before a destructive global reference decision.
2. For a bitmap change that the plugin cannot perform, use an available pixel
   editor or local PNG authoring within the requested art task. Work from the actual source; retain untouched pixels,
   alpha convention, frame bounds, palette, and a before/after comparison. Create
   a new versioned project PNG unless replacement is explicitly in scope. If
   local editing is unavailable or outside scope, report the gap.
3. `chromatic_asset_import` the new resource with its explicit sprite profile
   (and `paletteIndex`) or background palette mode; fix any violation in its
   `analysis`. Inspect the returned asset and deliberately update only the
   intended scene/actor references. A new resource is not automatically assigned.

## Existing bound background

- Read the selected room region and target atlas with `chromatic_tilemap_inspect`; use the
  returned current project revision and exact `pixelsSha256` values.
- Submit one exclusive `replace_cells` operation. Each `before` needs the current
  pixel hash, full palette byte, and full collision byte; each `after` needs the
  registered atlas `tileId`, target pixel hash, and intended full palette byte.
  Preserve the inspected palette byte for a pixel-only change; a palette-only
  change keeps the inspected pixel hash. `replace_cells` preserves collisions.
- Use `set_collision_cells` for collision edits in a separate revisioned
  operation. Preserve the UI/font and caller-reserved palette slots.
  Recipe-backed tilemaps do not support separate `.mono.png` companions.
- If no target tile has the desired individual pixels, author a new atlas source
  PNG within the requested art change. Register a compatible
  extended atlas via `chromatic_tilemap_atlas_create` without changing the meaning of any
  existing tile or primitive. Do not write the bound output PNG directly: that
  leaves its recipe stale. Dry-run, apply with the inspected revision, and
  reinspect if the project changed. See the [exact tilemap contract](../../authoring/references/tilemaps.md#replace-explicitly-selected-pixels-and-palette-bytes).

## New native artwork

- A new sprite/background starts with a real PNG. Author it in the workspace
  with a pixel editor or explicit native cell data, then place it in the selected
  project when integration is requested; `chromatic_asset_import`
  handles registration. Sprite profiles use 16 × 16 static, 48 × 16
  directional, 96 × 16 directional-animated, or `metasprite` for larger frames
  such as 32 × 32; an existing compatible template can supply other layouts.
  See [source colors and import rules](hardware-and-imports.md).
- To create a new background through native tile tools from existing source art,
  register the project-owned atlas with `chromatic_tilemap_atlas_create`, then use
  `chromatic_tilemap_create` to fill a fixed-size background or exactly capture an existing
  scene, and `chromatic_tilemap_edit` to place/fill/stamp named primitives. These tools do
  not create or paint the initial atlas PNG. See [native tilemaps](../../authoring/references/tilemaps.md).
- Use `chromatic_sprite_preview`/`chromatic_sprite_contact_sheet` (with `paletteId`) or
  `chromatic_graphics_preview_scene` for static review; they are enlarged by default, so
  write no zoom scripts. For an in-game appearance claim, build the actual ROM and inspect
  genuine `chromatic_emulator_observe`/`chromatic_emulator_step` frames. For deliberately authored
  movement, see [native animation](prompting-grid-animation.md).
