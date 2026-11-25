# Game Boy Hardware and Native Import Rules

Use this reference when selecting a compatibility mode, designing palette-safe
artwork, diagnosing tile overflow, or explaining sprite flicker. Separate physical
hardware behavior from editor import formats and engine-specific allocations.

## Hardware: actual cartridge and display constraints

- Screen: 160 × 144 pixels, or 20 × 18 background tiles.
- Background/window tiles: 8 × 8 pixels, two bits per pixel, four color indices.
- CGB background palettes: eight independent palettes of four colors each.
- CGB object palettes: eight additional palettes of four entries each. Object
  color index zero is transparent, so each hardware object has three opaque colors.
- Color encoding: little-endian RGB555 with five bits each for red, green, blue.
  Quantize an 8-bit channel to a five-bit value before comparing the final palette.
  Nearby desktop RGB colors may collapse to the same hardware color.
- Hardware objects: either 8 × 8 or 8 × 16 pixels. OAM has 40 entries, and the
  PPU selects no more than 10 objects on any single horizontal scanline.
- A 16 × 16 character is commonly composed of two 8 × 16 hardware objects. Five
  such characters aligned on one scanline can consume its entire object allowance.
  Wider bosses, projectiles, particles, and overlapping effects increase pressure.
- An object hidden only by moving its X coordinate off-screen may still consume a
  scanline slot because selection uses its Y coordinate.
- CGB background attributes select one palette and can flip an individual tile.
  Hardware capability does not mean every editor mode exposes or enables it.

Sources: [Pan Docs: tile data](https://gbdev.io/pandocs/Tile_Data.html),
[Pan Docs: palettes](https://gbdev.io/pandocs/Palettes.html),
[Pan Docs: OAM](https://github.com/gbdev/pandocs/blob/master/src/OAM.md), and
[Pan Docs: background attributes](https://gbdev.io/pandocs/Tile_Maps.html).

## Native source images

### Backgrounds using manual palettes

Use only these exact source colors, ordered darkest to lightest:

```text
#071821  #306850  #86c06c  #e0f8cf
```

The scene's selected color palette maps these four source shades to its displayed
RGB555 palette. Never use the sprite transparency marker `#65ff00` in a background.

Register the actual PNG and native `.gbsres` sidecar through `chromatic_asset_import`;
both source and destination must be confined to the selected distributed GB
Studio project. Palette indices are stored in the background's native
hexadecimal byte-run `tileColors` field. For an unbound background, use
`chromatic_palette_paint` rather than guessing an encoding or replacing unrelated tile
attributes. For a [bound native tilemap](../../authoring/references/tilemaps.md#replace-selected-cells),
use `chromatic_tilemap_inspect`, then `chromatic_tilemap_edit` with revisioned `replace_cells` and
unchanged pixel hashes for a palette-only edit. Resolve the
actual displayed colors with `chromatic_graphics_analyze_scene`; a monochrome-looking
manual-source PNG can display several distinct scene palettes at runtime.

### Backgrounds using automatic palettes

Supply actual color artwork. Each aligned 8 × 8 tile may use at most four colors,
and the scene may use at most eight distinct four-color palette families. Design
palettes after RGB555 quantization; preserve important value separation on real
hardware and color-correcting emulators.

For a mixed color/monochrome project, provide a same-name `.mono.png` override
when automatic grayscale construction loses readability:

```text
assets/backgrounds/forest.png
assets/backgrounds/forest.mono.png
```

### Sprites

Conventional native game sprite-source PNGs use:

```text
#071821  darkest visible shade
#86c06c  middle visible shade
#e0f8cf  lightest visible shade
#65ff00  transparent source marker
```

Do not include `#306850`: it is valid for manual backgrounds, not native game sprite
source images. Preserve the project's established alpha/chroma-key convention.
Regardless of source encoding, actual hardware object palette index zero remains
transparent and only three opaque indices remain available per hardware object.

#### Sprite palette mapping

In color mode each sprite tile draws through one of the scene's eight sprite
palette slots, and GB Studio compiles a sprite palette as entries `[0, 0, 1, 3]`:

| Source shade | Palette entry shown |
| --- | --- |
| `#e0f8cf` lightest | entry 0 |
| `#86c06c` middle | entry 1 |
| `#071821` darkest | entry 3 |
| `#65ff00` | transparent |

Entry 2 never shows on a sprite. Create sprite palettes with three colors
(`chromatic_palette_create {"name":"Hero","colors":["#f8f8f8","#e08040","#202020"]}`):
they are stored as entries 0, 1 and 3, with a blend in the unused entry 2 (three colors in
`chromatic_palette_update` keep the palette's entry 2, which backgrounds may use).
`chromatic_palette_assign` to a sprite slot returns the three colors sprites show
and warns when entry 2 holds a color you may have expected to see. Choose the
slot at import with `sprite.paletteIndex` (0–7, every tile; default 0), then
assign the palette to that slot in each scene where the sprite appears. An actor
has no palette of its own: GB Studio never reads an actor's `paletteId`, and the
actor tools refuse one.

Import profiles (`chromatic_asset_import` `sprite.profile`):

| Profile | Sheet | Layout |
| --- | --- | --- |
| `static` | 16 × 16 | One frame. |
| `directional` | 48 × 16 | Down, up, right; left is mirrored. |
| `directional_animated` | 96 × 16 | Two down, two up, two right frames. |
| `metasprite` | one row of `frameWidth` × `frameHeight` frames | Larger sprites, e.g. 32 × 32: one frame is static, several play in order. Frames are built from 8 × 16 tiles (width a multiple of 8, height of 16, up to 128 × 128); fully transparent tiles are left out. |
| `template` | as the template | Copies an existing compatible sprite's layout. |

A metasprite frame may use at most 40 hardware objects, and more than 10 drawn
tiles side by side in one row warns: the hardware draws at most 10 objects per
scanline. A larger directional character still needs a compatible existing `template`.

`numTiles` counts distinct 8 × 16 tiles after flip deduplication, as GB Studio's
compiler does (a mirrored half costs nothing), and the analysis's `tileBudget`
counts their 8 × 8 halves. A sprite needing more 8 × 16 tiles than a scene can
load (96, or 192 in Color Only) is refused.
The generated profiles build 8 × 16 objects, so they need the project's default
8 × 16 sprite mode; an 8 × 8 project refuses them (`SPRITE_MODE_UNSUPPORTED`).

The import's collision box: `static` and `directional` 16 × 16 (`boundsY -8`),
`directional_animated` 16 × 8 at the bottom, a metasprite its whole frame. When
the project's top-down grid is 16 px (`topdown_grid`), TOPDOWN sprites from the
16-pixel profiles get the full 16 × 16 cell: `sprite.sceneType` names the scene
type a sprite is for (default the project's default scene type), so pass e.g.
`PLATFORM` for one that is not. Change the box afterwards with `chromatic_sprite_edit`.

Several assets import in one call with `assets` (up to 32, checked before any is
written; native_metadata imports alone). Every import runs the graphics analysis
for its kind and the project's color mode and returns it as `analysis` (status,
palette families, violations). The asset is written even when that analysis is
`invalid`, and the destination cannot be imported again (`ASSET_ALREADY_EXISTS`),
so check a new PNG with `chromatic_graphics_analyze` first and import it once it
passes. Preserve the generated
states, eight animation slots, frame IDs, metasprite fields, SHA-1 checksum, and
native source-transparency convention.

`chromatic_sprite_preview` / `chromatic_sprite_contact_sheet` are authored-source
composites, not running-game frames. They are enlarged by default (a preview to
about 128 pixels, sheet frames to about 64); `paletteId` draws them in that
palette's sprite colors.

### Other imported art

- Backgrounds: dimensions must be multiples of eight; minimum 160 × 144; width
  and height at most 2040 pixels; total area at most 1,048,320 pixels.
- `assets/ui/frame.png` and `assets/ui/cursor.png`: use the four background
  source shades. The frame is interpreted through nine-slice scaling.
- `assets/emotes/*.png`: 16 × 16; follow sprite color rules.
- `assets/avatars/*.png`: 16 × 16; follow background color rules.
- `assets/fonts/*.png`: glyphs no larger than 8 × 8, arranged in rows of 16;
  matching `.json` files define metadata or custom character mapping. Magenta
  `#ff00ff` marks variable-width font padding where the project uses it.
- In color mode, the game editor uses background palette eight for UI and fonts.

The project may own more than eight global palette resources. Each running
scene has eight background palette slots and eight separate object palette
slots. Use `chromatic_palette_create`, `chromatic_palette_update`, and `chromatic_palette_assign` to
edit the actual resources/assignments; preserve the configured UI/font slot
unless an explicit supported override was requested. Distinguish configured
slots from palette indices actually consumed by decoded background tiles.

Sources: [GB Studio: backgrounds](https://www.gbstudio.dev/docs/assets/backgrounds/),
[sprites](https://www.gbstudio.dev/docs/assets/sprites/),
[UI elements](https://www.gbstudio.dev/docs/assets/ui-elements/), and
[project settings](https://www.gbstudio.dev/docs/settings/).

## Native engine budgets

### Monochrome or Color + Monochrome

- Background: up to 192 unique 8 × 8 tiles in ordinary scenes.
- Sprite availability: up to 96 **8×16 tile pairs** when the background uses no
  more than 128 tiles; down to 64 pairs when the background uses all 192 tiles.
- In 8×8 tile units: 128 dedicated background tiles, 128 dedicated sprite tiles,
  64 UI tiles, and a 64-tile region shared between background and sprites.

### Color Only

- Background: up to 384 unique 8 × 8 tiles in ordinary scenes.
- Sprite availability: up to 192 **8×16 tile pairs** when the background uses no
  more than 256 tiles; down to 128 pairs when the background uses all 384 tiles.
- In 8×8 tile units: 256 dedicated background tiles, 256 dedicated sprite
  tiles, 128 UI tiles, and a 128-tile shared region.
- Automatic horizontal/vertical background tile deduplication is available only
  when the applicable project and scene flip settings enable it.

`chromatic_graphics_analyze_scene` sums raw sprite `numTiles` metadata and retains the
nominal 8×16-pair range above. Its remaining-capacity and overage comparisons
are not normalized for 8×8 or mixed sprite modes. Compiled usage can also differ
after content removal or reuse; dynamic reservations are unverified. A metadata
overage is a warning, not confirmed overflow. Check compiled payloads and
reservations before reducing art or changing metadata. Below-range metadata
is not proof of fit.

These figures describe GB Studio's allocations, not universal hardware maxima.
Its Logo scene allows unusually detailed 160 × 144 images because normal player
and actor behavior is unavailable. Its 20 actors per scene and recommendation of
at most 10 actors visible are additional engine limits; they are distinct from
the hardware's 40 OAM objects and 10 objects per scanline.

Sources: [GB Studio: scene limits](https://www.gbstudio.dev/docs/project-editor/scenes/limits/),
[background requirements](https://www.gbstudio.dev/docs/assets/backgrounds/), and
[color and automatic-flip settings](https://www.gbstudio.dev/docs/settings/).

## Diagnosis order

1. Confirm the asset type, dimensions, compatibility mode, and source palette.
2. Count colors per aligned 8 × 8 tile after RGB555 quantization.
3. Count distinct consumed background/object palette families separately;
   configured unused slots do not prove tile usage.
4. Count exact fixed-shade unique tiles; normalized palette-independent patterns
   are only an auxiliary similarity heuristic. Inspect flip-deduplicated counts
   only when enabled for the actual scene and project mode.
5. Compare background complexity against the remaining sprite-tile allocation.
6. For disappearing sprites, distinguish actor count, OAM object count, and
   objects sharing one scanline; reproduce the specific failure in the emulator.
7. Inspect monochrome fallbacks, UI palette conflicts, and color correction.

## Display colors: the Chromatic is the reference

Judge colors as the Chromatic shows them. ModRetro builds its screen to match the
Game Boy Color's color balance, so palette colors look darker and less saturated
there than their raw RGB555 values. The hermretro player approximates this with
GB Studio's default color correction. Pass `colorCorrection: "chromatic"` to
`chromatic_sprite_preview`, `chromatic_sprite_contact_sheet` or
`chromatic_graphics_preview_scene` to see art with the player's correction, and
to `chromatic_emulator_step`, `chromatic_emulator_observe` or
`chromatic_emulator_replay` to see running frames with it (their sample hashes
stay those of the uncorrected frames). The correction applies to color-hardware
(CGB) sessions only: a DMG session, including a dual-mode cartridge run as DMG,
keeps the emulator's colors. Keep enough value separation between a palette's
colors after it.

`chromatic_graphics_preview_scene` is a static authored-color projection. Confirm actual
colorization, sprite overlays, UI, flicker, and movement through a freshly
built cartridge and genuine `chromatic_emulator_step` samples or `chromatic_emulator_observe`.
