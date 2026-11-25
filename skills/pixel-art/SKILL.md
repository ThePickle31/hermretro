---
name: pixel-art
description: "Create, edit, or check native game sprites, backgrounds, tiles, and palettes. Use for Image Generation or native pixel work, tile budgets, and in-game readability."
version: 1.0.34
license: MIT
metadata:
  hermes:
    tags: [chromatic, modretro, game-boy, pixel-art, palettes]
    related_skills: [hermretro:authoring, hermretro:rom-debugging]
---

# ModRetro Chromatic pixel art

Choose the workflow from the request and the existing artwork. Read the matching
reference; load other details when the task needs them.

If the plugin tools are unavailable, follow the [setup skill](../setup/SKILL.md).
Native asset work needs the runtime; a compiler or emulator is needed only for
requested build or gameplay checks.

## Browser previews

Show the game to the user in the **hermretro emulator** beside the chat: once everything agreed with the user is in it and you have tested it, call `chromatic_present_game`, optionally with a short `note` on what to try. Do not open `chromatic_web_preview` URLs, including screenshot Open links, yourself, and do not reload the player with `drive_preview`. Only if the user says they cannot see the emulator, open `studio.playerUrl` from that result with `desktop_preview` (`action: "open"`); without desktop tools, give the user that URL. Give `chromatic_device_capture` URLs to the user without claiming they opened (not yet verified inside Hermes). Never launch an external browser yourself.

## Choose a workflow

| Need | Route |
| --- | --- |
| **A new static sprite** | When [image generation is available](#check-for-image-generation), start with the [two-step Image Generation workflow](references/prompting-recoverable-grids.md): generate a deliberately coarse design, then reconstruct it as whole filled grid cells. Otherwise draw it natively. Use the requested or existing project size; otherwise start at 32 × 32. |
| **A background, tileset, or reusable room** | Use [native artwork and tile tools](references/native-pixel-tools.md#new-native-artwork), with [hardware and import guidance](references/hardware-and-imports.md) for palette and tile budgets. Use [native tilemaps](../authoring/references/tilemaps.md) for rooms built from authored tiles. |
| **Exact pixel edits, manual art, palettes, or tile composition** | Use [native pixel authoring and plugin tools](references/native-pixel-tools.md). Author PNG/cel pixels directly; use the plugin for supported palette, tilemap, and sprite-metadata edits. Prefer this route when existing pixels must stay exact. |
| **Animation from an approved still** | Use [native animation guidance](references/prompting-grid-animation.md): optional generated motion reference, deliberately authored native frames, then timed review. Preserve the approved still and working motions. |
| **Editor files, existing raster art, or import/conversion** | Use [authoring and interchange](references/authoring-and-interchange.md). Preserve editable sources and check the available conversion/import tools. |

Honor a requested method. When the user is choosing, explain the relevant
tradeoff: Image Generation explores designs; native authoring provides exact
pixel control. A generated grid still requires cell and visual review.

## Check for image generation

Image Generation means Hermes's `image_generate` tool. It exists only when an image backend is set up (a `FAL_KEY`
or a configured image provider), so check before choosing that route: it is in your tool list, or
`tool_search` with `image generate` finds it. When it is missing, say so once if the user asked for generated art,
and draw the art yourself:

1. Write a script file that draws the PNG at native size in the exact source colours of
   [hardware and imports](references/hardware-and-imports.md#native-source-images), into a source folder inside
   the selected project (for example `art/hero.png`, not under `assets/`), and run it.
2. Check that PNG with `chromatic_graphics_analyze` (its `kind` and the project's `colorMode`). Fix the script and
   check again until it reports no violations (colours, tile budget, size).
3. Import it once with `chromatic_asset_import` (`sourcePath` the checked PNG, `assetPath` its place under
   `assets/`). An import writes the asset even when its analysis reports violations, and a second import to the
   same `assetPath` is refused with `ASSET_ALREADY_EXISTS`, so import only a PNG that has passed.
4. Look at it with `chromatic_sprite_preview` or `chromatic_graphics_preview_scene`, then in the game.

## Work in the right context

Source-art exploration can stay in the workspace. Before changing a game,
select the intended `.gbsproj` and inspect the actual asset, style, and
compatibility mode. Follow the [project operating guide](../authoring/references/project-selection.md)
for selection and revision safeguards; keep original and editable artwork.

- For source colors, dimensions, import profiles, and budgets, read
  [hardware and imports](references/hardware-and-imports.md).
- For silhouette, genre, and scene readability, read
  [art direction](references/genre-art-direction.md).
- For recipe-backed rooms, protected cells, and exact collision edits, read
  [native tilemaps](../authoring/references/tilemaps.md).

Inspect the result at native size. Review animation in motion and keep user
feedback authoritative; passing pixel checks does not establish visual quality.
When integrating into a game, use [stepped playtesting](../rom-debugging/references/stepped-playtesting.md)
for actual scene behavior. Distinguish source previews from verified gameplay.

## In hermretro

- Call `chromatic_*` tools directly, never from `execute_code`. Each game is worked on only in its own
  conversation (`GAME_CHAT_ONLY` otherwise: the user opens that game on the hermretro Build page);
  `PROJECT_WRITER_BUSY` means the game is still busy with an earlier call.
- To show art in the running game, build with `chromatic_rom_build`, playtest it, make sure the game card
  is complete (`chromatic_game_info`), then call `chromatic_present_game` with a `note` on what to look at.
- `chromatic_asset_import` imports several PNGs at once (`assets`), sets the sprite palette slot
  (`sprite.paletteIndex`), imports larger sprites with the `metasprite` profile, and returns each
  asset's graphics analysis. Sprites show palette entries 0, 1 and 3 only: give sprite palettes
  three colors ([palette mapping](references/hardware-and-imports.md#sprite-palette-mapping)).
- Previews are enlarged by default; `colorCorrection: "chromatic"` on previews and on color-hardware
  emulator step, observe and replay frames shows colors as the Chromatic, the reference display, does ([display colors](references/hardware-and-imports.md#display-colors-the-chromatic-is-the-reference)).
- To show the user existing art, deliver the real file on its own line (`MEDIA:<project>/assets/sprites/<name>.png`).
  The hermretro Build page draws it in the game's colours, animates a sprite, and opens it in its viewer;
  a preview or contact sheet you draw instead is just a flat image there.
- Cover art (required before `chromatic_present_game`): draw it yourself as native pixel art, never with
  Image Generation: exactly 160x144, opaque, at most 32 colours from the game's own palettes, its main
  character and title readable. Pass the PNG to `chromatic_game_info` as `cover`.
- Links into `../<skill>/` are sibling hermretro skills: open them with
  `skill_view("hermretro:<skill>", file_path="references/<file>")`.
