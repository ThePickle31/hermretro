# hermretro's changes to the engine

`engine/modretro-chromatic/` is ModRetro's release with the changes below, made by the maintainer (the engine's MIT
licence allows them). The tag `engine-upstream-<version>` holds the release untouched, without the same left-out
files (`THIRD_PARTY_NOTICES.md`):
`git diff engine-upstream-<version> HEAD -- engine/modretro-chromatic` shows every change. One line per change: the
files, what changed and why.

- `dist/server.js`, `dist/device-capture/linux-helper.js`: the path ffmpeg reads the Chromatic's video from during
  Linux hardware capture is `/dev/fd/6` instead of the equivalent per-process path under the proc filesystem (two
  places in each file). On Linux `/dev/fd` links to that same directory, so ffmpeg opens the same file; the
  original path made Hermes's install-time scanner ask for confirmation on every install.
- `assets/devices/images.br` (removed), `dist/server.js`: the device finishes' pictures live in the plugin's
  `player/skins/<id>/skin.webp|png`, not in the engine. The engine reads them from the folder in
  `CHROMATIC_DEVICE_SKINS` (the broker sets it, for the prepared copy outside the plugin), else the plugin's own
  `player/skins/` beside the bundled engine, loose rather than packed, for its web preview and the hardware
  live-feed window (`deviceArtworkFile` maps `chromatic-<id>.<ext>` to `<id>/skin.<ext>`), so each picture exists once.
- `dist/server.js` (`dist/web-build.js` module, `rom_build`): the browser export plays the ROM `rom_build` made. A
  successful build of the selected project writes `build/.codex-rom-build.json`, a receipt of its ROM (path and
  SHA-256) and the export's source fingerprint (taken before and after the build), signed with the key that
  attests web exports. A web build of the same sources writes that ROM's bytes over the one `make:web` compiled and
  does not reuse a cached export holding another; a project with batteryless saves on keeps `make:web`'s ROM, which
  GB Studio compiles without them on purpose. GB Studio puts a per-compile save signature in every ROM, so the two
  compiles always differed: the game played, flashed and shared is now one file with one hash.
- `dist/server.js` (`dist/emulator.js`, `dist/tool-domains/schemas.js`, `dist/contact-sheet.js` and the
  `emulator_step`/`emulator_observe`/`emulator_checkpoint` tools), `scripts/emulator_worker.py` (`play_step`):
  `emulator_step` also takes an ordered `inputs` list of `{buttons, frames, sample?}` run in one call (at most 64
  inputs, 3,600 frames and 8 samples; the last input is always sampled), and the worker runs every step as such a
  list. Step and observe results are compact by default (frame, buttons, sample hashes and one `recordingSpan`
  without `fromPrefixPin`; `detail:"full"` keeps the whole result), a single held set samples only its last frame
  unless `sampleCount` asks for more, and `scale` (1–4) enlarges the returned images. The checkpoint description
  names what a save needs (an active recording, a sampled neutral frame). Hermes drops a tool call identical to
  an earlier one in the same turn, so press-wait-press sequences sent as separate steps lost presses, and the
  full result of every step (about 4 KB, with up to four images) filled the agent's context.
- `dist/server.js` (`dist/project-session.js` module): a new starter or blank project's author is the `author`
  argument, else empty, never the template's ("Codex"); a Wrecklight remix keeps its source's author as before.
  `examples/starter/project/engine_field_values.gbsres`: coyote time (`FEAT_PLATFORM_COYOTE_TIME`) and drop-through
  (`FEAT_PLATFORM_DROP_THROUGH`) are on, GB Studio's own defaults, so a new platformer plays like one made in GB
  Studio.
- `dist/server.js` (`settings_update`): takes the player's `startMoveSpeed` (pixels per frame, within the one byte
  GB Studio compiles it to; top-down, shooter and point-and-click scenes use it); before, agents could not change the
  player's speed.
- `dist/server.js` (the server instructions, `web_preview`, `device_capture`): the text names Hermes, the hermretro
  emulator (`chromatic_present_game`, with its `studio.playerUrl` as the fallback) and Hermes Desktop's preview
  instead of "Codex's built-in browser", so hermretro no longer rewrites the descriptions it registers.
- `dist/server.js` (`dist/build.js` module, `rom_build`): a successful build returns the last 20 lines of compiler
  stdout (`stdoutOmittedLines` counts the rest) instead of 12–20 KB of it; every build writes its whole output to
  `logPath` (`build/logs/<ROM file name>.log` in the project, its folder checked when the log is written), and a build
  whose log cannot be written returns all of its output with `logError`. Error diagnostics come before warnings, so
  notices cannot crowd a compiler error out of the 16 kept. Node's `DEP0190` notice from GB Studio's CLI is left out
  of stderr and no longer counts as a warning (the `warnings` field is gone: it held only that notice), and GB
  Studio's deprecation notices (for example `EVENT_IF_VALUE` compiled with `ifVariableValue`) are
  `DEPRECATED_EVENT` diagnostics, once each, instead of lines only in stderr.
- `dist/server.js` (`dist/emulator.js` and the new `emulator_replay` tool), `scripts/emulator_worker.py` (`replay`,
  `open` split into `session_plan`, `load` and `boot`, per-frame hashes): `emulator_replay` boots a ROM, usually a
  rebuild, the way a recorded attempt booted (its boot frames and hardware mode) and plays the attempt's normalized
  inputs again in one call, comparing every frame with the attempt's. Recordings now keep a 16-hex-digit hash of
  each frame they play (in each step's `action` event and in `boot_complete`, copied into checkpoint branches);
  an older recording is compared at its retained images only, and the report says which (`coverage`). The replay
  stops at the first frame that differs and returns the recorded and replayed images (`onDivergence:"continue"`
  plays on and reports the first difference); `toActionIndex` replays part of the attempt. A cartridge with a
  real-time clock is reported as best effort (`deterministic:false`). The session stays open where the replay
  ended, recorded as a new attempt with the source's limits unless `recording:false`, with a `replay` event naming
  the source recording, branch, ROM and replayed action boundary; until a replay plays its source's whole route,
  that source stays the default of the next one. A replay needs no open session (it starts the worker and takes
  the recording lease, given back when it is refused), and a replay refused before it starts (a wrong branch or
  `toActionIndex`, a `maxFrames` shorter than the route, the recording quota) leaves the current session running.
  A new recording's `outputPath` may no longer lie inside another recording, the recording archives or an archive
  reference, whose bytes are inventoried. Checkpoints bind to the exact ROM, so every fix used to mean playing the
  whole route again by hand (several full playthroughs per game in the five-game audit).
- `dist/server.js` (`dist/assets.js`, `dist/sprites.js`, `dist/palettes.js`, `dist/scene-graphics.js`,
  `dist/tool-domains/` modules): art import and previews. `asset_import` imports up to 32 assets in one call
  (`assets`, all checked before any is written; a failure while writing removes every file the call created),
  takes `sprite.paletteIndex` (the sprite palette slot every tile uses), adds a `metasprite` profile (one row of
  frames up to 128 × 128 built from 8 × 16 tiles, blank tiles left out, a whole-frame collision box), gives the
  16-pixel profiles a 16 × 16 box for TOPDOWN sprites (`sprite.sceneType`, default the project's default scene
  type) when the top-down grid is 16 px, counts `numTiles` as GB Studio's compiler does (distinct 8 × 16 tiles
  after flip deduplication) and refuses a sprite larger than a scene can load, refuses generated profiles in a
  project whose sprite mode is 8 × 8, and returns each asset's graphics analysis (native_metadata too), whose
  sprite tile budget counts the same way. `palette_create`/`palette_update` take three colors for a sprite
  palette (entries 0, 1 and 3; GB Studio never draws entry 2 on sprites; an update keeps the existing entry 2)
  and `palette_assign` to a sprite slot returns the colors sprites show and warns about a distinct entry 2.
  `sprite_preview`, `sprite_contact_sheet` and `graphics_preview_scene` enlarge by default (a scene sheet only
  when the enlarged sheet fits the renderer), the sprite previews take a `paletteId`, and all three take
  `colorCorrection: "chromatic"`, the hermretro player's color correction (the Gambatte curve), as an
  approximation of the Chromatic's screen. Agents hand-wrote native metadata and hashes for palettes and large
  sprites, wrote zoom scripts, and skipped the analysis.
- `dist/server.js` (`dist/build.js`, `dist/source-debug.js`, the `emulator_debug` and `emulator_inspect` tools),
  `scripts/emulator_worker.py`: `emulator_debug` reports live state: the player and the actors asked for (by name, ID
  or symbol, or `"all"`) with tile and pixel position, direction, moving and move speed (a platformer player: its
  platform state and velocities), withheld while a scene change is still loading; the overlay, a `dialogue` state
  (none, drawing, waiting, menu or unknown) and the buttons the script that owns input accepts next, taking the
  running menu or text box, the VM lock and presses already read but not yet handled into account; how many scripts
  run and whether the VM is locked. A debug build reads live state only when the engine files it decodes are GB
  Studio 4.3.0-e1's own, byte for byte (`liveStateLayout`), and maps a scene's actors to their runtime slots in GB
  Studio's order (`_index`, then natural file order) only when the ROM's actor table matches their start tile,
  direction and sprite; prefab actors and indistinguishable ties are refused. A query asking for actors without
  live state still answers the scene and variables, with a limitation. Source reads on Game Boy Color take WRAM
  addresses from 0xD000 in bank 1. Variable selectors match an exact name or symbol, then the full name or symbol
  in any case, then the symbol without `var_`; an unknown name or ID lists the authored variables.
  `emulator_inspect` reads up to 2,048 bytes instead of 256. Agents decoded `_actors` from raw WRAM by hand, hit the
  256-byte limit, and guessed variable names that the tool only rejected.
- `dist/server.js` (`actors.js`, `triggers.js`, `project.js`, `scene-batch.js`, `native-script-events.js`,
  `game-scripts.js`, the project inventories and `rom_build`): actor and trigger symbols are unique across the whole
  project, as GB Studio's `ensureSymbolsUnique` keeps them (they were `actor_<name>` per scene folder, so two scenes'
  same-named actors compiled as one script), including the script names they compile to (`actor_door_interact`) and
  custom script symbols, and a rename gives a new one when the slug changes or the symbol is shared; the inventories
  report a shared scene, actor or trigger symbol or compiled name as a `DUPLICATE_SYMBOL` error naming each owner's
  id, which `project_inspect` and `project_inventory`'s diagnostic listing list and `rom_build` (after its path
  containment check) refuses to build past, each after a strong refresh, so a file edited outside the engine is
  checked before the file watcher reports it (macOS reports it late).
  Setting `symbol` (or another reserved key) in `scene_apply` or `actor_create` is an error instead of being dropped
  or taken, a `scene_apply` `id` that differs from its `actorId`/`triggerId` is an error, and `changedPaths` lists
  only files whose bytes change. Deleting and recreating one id in a `scene_apply` replaces the resource. Every
  script-writing path, `dialogue_update` included, gives each event without an id, nested ones included, a stable
  unique one (inserting the same event twice no longer collides). Actor direction and position arguments that GB
  Studio compiles as script values must be typed ScriptValues on write, like the scene-switch coordinates already
  were; an active actor direction event needs a `direction` that is a variable, an expression or up/down/left/right,
  commented-out events are not checked, and an unchanged older id-less event stays accepted once it gets an id.
