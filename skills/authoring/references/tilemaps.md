# Native tilemaps

The tilemap tools build an ordinary native background PNG and its `.gbsres` from named 8 × 8 tiles, keep a room
recipe beside it, and can write the scene's collision from the same tiles. GB Studio stays the editor and compiler.
Rooms have a fixed size and manual colours; this is not a Tiled importer.

## Grid-based games: which route

A maze, puzzle board, top-down town or any room whose walls and floors sit on a grid can be made two ways:

| Route | Use it when |
| --- | --- |
| **Drawn PNG + collision**: draw the background PNG, import it with `chromatic_asset_import`, set it on the scene, then mark walls with `chromatic_collision_edit` rectangles | A few rooms, each drawn once, with art that is not built from repeating tiles (a title, an ending, a hand-painted town). The quickest route. |
| **Recipe tilemap**: an atlas of named tiles, one recipe per room, edited by placing tiles | Many rooms from the same tiles, a layout you will change while tuning (levels, puzzles), or walls whose collision should come with the tile. Placing a wall tile sets its collision. Stamping it somewhere else does not clear the cells it left (painting floor there is decoration and keeps the wall's collision): open them with `set_collision_cells` (below). |

Either way, plan the grid in 8 × 8 tiles: a 16 × 16 gameplay cell is 2 × 2 tiles (make it a 2 × 2 primitive and
`stamp` it), and the scene, the PNG and its metadata have the same size in tiles. Collision value `15` blocks all
four sides; `0` is open. Keep a recipe room's collisions in the recipe: `chromatic_collision_edit` writes only the
scene and leaves the recipe out of step, so use `set_collision_cells` (below) once a room has a recipe. Check
the result with `chromatic_collision_inspect`, `chromatic_graphics_analyze_scene` and a frame from the emulator.

## Files and units

| Data | Location | Meaning |
| --- | --- | --- |
| Atlas source PNG | `project/tilemaps/**/*.png` | Opaque 8 × 8 patterns in the four background shades |
| Atlas manifest | `project/tilemaps/**/*.atlas.json` | Named source tiles and named larger primitives |
| Room recipe | `project/tilemaps/**/*.room.json` | Every cell's tile, palette and collision bytes, protections, identities and hashes |
| Native background | `assets/backgrounds/**/*.png` and `.png.gbsres` | What GB Studio compiles |

The project must use GB Studio's distributed format. Every coordinate and size is in **8-pixel tiles**; a
rectangle covers `[x, x + width) × [y, y + height)`. A motif's `anchor` is a tile offset inside it and a stamp's
`x, y` places that anchor. Nothing is cropped, rotated, flipped, masked or resized.

The source shades are `071821`, `306850`, `86C06C` and `E0F8CF`; dark pixels stay opaque. Only a **null motif
cell** leaves a room cell untouched. Source-colour indices and native palette slots are different things.

## The tools

| Tool | Effect |
| --- | --- |
| `chromatic_tilemap_atlas_create` | Register a project PNG and a new atlas manifest; never overwrites an atlas |
| `chromatic_tilemap_create` | Create a room recipe and a new background, and bind it to one scene (the old background stays) |
| `chromatic_tilemap_inspect` | Read an atlas or a room region (at most 1,024 cells) with the current revision and tile hashes |
| `chromatic_tilemap_edit` | Place, fill or stamp primitives; replace selected cells' pixels/palettes; set selected collision bytes; adopt an existing recipe |
| `chromatic_tilemap_compile` | Check that the unchanged recipe regenerates the same native files (identical files are not rewritten) |

Every change needs `expectedRevision` (from `chromatic_project_inspect`, `chromatic_project_refresh` or the last
tilemap call) and accepts `dryRun: true`, which checks the real outputs and returns their hashes without writing or
reserving the revision. On a stale revision, inspect again.

## Make an atlas

Draw the source PNG first, then register it. Tiles name 8 × 8 patterns; primitives compose them:

```json
{
  "atlasPath": "project/tilemaps/materials-v1.atlas.json",
  "sourcePath": "project/tilemaps/materials-v1.png",
  "name": "Materials v1",
  "tiles": [
    { "id": "floor", "x": 0, "y": 0 },
    { "id": "wall", "x": 1, "y": 0 }
  ],
  "primitives": [
    { "id": "floor", "role": "decoration", "width": 1, "height": 1, "anchor": { "x": 0, "y": 0 },
      "cells": [{ "tileId": "floor" }] },
    { "id": "wall", "role": "surface", "width": 1, "height": 1, "anchor": { "x": 0, "y": 0 },
      "cells": [{ "tileId": "wall", "collision": { "mask": 15, "value": 15 } }] },
    { "id": "wall-block", "role": "surface", "width": 2, "height": 2, "anchor": { "x": 0, "y": 0 },
      "cells": [
        { "tileId": "wall", "collision": { "mask": 15, "value": 15 } }, { "tileId": "wall", "collision": { "mask": 15, "value": 15 } },
        { "tileId": "wall", "collision": { "mask": 15, "value": 15 }, "paletteSlot": 1 }, null
      ] }
  ],
  "expectedRevision": "<current project revision>"
}
```

Names are unique among tiles and among primitives, and every tile lies inside the PNG. A decoration primitive
cannot change collision; a surface primitive must declare at least one mask, applied as
`newByte = (oldByte & ~mask) | value` (`value` only within `mask`). Nothing is solid because of its colour or name,
and covering a surface with decoration keeps its collision.

## Create a room

```json
{
  "recipePath": "project/tilemaps/room-v1.room.json",
  "atlasPath": "project/tilemaps/materials-v1.atlas.json",
  "sceneId": "<existing scene ID>",
  "backgroundPath": "assets/backgrounds/room-v1.png",
  "name": "Room v1",
  "base": { "type": "fill", "tileId": "floor", "paletteSlot": 0 },
  "maxUniqueTiles": 128,
  "expectedRevision": "<current project revision>"
}
```

- `base: {"type": "fill", ...}` starts the new background from one tile. The scene's collision grid is kept.
- `base: {"type": "existing"}` captures the scene's current background instead: every 8 × 8 pattern must match a
  named atlas tile exactly, or it fails with `TILEMAP_CAPTURE_TILE_MISSING` and the coordinates (add the tile to a
  new atlas version and retry). Capture keeps the exact PNG bytes, palette encoding and collisions. Only capture
  takes `protectedRegions` (cells later edits may not touch); `reservedPaletteSlots` keeps palette slots out of
  explicit assignments.
- The scene, PNG and metadata must already agree in size. Scenes with a `tilesetId` and backgrounds with a
  `.mono.png` companion are refused.

The new background gets its own ID and symbol; only the chosen scene is rebound and everything else is kept.

## Edit a room

```json
{
  "recipePath": "project/tilemaps/room-v1.room.json",
  "operations": [
    { "type": "fill", "primitiveId": "wall", "x": 0, "y": 0, "width": 20, "height": 1 },
    { "type": "stamp", "primitiveId": "wall-block", "x": 8, "y": 6 },
    { "type": "place", "primitiveId": "floor", "x": 12, "y": 15 }
  ],
  "dryRun": true,
  "expectedRevision": "<current project revision>"
}
```

`place` and `fill` take a 1 × 1 primitive, `stamp` any size. Operations run in order, later cells replacing earlier
ones; holes keep what was there. The whole anchored rectangle must fit, and protected cells refuse any placement.
Without a `paletteSlot` a cell keeps its palette byte; explicit slots must be the scene's existing slots and never
the UI or reserved ones. The result lists changed tiles, cell counts, samples and the change in unique 8 × 8
patterns (flips are never deduplicated).

## Replace selected cells

`replace_cells` must be the only operation in its call. It can change protected cells but never collision bytes or
unselected cells. Read the region and the target atlas with `chromatic_tilemap_inspect` first: each tile's
`pixelsSha256` is the SHA-256 of its 256 RGBA bytes.

```json
{
  "recipePath": "project/tilemaps/room-v1.room.json",
  "expectedRevision": "<current project revision>",
  "dryRun": true,
  "operations": [{
    "type": "replace_cells",
    "atlasPath": "project/tilemaps/materials-v1.atlas.json",
    "atlasSha256": "<inspected atlas manifest hash>",
    "cells": [{
      "x": 10, "y": 8,
      "before": { "pixelsSha256": "<current tile hash>", "paletteByte": 130, "collisionByte": 240 },
      "after": { "tileId": "floor", "pixelsSha256": "<target atlas tile hash>", "paletteByte": 130 }
    }]
  }]
}
```

Keep the inspected palette byte for a pixel-only change; a palette-only change keeps the pixel hash. A new atlas
version may add tiles but must keep every existing tile's pixels and every primitive's definition.

## Set selected collision bytes

`set_collision_cells` is also alone in its call. It sets whole bytes (0–255) on selected cells, protected ones
included, and changes nothing else; the recipe and the scene are written together.

```json
{
  "recipePath": "project/tilemaps/room-v1.room.json",
  "expectedRevision": "<current project revision>",
  "dryRun": true,
  "operations": [{
    "type": "set_collision_cells",
    "cells": [{
      "x": 10, "y": 8,
      "before": { "pixelsSha256": "<current tile hash>", "paletteByte": 130, "collisionByte": 15 },
      "after": { "collisionByte": 0 }
    }]
  }]
}
```

To change art and collision, run `replace_cells`, inspect the cells again, then `set_collision_cells` with the new
revision and preimages.

## Adopt an existing recipe

A recipe made by another tool can be adopted without recapturing it (capture cannot keep duplicate-tile choices or
primitive names): one `adopt_binding` operation with `identity` (`roomId`, `backgroundId`, `atlasId`, `sceneId`) and
`before` holding the SHA-256 of the complete recipe, atlas manifest, atlas PNG, background PNG, its sidecar and the
scene (`recipeSha256`, `atlasSha256`, `sourceSha256`, `pngSha256`, `metadataSha256`, `sceneSha256`). It only adds
`adoptedBinding` to the recipe. `chromatic_tilemap_inspect` then also accepts that recipe's bound `atlasPath`.

## Limits and failures

Paths stay inside the selected project. Limits: 4,096 atlas tiles, 256 primitives of up to 32 × 32 cells (32,768
motif cells in all), 100 operations, and 4,096 cells per edit. Every change checks the whole project revision
before preparing and before writing, and refuses a background another scene uses, or native files changed outside
the recipe. Writes have **best-effort rollback**: a concurrent edit is kept and reported as
`TRANSACTION_RECOVERY_CONFLICT`; keep the failure receipt and inspect the changed paths before recovering. Build the
game and look at it in the emulator: a valid recipe does not show how the room plays.
