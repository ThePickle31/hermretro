# Stepped emulation and gameplay checks

## Runtime availability

PyBoy is an optional, separately installed LGPL Python runtime. The plugin
discovers toolchain-local `.local/pyboy-venv/bin/python` on macOS/Linux,
`.local/pyboy-venv/Scripts/python.exe` on experimental Windows x64, or the
interpreter explicitly configured with `GB_STUDIO_PYTHON`.

Headless play of an existing ROM needs the `runtime,emulator` components;
building a ROM also needs `build` for the official GB Studio CLI and GBDK. Linux
needs no macOS application bundle or graphical desktop. `chromatic_toolchain_doctor` reports compatible
metadata by default; it does not launch Python or a game. An explicitly selected
`emulator-import` probe checks isolated PyBoy/Pillow imports and reports its
result separately. Neither a successful generic compiler check nor an import
probe proves that the user's ROM has run.

If the emulator is missing or unhealthy, follow the [setup skill](../../setup/SKILL.md)
and [Packaged setup](../../setup/references/setup.md): use the bundled entrypoint
directly and review a plan for an external owned root. Use existing task
authorization for necessary setup; ask only for missing scope or required
platform approval before `apply --yes`. If setup remains unavailable, report
that gameplay and real-frame observation did not run. The `emulator` group prepares isolated managed Python,
PyBoy, and Pillow and reuses healthy tools. Do not run npm in the immutable
payload, modify global Python, repair an active shared runtime, or rerun setup
for every session. A prepared future payload needs a separate authorized
activation handoff. Use only authorized homebrew or licensed ROMs, never
proprietary boot ROMs.

## Official browser play

```text
chromatic_web_preview {}
chromatic_web_build {"outputPath":"build/browser-preview"}
chromatic_web_preview {"outputPath":"build/browser-preview"}
chromatic_web_preview_close {}
```

Show the game to the user in the **hermretro emulator** beside the chat: once everything agreed with the user is in it and you have tested it, call `chromatic_present_game`, optionally with a short `note` on what to try. Do not open `chromatic_web_preview` URLs, including screenshot Open links, yourself, and do not reload the player with `drive_preview`. Only if the user says they cannot see the emulator, open `studio.playerUrl` from that result with `desktop_preview` (`action: "open"`); without desktop tools, give the user that URL. Give `chromatic_device_capture` URLs to the user without claiming they opened (not yet verified inside Hermes). Never launch an external browser yourself.

For an unavailable, locked or unreachable browser, continue the separate
[headless gameplay workflow](stepped-playtesting.md#when-browser-play-is-unavailable).

After a confirmed close, the same plugin instance tries its last port again and uses another free port if it is occupied. The reopened view always gets a new private URL; old links are invalid. This does not discover, adopt, or stop other listeners.

Reuse the active preview URL or emulator/capture session for the same task. When temporary testing is complete, close only the session this task owns with `chromatic_web_preview_close`, `chromatic_emulator_close`, or `chromatic_device_capture {"action":"close"}`. Preserve user play (including paused games), ongoing recordings, and unresolved saves or commands; inspect status and retain recovery evidence before closing. Never scan processes, kill by name, claim an unfamiliar port, or clean up another task's session. An unknown action is not safe to replay.

The official `make:web` export contains GB Studio's Binjgb/WebAssembly player
and actual cartridge, including its keyboard, gamepad, touch, and audio
behavior. Do not replace its HTML, build a second browser player, or add an
ad hoc server.

The URL binds to loopback and contains a private capability. An authenticated
unchanged export is reused across server sessions; an active session also
reuses its listener and URL. Indexed source/plugin changes refresh the export
without changing that URL. Use `force:true` only for an intentional
authoritative rebuild. Closing stops the server without deleting the export.

Browser observations do not establish PyBoy behavior, a dedicated native ROM
build, or physical-hardware compatibility.

## Direct steps and observations

Follow [stepped playtesting](stepped-playtesting.md) for the
canonical tool contract and native edit/build/retest loop. Pass the absolute
ROM path returned by the build: build outputs are project-relative, while ROM
and recording paths resolve from the authorized workspace.

```text
chromatic_emulator_run {"romPath":"<returned ROM outputPath>","cgb":true,"initialFrames":120}
chromatic_emulator_observe {}
chromatic_emulator_step {"inputs":[{"buttons":["right","a"],"frames":12,"sample":true},{"buttons":["right"],"frames":8,"sample":true},{"buttons":[],"frames":1}]}
```

The first input holds right and A. The second releases only A; right stays held
without another press edge. The last input releases all buttons. Frame counts
are explicit, positive, and bounded to 3,600 per call. A step returns up to eight
genuine samples: the last frame, and the last frame of each input marked
`sample:true`.

Observe has zero frame, input, and recording-journal mutation. `includeImages`
controls only inline image delivery on step or observe. Read the actual images
before describing visual content; hashes alone do not establish behavior.
For flicker, sample consecutive frames rather than widely spaced states.

An unchanged `chromatic_emulator_run` reuses its current frame and buttons without
repeating `initialFrames`. Use `restart:true` for an intentional reboot;
changed cartridge bytes or hardware mode boot fresh. Both recorded and
unrecorded boots ignore adjacent battery-save/RTC files. Close before changing
projects, and use `chromatic_emulator_close {}` to stop or cancel work.

There is no autonomous emulator clock. Thinking between calls advances zero frames.
Recording `maxWallTimeMs` counts emulator execution, reported as
`executionWallTimeMs`, not idle time. Game time follows actual native frames.
Host throughput is not a cartridge CPU-cycle or physical-hardware measurement.

Optional [recordings, checkpoints, and clips](recorded-playtesting.md)
preserve input history and failures. Checkpoints require a neutral delivered
frame and the same build and runtime, including the worker implementation hash
(a rebuild without an edit is the same build when both builds captured their
symbols in this session).
Archive-read compatibility does not authorize loading an old state into a new
build.

## Bounded hardware and source diagnostics

```text
chromatic_emulator_inspect {"view":"oam","visibleOnly":true,"limit":40,"includeScanlineSummary":true}
chromatic_emulator_inspect {"view":"memory","region":"wram","offset":0,"length":32}
chromatic_emulator_inspect {"view":"vram","region":"vram","offset":0,"length":32,"bank":0}
```

OAM inspection reads at most 40 hardware objects; its optional scanline summary
compares with the physical 10-objects-per-scanline limit. Memory reads are
limited to 2,048 bytes from named VRAM, WRAM, OAM, or HRAM regions, with bank
selection validated against actual hardware mode. Cartridge/boot ROM, arbitrary
I/O, host files or memory, and target-memory writes are unavailable.

`chromatic_emulator_audio {}` reads the sound registers (NR50–NR52 and each
channel's envelope or output level) on the current frame without advancing.
`active` is true when the sound hardware is on and a channel is enabled, its
DAC on and sent to a speaker. It shows which channels the game drives, not
what comes out: a faded envelope leaves its channel active. A short effect
ends within frames, so check right after it. A replay of an attempt recorded
before sound emulation runs as that attempt did, without it, and cannot be
checked for audio; open the ROM with `chromatic_emulator_run` instead.

ROM-only mode does not infer high-level game state or named variable addresses.
A successful official build of the selected project captures debug artifacts,
and `chromatic_emulator_run` or `chromatic_emulator_replay` starts its exact ROM
in source mode in the same MCP session (`"debugMode"` in its result says which; a `sourceDebug` there says
why source mode is off, such as source edited since the build):

```text
chromatic_rom_build {}
chromatic_emulator_run {"romPath":"<returned ROM outputPath>","restart":true,"initialFrames":120}
chromatic_emulator_debug {"variableNames":["has_key"],"actors":["Guard"],"includeScene":true}
```

A debug read is compact: frame, scene, live state, variables and what you ask
for (`collisions`, or references with `referenceLimit`). `detail:"full"` adds
the build identity, the standing limitations and 16 references.

A variable selector matches an exact authored name or symbol first, then the
full name or symbol in any case (`oil` finds a variable named `Oil`), then the
symbol without `var_` (`lantern_oil` finds `var_lantern_oil`). A selector that
matches several variables at the first step that matches any lists their IDs;
select by ID then. An unknown name or ID lists the authored variables. Supported
source queries expose signed 16-bit variables, current scene, live state, up to
256 authored collision tiles, and bounded resource/event references. Up to 32
variable selectors and 64 references are supported.

`live` is read from the running game at the paused frame:

- `sceneLoading`: a scene change is still loading. The player and actors are
  left out until it finishes; step a few frames and read again.
- `player`, and each actor named in `actors` (authored name, ID or symbol in the
  current scene, or `"all"`): tile `x`/`y` (the units `chromatic_actor_create`
  uses), `pixelX`/`pixelY`, `direction`, `moving`, `moveSpeed`, `active` (on
  screen and updating) and `hidden`. `moving` means a walking animation plays
  (scripted moves, top-down and adventure walking) or the top-down player is
  between grid cells; `moveSpeed` is the actor's scripted and top-down speed in
  pixels per frame. A platformer player moves by its own velocities instead,
  which `moveSpeed` does not set: it reports `platform` (`state`: ground, run,
  jump, fall, ladder, wall, dash, float, knockback or blank; `velocityX` and
  `velocityY` in pixels per frame), and `moving` is true only while those
  velocities move it (standing still on a ladder is not moving; nothing moves it
  while a script holds the VM locked). Actors map to the game's own actor slots
  only when the build's actor table matches the authored actors in GB Studio's
  order; prefab actors, and actors that share an `_index`, start tile,
  direction and sprite, cannot be mapped, and `limitations` says so.
- `ui`: `overlayOpen` (the window layer is on screen; a HUD counts), `dialogue`
  and the `buttons` the script that owns input accepts next. `dialogue` is
  `waiting` (a text box waits for a button), `drawing` (a text box or menu is
  opening or its text is still typing), `menu` (with `menuOptions`; up, down,
  left and right move the cursor), `none` (no overlay and no text), or `unknown`
  (the overlay is on screen with nothing waiting: a HUD, or a script between
  steps). While a menu or text box runs it owns input and other scripts' waits
  do not count; while a script holds the VM locked only its own wait counts.
  A press the engine has already read but not yet handled (A on a menu, a
  button for an input wait) means it is not waiting for another one. Direction
  buttons on a menu are handled before A, so Down with A moves the cursor and
  keeps the menu open. A script polling buttons in a loop is not detected.
- `scripts`: how many scripts run and whether one holds the VM `locked` (the
  player cannot move while it does).

Step until `waitingForInput` is true before pressing, rather than guessing
frame counts. Live state is read only from a build whose engine files are GB
Studio's own, unchanged; an ejected or plugin-changed engine leaves `live` out
and `limitations` says why, while the scene and variables still answer. Exact ROM bytes, same-build
`symbols.noi` / `globals.i`, supported engine layout, and unchanged source
and plugins must agree. Missing or optimized-out values stay unavailable.
Compiler artifacts alone do not guarantee a decodable layout.

Authored collision/event links explain source context, not the virtual
machine's currently executing event. After an edit, rebuild with fresh
artifacts before making source-aware claims. Preserve compiler stderr and
failure diagnostics; an aborted build cannot authenticate a new debug context.

## Report the check, not more

Keep the same functional expectation and relevant starting condition before
and after a fix. Repeat the exact button sets and frame counts through the
stepped API, inspect the result, and check nearby behavior when relevant.
Report ROM identity, inputs, observed frames, source diagnosis, and remaining
gaps.

A sample proves only its actual frame; intervening motion, audio, save/load,
and physical hardware remain unverified unless exercised separately. Static
`chromatic_dialogue_preview`, `chromatic_graphics_preview_scene`, `chromatic_sprite_preview`, and
`chromatic_sprite_contact_sheet` outputs are authoring aids, not running-ROM evidence.
Animation changes can alter hashes without a functional regression.

## Sources

- [PyBoy upstream README and API](https://github.com/Baekalfen/PyBoy)
- [GB Studio native build and web export documentation](https://www.gbstudio.dev/docs/build/)
- [Pan Docs Game Boy hardware reference](https://gbdev.io/pandocs/)
