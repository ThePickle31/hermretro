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
- `dist/server.js` (`dist/contact-sheet.js`, `dist/emulator.js`, the `script_inspect`, `emulator_step`,
  `emulator_observe`, `emulator_replay` and `emulator_recording` tools): `script_inspect` takes `sceneId` with
  optional `actorId`, `triggerId`, `scriptKey` and `branchPath` like its neighbours, or the same fields as `target`,
  and refuses both or neither before it selects a project. `emulator_step` accepts `frames:0` and `sampleCount:0`,
  and an `inputs` list that is empty or holds only 0-frame inputs, in its schema and refuses them, and a call with no
  input, with an error that names `emulator_observe` (to look without advancing) and `includeImages:false` (to
  advance without images). `emulator_step`, `emulator_observe` and `emulator_replay` take
  `colorCorrection: "chromatic"`, the hermretro player's color correction that the art previews take, for frames
  from color hardware (`imageDelivery.colorCorrection` says what was applied); it is applied to the decoded pixels
  before enlargement and, in a contact sheet, after the native PNG's SHA-256 is verified, so sample and tile hashes
  stay those of the native frames. The step and recording descriptions, and the worker's refusal after a recording
  is finalized (stopped, or failed at a recording limit), say that it ends the session's play and how to go on:
  `emulator_run` again, or `emulator_replay` with the `recordingPath` and `branchId` the recording returned. Hermes
  rejected the agents' `sampleCount:0` and flat `sceneId` against the schema before the engine saw them, the
  emulator frames showed uncorrected colors, and agents stopped recordings without knowing play ended with them.
- `dist/server.js` (`dist/assets.js`, the new `dist/audio.js`, `dist/tool-domains/` modules, `dist/emulator.js`),
  `scripts/emulator_worker.py` (`audio`, the sound registers emulated), `assets/music/` (new): music and sound.
  `asset_import` takes `music` (a `.uge` up to version 6 or a four-channel `.mod`, under `assets/music`) and `sound`
  (a `.wav` GB Studio's decoder reads, or a Game Boy `.vgm`/`.vgz`, under `assets/sounds`): it checks the file as GB
  Studio loads and compiles it (UGE notes, instruments and effects that reach the exporter, the version 5 repeated
  pattern IDs the loader repairs; WAV bit depth and samples after resampling and mixing; the VGM command stream and
  end marker; every song and sound within its one 16 KiB bank), accepts only paths GB Studio's globs find and type
  correctly, uses the disk's spelling, writes the sidecar with the path under the asset folder, an ID made from its
  path and a `song_`/`sound_` symbol unique among every compiled asset (`.sav` effects and files without a sidecar
  included), and returns a `playEvent`; `asset_inspect` reads songs and sounds. The new `music_compose` writes a
  hUGETracker version 6 `.uge` from note lists (sections of rows in scientific pitch on pulse1, pulse2 and wave,
  drums on noise, an order, preset instruments, `ticksPerRow`), or one of four bundled original tracks
  (`assets/music/*.json`, under hermretro's MIT license); it refuses a song over its bank, keeps every last-row cut
  (the loop break moves to the row after), writes the song and sidecar together and rolls the song back if the
  sidecar fails; `overwrite` replaces a song and keeps its ID. The new `emulator_audio` reports which sound channels
  the game drives on the current frame (NR50–NR52, each channel's envelope start or wave output level; a faded
  envelope leaves its channel active): PyBoy now emulates the sound registers (`sound_emulated`, ticked without
  sampling), recorded as `soundEmulated` in the runtime identity; a replay boots as its attempt ran, so an attempt
  recorded before it replays without them. Without a sidecar GB Studio gives a song a new random ID on every load,
  so no event could name it; agents had no way to import audio and four of the five audit games had beeps only (one
  played its song through a raw GBVM line).
- `dist/gb-studio-events.json` (new), `dist/server.js` (`event-catalog.js` module, `rom_build`, the tool domains):
  a catalog of GB Studio's script events, written by `tools/engine/event_catalog.py` from the event definitions of
  the GB Studio the toolchain compiles with and the hand-written `tools/engine/event_guidance.mjs`: each event's args
  (type, default, allowed values, whether it takes a list, the conditions under which it is used, `__disableElse`
  where the compiler reads it), child branches with their conditions, warnings, deprecation with its replacement and
  how to convert the args, events the compiler can no longer build (`EVENT_WEAPON_ATTACK`), what an event needs first,
  and an example that works (the editor's, or a hand-written one where that loops forever or needs another event). A
  new tool `event_describe` lists the categories, lists events by query, category or `includeDeprecated` 40 at a
  time with a cursor, and describes up to five, in full or compact. `rom_build` adds warnings for scripts that build
  but misbehave, in scenes, actors, triggers, the prefabs they inherit and the custom scripts they call (each in the
  calling scene): text in a LOGO scene (`TEXT_IN_LOGO_SCENE`), a `$0$` token in printed text (GB Studio prints the
  script's default variable; `TEXT_VARIABLE_TOKEN`), a right-hand menu opening over actors or the player's start or
  landing tile in a Game Boy Color scene no larger than the screen, unless every path to it hides the sprites
  (`ACTORS_OVER_MENU`), and each deprecated event, counted by where it is written, in place of GB Studio's own notice
  for it (`DEPRECATED_EVENT`); disabled else branches and commented-out events are skipped, at most three of each
  warning are listed, and the compiler's own diagnostics come first. Agents read GB Studio's source about 160 times in
  the five-game audit to find event args, and met each of these only when playing the game.
- `examples/starter/project/engine_field_values.gbsres`, `docs/native-sprite-import.md`, `dist/server.js` (`rom_build`,
  `emulator_run`, `emulator_replay`, `emulator_debug`, `asset_import`): a new starter or blank project's shoot-'em-up
  movement is GB Studio's default (`SHOOTER_MOVEMENT_TYPE` `MOVEMENT_TYPE_FREE`, was
  `MOVEMENT_TYPE_LOCK_PERPENDICULAR`; the starter is top-down and never used it). A project build captures debug
  artifacts unless `captureDebugArtifacts` is false (no measurable build time, about 32 KB in `build/<rom>.debug`), and
  its result names only their folder and `sourceDebug.available` (`detail:"full"` keeps the files, hashes and
  identity); when that default capture fails the build still succeeds and `sourceDebug` says why (an explicit
  `captureDebugArtifacts:true` still fails it). `emulator_run` and `emulator_replay` without `debugMode` start a ROM in
  source mode when a build in this session captured artifacts for it (found by the emulator's own path check, so a path
  through a symbolic link such as macOS's `/tmp` works), else in ROM mode, with `sourceDebug` saying why when that
  build's artifacts no longer apply or the ROM changed as it opened. A debug read leaves out the build identity, the
  standing limitations and references unless `detail:"full"` or `referenceLimit` asks (about 6 KB to 0.7 KB a call),
  and a `native_metadata` import leaves out its ID map and pattern notes unless `detail:"full"` (about 6 KB to 1.5 KB).
  In the benchmark rerun four of five games spent a second build only to turn source debugging on, a blank shoot-'em-up
  could not move its player up, and imports and debug reads repeated kilobytes on every call.
- `dist/server.js` (`actors.js`, `native-script-events.js` and every script writer, `project.js`, `event-catalog.js`,
  `build.js`, `scene-graphics.js`, `rom_build`): writes that GB Studio would silently ignore are refused, and builds
  that drop part of a game fail and keep the last good ROM. An actor `paletteId` (GB Studio never reads it: a sprite
  tile's `paletteIndex` picks the scene's sprite palette slot) is refused when a request gives or changes one,
  including actors given in a scene update's properties (`ACTOR_PALETTE_UNSUPPORTED`, naming `asset_import`
  `sprite.paletteIndex` and `palette_assign`); one already stored is kept through unrelated edits. The scene analysis
  no longer counts it as a used slot, and it and `rom_build` warn when a color scene assigns sprite palette slots 0-6
  that none of the sprite tiles it can draw use (`UNUSED_SPRITE_PALETTE_SLOTS`; slot 7 also colours emotes): its
  actors' sprites, a prefab's for an actor made from one, and the sprite fields of the events its scripts and called
  custom scripts run, commented-out events skipped; no warning when one cannot be known (a plugin event, a missing
  prefab or custom script, no player sprite set). A script event the request writes (new, changed, or named by the
  edit) whose command is neither in the event catalog nor one the compiler handles itself is refused with
  `INVALID_EVENT` and the three nearest current events, in a scene's own scripts and in the actors and triggers a
  scene update gives; a project with any `plugins/*/**/events/event*.js` keeps every command, since GB Studio
  registers the id the plugin's code returns. A GB Studio build whose output has GB Studio's `No compiler for command
  "…". Are you missing a plugin?` line (it leaves the event out and still writes the ROM) fails with
  `UNKNOWN_EVENT_COMMAND`. Every build now compiles into a `.rom-build-*` folder beside the ROM and replaces the ROM
  only when it succeeds; a failed build returns `rom: null`. In the benchmark rerun an actor `paletteId` drew every
  sprite in one palette, found only while making the cover, and an invented `EVENT_INPUT_AWAIT` built with
  `success: true`.
