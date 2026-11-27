# hermretro's changes to the engine

`engine/modretro-chromatic/` is hermretro's engine. It started from ModRetro's Chromatic engine 1.0.34 (MIT: its
licence and notices stay) and is changed only by hermretro: a fix ModRetro makes in a later release is read in their
release and made again here by hand, as any other change. The tag `engine-upstream-1.0.34` holds that release as it
was published, without the files left out (`THIRD_PARTY_NOTICES.md`):
`git diff engine-upstream-1.0.34 HEAD -- engine/modretro-chromatic` shows every change. One line per change: the
files, what changed and why.

The changes are made in the engine's `dist/` modules (the server's own is `dist/entry.js`), and
`node tools/engine/bundle.mjs` builds `dist/server.js` from them. The entries before "the bundle is built from its
modules" below were made in the bundle itself; where one names `dist/server.js` and a module, the change is now in
that module.

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
- `scripts/emulator_worker.py` (`unstamped_rom_digest`, `load`, `checkpoint_save`, `checkpoint_restore`), `dist/server.js`
  (the `emulator_checkpoint` description): a checkpoint restores onto a rebuild of the unchanged project. GB Studio's
  4-byte `save_signature` hashes the loaded project, whose resources carry their load time (`_v: Date.now()`), so two
  builds of an unchanged project differ there and in the header's global checksum (`0x14E-0x14F`) and nowhere else.
  A session also hashes its ROM with those bytes zeroed, the signature found from the build's linker symbols
  (`_save_signature`, bank 0) and its place part of the hash, and checkpoints and recordings keep that hash beside the
  exact one; a restore takes either. The symbols count only as `rom_build` captured them with that ROM in this session:
  the server passes the ROM and `symbols.noi` SHA-256s its build recorded together (`buildSymbols`, `withBuildSymbols`,
  the `symbols` option of `run` and `replay`) and the worker checks both before using them (`build_symbols`), so a
  GBDK or no-debug build beside an earlier build's symbols matches only its own bytes. A branch restored from another
  build's checkpoint records that restore (`crossBuildRestore`) and a clean-boot replay past it is refused, since its
  battery RAM held the other build's signature. Without verified symbols, or with any other byte different, the
  restore is refused as before; the game's own battery save still refuses the other build's signature. A checkpoint
  saved before a no-change rebuild was refused, so the agent replayed the route by hand.
- `dist/server.js` (`event-catalog.js`, `native-script-events.js`, `game-scripts.js`, `actors.js`, `triggers.js`,
  `project.js`, `scene-batch.js`, `build.js`): an event GB Studio lists but cannot compile (the catalog's
  `unavailable`, set from source when its compile takes a helper GB Studio no longer passes; in 4.3.2 only
  `EVENT_WEAPON_ATTACK`, whose `weaponAttack` is gone) is refused by every script-writing tool the same way as an
  unknown command (new, changed, moved, or held by a patch's branches), with `INVALID_EVENT` naming its replacement
  and how to convert. A project with plugin events keeps it (a plugin may register it again), and so does a
  single-file project from before 2.0.0 r14, which GB Studio's legacy migration converts on load. A failed GB Studio
  build whose last failure record is `Compiling "…" failed with error "…"` reports one `SCRIPT_EVENT_COMPILE_FAILED`
  for the innermost event (GB Studio wraps the error again at every enclosing event), with the replacement for a
  deprecated one in place of its deprecation warning, instead of generic `COMPILER_ERROR`s. Before,
  `EVENT_WEAPON_ATTACK` was written without complaint and the build failed with GB Studio's raw `weaponAttack is not
  a function`.
- `dist/server.js` (new `dist/project-tree-watcher.js` module, `dist/project-world-index.js`): on Linux the project
  index watches the project with one watch per folder of its own (`ProjectTreeWatcher`) instead of Node's recursive
  `fs.watch`. Node 24.22, 26.9 and newer on Linux (also Node's main branch; 22, 25 and earlier 24 and 26 do not) throw
  from the recursive watch's own event handlers, outside any `error` event, when a watched folder becomes a file
  (`ENOTDIR`) or a new folder cannot be watched (`EACCES`, `ENOSPC`), which ended the engine and every chat's tools
  with it; the engine runs on Hermes's Node, 26.12 today. Every failure of a watch is now an `error` event that closes
  it; a folder is watched only when it is the same folder (not a link) before the watch and after its listing, and an
  event about a folder itself, or from one no longer at its path, watches that path again. macOS and Windows keep
  Node's native recursive watch. After a watch `error` the index closes the watcher, reads the project in full on each
  call, and starts a watch again at a full read, waiting from 1 s, doubling to 1 min, after each failure (it went back
  to ready with the dead watcher and missed later edits, and a watch that could not start was never tried again). A
  changed path that is now gone, a file or another folder drops what the index held at and below it (a folder moved
  away and replaced kept its files in the inventory), and the index reads the project again when the project folder
  itself was moved or replaced (on macOS the watch names that event by the folder's own name, which the index
  ignored). Replacing a build's debug folder with a file stopped the engine.
- `scripts/emulator_worker.py` (`replay`), `dist/server.js` (`emulator_replay`, `EmulatorService.replay`,
  `replayVerdict`, `replayExpectSchema`): a replay takes the attempt's `sessionId` and is refused, leaving the current
  session running, when its folder now holds another attempt; it names the session it ended (`replay.endedSession`,
  with that session's recording and whether it was still recording); `expect` (`frames`, `scene`, `variables`) gives a
  `verdict` (passed, failed, or needs-review when the scene or variables could not be read) read where the replay
  ended; and `finishRecording` stops the replay's recording with that verdict as its outcome. The verdict and the stop
  run in the replay's own queued emulator operation, so no step, restart or other replay comes between. hermretro's
  `chromatic_playtest` made the replay, the state read and the stop three calls, so another call could come between
  them, a reused folder replayed another attempt, and a live attempt was ended without saying so.
- `dist/server.js` (`tool-domains/schemas.js`, `tool-domains/playtest.js`, `server.js`): `emulator_step`, in
  both forms, takes an optional `debug` with `emulator_debug`'s selectors (`actors`, `variableNames`, `variableIds`,
  `includeScene`, shared as `liveStateSelectors`) and returns, read on the last frame in the same emulator operation,
  `debug`: `live`, the scene's id, name and type, and only the named variables as `{id, name, value}`. A read that
  cannot be made (ROM-only session, an unknown actor) is `debug: {error, code}` in a successful step, since the
  inputs already ran; its text is cut to 2,000 characters. The read's worker requests (`status`, `inspect` with
  `keepSession`) fail alone on a timeout instead of ending the session, and when the worker stopped during the read
  the step's result says so (`session: {status: "lost", recording}`). In the benchmark about 300 of Bolt Bounce's 345 calls alternated `emulator_step` and
  `emulator_debug` to see the state after each step.
- `dist/server.js` (`script_edit`, `script_inspect` and `scene_apply`'s `script.edit` operations, `operationFields`,
  `emulator_debug`'s `#liveActorSelection`, `emulator_review`): a script target takes the event as `target.eventId`,
  the same as `eventId` beside it (two different ones are refused), in all three tools; `script_transition`'s target
  names no event. A `scene_apply` operation that names its scene, actor, trigger, script, event or branch path in
  more than one place (beside `input`, in it, or in either `target`) must name the same one, or the batch is refused
  with nothing applied; the two targets are merged key by key, where `input.target` used to replace the outer one.
  An `emulator_debug` actor is found in the whole authored project (an exact name, ID or symbol in any scene first,
  then a name in any case) before the current scene's live slots: one in another scene comes back as data, with its
  names, `sceneId` and `unavailable: "not in the current scene (it is in <scene>)"`, several as `matches` with their
  IDs and scenes, also when the current scene's actors cannot be mapped (prefabs); a current-scene actor without a
  live slot is data too; a name no scene has is still refused. `emulator_review` states its 1–8 `maxImages` in the
  field and the tool description. In the benchmark `scene_apply` refused `target.eventId`, a debug read of a later
  level's actor failed twice, and a review asked for 9 images.
- `scripts/setup-compiler.mjs` (`CLI_SAVE_SIGNATURE_PATCH`, `patchedSaveSignatureSource`, `patchSaveSignature`,
  `cliWorkerCurrent`, the Windows `ensureOfficialCli`, `resolveInstallPrerequisites`, `--use-existing` and
  `verifyPinnedWorktree`), `scripts/setup-compiler.sh` (`cli_worker_current`), `scripts/setup-components.mjs` (`cli`,
  `replaceSource`, `saveSignaturePatch`), `scripts/setup.mjs` (`applySetup`), `scripts/dependency-doctor.mjs`
  (`detectCli`), `dist/server.js` (`compilerBoundKey`, `rememberNativeRom`, `buildWeb`, the reviewed compiler profile,
  now `…-native13-v3`), `dist/wrecklight/profiles/base.js`, `docs/wrecklight-remix.md`, `docs/agent-guide.md`: setup
  compiles GB Studio with one more checked source patch, so the same project builds to the same ROM bytes wherever it is
  (a copy in another folder, a game installed from its repository on another machine), web copy included, and its
  battery saves keep loading after a rebuild. GB Studio's `save_signature` hashed `JSON.stringify(projectData)`, which
  holds its asset loaders' `_v` (the load time) and `inode`, and a new random UUID for an asset without a .gbsres;
  `src/lib/compiler/compileData.ts` now hashes the project without those two loader fields of asset records (an event
  arg named `_v` still counts), its UUIDs numbered by first appearance, and the content of the code the project brings
  (every file in `assets/engine` and `plugins`: engine code, plugin event scripts and their `plugin.json`), which can
  change what a save holds. An edit to the project's data, engine code or plugins changes the signature; an art-only
  edit can keep it (a background's pixels). The patch applies only to the exact pinned source, in its own line endings,
  replacing the file at once, and is recorded in the CLI's setup receipt. A CLI compiled before it is reported
  `incompatible` by the doctor (with the recovery step for its kind of install) and compiled again by every installer;
  `--use-existing` reports it and changes nothing. Setup now prepares and verifies a replacement component in staging
  before it moves the previous one aside (only the emulator, prepared in place, is moved first), so an upgrade that
  fails offline leaves the old compiler working, and a receipt left by an unfinished install never lets another detected
  copy count as reused. A cached web export and the native ROM receipt are signed for the compiler that made them (the
  CLI and its build worker, by content), so after the compiler changes neither is reused. Every rebuild changed the ROM
  and invalidated the game's saves, and a copy built from the same source could never match its author's ROM.
- `dist/server.js` (`dist/build.js` module, `rom_build`): a game's GB Studio builds reuse one compiler folder,
  `gbs_<6 hex digits of the user and the .gbsproj>` in the trusted temporary folder, instead of a fresh `gbs-XXXXXX`
  each time, so GB Studio's object cache (`_gbscache`, keyed by content and by the folder's path) lasts between
  builds: a rebuild compiles only what changed (about 0.4 s instead of 6.5 s for the starter), with the same ROM.
  - The folder is the user's own (mode 700, checked); everything but the cache is removed before and after each build.
  - A build holds it through `.claim-<pid>-<uuid>` files, one for the engine and one for the compiler's process
    group, which can outlive the engine: the compiler starts through `/bin/sh` and waits on its standard input until
    its claim is written. A claim is alive while its process or group is. Another build meanwhile gets a fresh
    folder.
  - GB Studio's keys follow only `include "..."` lines, so a game that brings compiler input of its own (its own
    engine code in `assets/engine`, or any plugin folder in `plugins`: an engine overlay, or an event that writes a
    header an engine file reads) builds in a fresh folder, and the cache is dropped when the compiler changes (the CLI, its build
    worker, GB Studio's engine and GBDK, by content; a link among them means a fresh folder).
  - Those keys are enough for GB Studio's engine files (their other includes are GBDK's) but not for the game's
    generated ones (they take only the values of `data/game_globals.i`, not the names, and a raw `.include` is not
    followed): after each build only the cached objects of files GB Studio ships in `appData/engine/gbvm/src`
    (outside `src/data`) are kept, so the game's own compile on every build. `COLOR`, `SGB`, `BATTERYLESS` and
    `DEBUG`, which GB Studio sets only for a setting that asks for them, are left out of the compiler's environment
    so an inherited one cannot make two settings share a key.
  - What a stopped or failed compiler changed in the cache is removed, and the whole cache after a build whose
    engine or compiler stopped before it finished. Windows keeps a fresh folder per build.
- `dist/entry.js` (new), `dist/server.js` and every module our changes touched: the bundle is built from its
  modules. Each change made in the bundle so far is now in its module, written as the module's source
  (`dist/entry.js` is the server's own module, rebuilt from the bundle, as ModRetro's release ships none); the new
  `dist/audio.js`, `dist/event-catalog.js` and `dist/project-tree-watcher.js` are modules of their own; a helper one
  module's change used from another is exported and imported; `GameStudioProjectError` moves from `dist/project.js`
  (which re-exports it) to the new `dist/project-error.js`, so `dist/project-files.js`, which the backend's writer
  lock loads directly, loads without the project model behind it. `dist/server.js` is what `node tools/engine/bundle.mjs`
  builds from them (`python tools/check.py engine` checks it), holding the same modules as before.
- `tools/engine/update.py` and `tools/engine/report.py` (removed): the engine is no longer updated by merging a
  ModRetro release into it. A fix from a later release is ported by hand, like any change.
- `dist/**/*.js.map` (removed, with each module's `sourceMappingURL` line), `scripts/*.d.mts` (removed, and from
  `package.json`'s `files`), `docs/release-1.0.*.md` (removed, and the README's links to them). The server bundle is
  byte for byte the same; the one difference is in opt-in diagnostics: with `node --enable-source-maps`, a stack
  trace through a module loaded directly names `dist/<module>.js` instead of a `src/*.ts` file the release never
  shipped (and which no longer matched the modules we changed). The type declarations are for a compiler nobody
  runs, and ModRetro's release notes stay readable in the tag `engine-upstream-1.0.34`.
- `.codex-plugin/`, `.mcp.json`, `scripts/prepare.mjs`, `scripts/prepare-plugin-payload.mjs`, `scripts/bundle-mcp.mjs`,
  `scripts/register-personal-plugin.py`, `scripts/setup-windows.mjs`, `scripts/setup-windows.ps1`,
  `scripts/device-mcp.mjs` and `scripts/device-client-deps.mjs` (removed): ModRetro's Codex packaging, which hermretro
  never used: its plugin manifest and MCP config, the build and packing of a Codex plugin payload, its registration in
  Codex, the Windows installer that ran those, and a developer client that read `.mcp.json`, with the module only it
  loaded. The code that read them goes too: the launcher's check of
  a Codex payload receipt (`scripts/start-mcp.mjs`), setup's preparation of a payload and `prepared-mcp.json`
  (`scripts/setup.mjs`), the runtime copy's receipt branch and its requirement for the two files
  (`scripts/setup-runtime.mjs`), the doctor's reading of the receipt (`scripts/dependency-doctor.mjs`), and the
  refusal to write into a Codex payload (`scripts/setup-compiler.mjs`/`.sh`, `scripts/setup-emulator.mjs`/`.sh`).
  None of it ran for hermretro's bundled engine, which never has such a receipt or a `+codex.payload.` version.
  The doctor's check that `scripts/device-client-deps.mjs` is present goes with that module.
  `package.json` keeps the npm scripts whose files exist and drops its build-only devDependencies; the docs and
  hermretro's setup and deployment skills no longer describe the removed files. Windows code paths and
  `scripts/setup.ps1` stay.
