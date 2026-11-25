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
- `dist/server.js` (`dist/project-session.js` module): a new project's author is the `author` argument, else empty,
  never the template's ("Codex" in the starter). `examples/starter/project/engine_field_values.gbsres`: coyote time
  (`FEAT_PLATFORM_COYOTE_TIME`) and drop-through (`FEAT_PLATFORM_DROP_THROUGH`) are on, GB Studio's own defaults,
  so a new platformer plays like one made in GB Studio.
- `dist/server.js` (`settings_update`): takes the player's `startMoveSpeed` (pixels per frame, within the one byte
  GB Studio compiles it to); before, agents could not change the player's speed.
- `dist/server.js` (the server instructions, `web_preview`, `device_capture`): the text names Hermes, the hermretro
  emulator (`chromatic_present_game`) and Hermes Desktop's preview instead of "Codex's built-in browser", so
  hermretro no longer rewrites the descriptions it registers.
- `dist/server.js` (`dist/build.js` module, `rom_build`): a successful build returns the last 20 lines of compiler
  stdout (`stdoutOmittedLines` counts the rest) instead of 12–20 KB of it; every build writes its whole output to
  `logPath` (`<rom name>.build.log` beside the ROM). Node's `DEP0190` notice from GB Studio's CLI is left out of
  stderr and no longer counts as a warning (the `warnings` field is gone: it held only that notice), and GB
  Studio's deprecation notices (for example `EVENT_IF_VALUE` compiled with `ifVariableValue`) are
  `DEPRECATED_EVENT` diagnostics, once each, instead of lines only in stderr.
