# Build, play, fix, and retest

The model editing the game can play it through the
hermretro plugin. Build the native
project, choose a short controller input, inspect real frames, and decide what
to do next. The emulator does not advance while the model is thinking.

## When browser play is unavailable

If the hermretro emulator is unavailable, locked or unreachable, retain its
URL and state, report that browser limitation, and continue **gameplay** checks
with the public headless PyBoy tools. Browser access is not a prerequisite.
Use `chromatic_emulator_run` on the intended exact ROM, `chromatic_emulator_step` for bounded inputs,
`chromatic_emulator_observe` for the current frame, and `chromatic_emulator_review` for retained
recording evidence. Use the verified cartridge from the intended build/export;
if a build is needed, build the selected project. Do not substitute a sample or
transfer browser save states into PyBoy.

If PyBoy is missing, follow the [setup skill](../../setup/SKILL.md)
with the `emulator` component under existing task authorization. A real access
denial, unavailable dependency or uncertain action remains scoped to the
affected work: preserve its result and do not replay it or use another route to
bypass it. Continue only independent authorized checks.

Headless frames establish native-emulator gameplay evidence. Browser UI,
annotations, browser recordings and physical-device/capture acceptance remain
separate; emulator tools do not control hardware. Preserve active user play and
unresolved saves/recordings. Do not switch browsers or reload a blocked view to
continue gameplay. When the hermretro emulator is available, present the game
with `chromatic_present_game` as described in [browser preview](../../authoring/references/browser-preview.md).

## Play the selected project

Select the actual project and check `chromatic_toolchain_doctor` when compiler or optional
PyBoy availability is uncertain. To select an existing project in an
unconfigured session, use its absolute path. A new project created with
`chromatic_project_create` still needs selection unless `select: true` was explicit.
Follow [project selection](../../authoring/references/project-selection.md) for first-create authorization and [platform and setup](../../authoring/references/platform-and-setup.md) for setup.

Describe the behavior you want to check, then build and play. These inputs are
illustrative; choose a route that exercises your own game.

```text
chromatic_project_select {"projectPath":"/absolute/path/to/MyGame/project.gbsproj"}
chromatic_rom_build {}
chromatic_rom_inspect {"romPath":"<returned ROM outputPath>"}
chromatic_emulator_run {"romPath":"<returned ROM outputPath>","restart":true,"initialFrames":120,"recording":{}}
chromatic_emulator_observe {}
chromatic_emulator_step {"inputs":[{"buttons":["right"],"frames":12,"sample":true},{"buttons":["right","a"],"frames":8},{"buttons":[],"frames":1}]}
```

Use the absolute paths returned by tools. Build output paths are relative to the
selected project; ROM and recording paths are relative to the authorized
workspace, which may be its parent.

`chromatic_emulator_run` initializes a fresh boot or reuses the same unchanged ROM,
preserving its current frame and held buttons. `initialFrames` applies only to
a fresh boot. Use `restart:true` for an intentional reboot; changed ROM bytes
or hardware mode start fresh automatically. Every boot is isolated from
adjacent cartridge battery-save and RTC files, with or without recording.
Recording is opt-in: omit `recording` when a retained attempt is unnecessary.

For monochrome compatibility checks, pass `cgb:false`, including for cartridges
that also support Game Boy Color. Omit `cgb` to follow the cartridge's default,
or pass `cgb:true` to request color hardware.

## Make each input explicit

`chromatic_emulator_step` takes either one held set (`buttons` and `frames`) or an
ordered `inputs` list, never both:

| Field | Meaning |
| --- | --- |
| `inputs` | Ordered list of 1–64 `{buttons, frames, sample?}` run in this one call, at most 3,600 frames in all. Each input holds its complete set for its frames; `sample:true` also samples that input's last frame. The last input is always sampled. To look without advancing, use `chromatic_emulator_observe`, not an empty list or 0 frames. |
| `buttons` | One held set instead of `inputs`: any of `a`, `b`, `up`, `down`, `left`, `right`, `start`, `select`. Use `[]` for no buttons. |
| `frames` | With `buttons`: positive frame count, 1–3,600. To look without advancing, use `chromatic_emulator_observe`. |
| `sampleCount` | With `buttons`: 1–8, default 1. Real samples evenly across positive frame offsets, including the endpoint. For no images use `includeImages:false`. |
| `includeImages` | Optional, default `true`. `false` omits inline images without changing input, frame advancement, or sampling. |
| `scale` | Optional, 1–4. Enlarges the returned images with square pixels; sample hashes stay those of the native frames. |
| `colorCorrection` | Optional, `none` (default) or `chromatic`. `chromatic` draws color-hardware (CGB) frames with the hermretro player's color correction, as the Chromatic shows them; sample hashes stay those of the native frames. A DMG session, including a dual-mode cartridge run as DMG, keeps the emulator's colors and reports `none`. |
| `imageLayout` | Optional, `individual` (default) or `contact-sheet`. The sheet labels the same requested samples in memory; it adds no frames, captures, or file writes. |
| `detail` | Optional, `compact` (default) or `full`. |

A call returns at most 8 samples. The held set persists after the call. Sending
the same set again does not release and re-press those buttons. To release a
button, leave it out of the next input's set. A two-frame A press followed by
one neutral frame is one call:

```text
chromatic_emulator_step {"inputs":[{"buttons":["a"],"frames":2,"sample":true},{"buttons":[],"frames":1}]}
```

Send every sequence of presses and waits as one `inputs` list, never as repeated
identical calls in one turn: Hermes silently drops a tool call identical to an
earlier one in the same turn, so "press A, wait, press A, wait" sent as four
calls loses presses. A menu or dialogue walk is one call:

```text
chromatic_emulator_step {"inputs":[{"buttons":["a"],"frames":2},{"buttons":[],"frames":30},{"buttons":["a"],"frames":2},{"buttons":[],"frames":30,"sample":true},{"buttons":["down"],"frames":2},{"buttons":[],"frames":10}]}
```

The neutral input advances frames; it is not a pause command. To stop and
discuss the result, simply stop sending steps. Use `buttons:["right"]` after a
right-and-A input when right should remain held and only A should be released.

The compact result holds `frame`, `startFrame`, `advancedFrames`,
`activeButtons`, `sampledButtons`, `samples` (frame, SHA-256 and `inputIndex`),
`recordingSpan` when recording, and `imageDelivery`; one image per sample
follows. `detail:"full"` adds the ROM path and hash, runtime, clock, recording
state, `execution` and the retained path of each sample. Ask for it only when
you need one of those.

Read the returned images and exact frame metadata before choosing the next
input. Use shorter steps near a landing, transition, or uncertain interaction.
For suspected flicker, request consecutive frames, for example `frames:8`
with `sampleCount:8`. Samples do not prove what happened in the gaps.

`chromatic_emulator_observe {}` returns the current genuine 160 × 144 PNG without
advancing a frame, delivering input, or changing the recording journal.
`chromatic_emulator_observe {"includeImages":false}` returns metadata without the inline
image, `{"scale":3}` returns it three times larger, and
`{"colorCorrection":"chromatic"}` returns it in the Chromatic's colors. Optional
`imageLayout:"contact-sheet"` labels the same current image in memory; the
individual PNG remains the default. Its result is compact unless `detail:"full"`. Observation accepts no actions
or output path and writes no files.

Read `execution` separately from `imageDelivery`. An image-delivery error can
follow completed or partially completed input. Do not repeat a step just to
recover its images; use zero-tick observation or review its retained recording
span. A transport failure with unknown execution is not evidence of zero
advanced frames. Inspect surviving state before deciding whether to continue
or deliberately start a new attempt.
If cancellation cleanup also fails, `cleanup` reports that separately without
discarding the execution result. Resolve cleanup before starting more work in
that session.

## Diagnose, edit, and retest

Use `chromatic_emulator_inspect` for bounded OAM or allowlisted hardware-memory views.
For named variables or the current scene, call `chromatic_emulator_debug` on
the ROM the last build returned: builds capture debug artifacts and
`chromatic_emulator_run` starts their ROM in source mode by default. Source diagnostics require the matching successful
build and unchanged authored source; addresses are not guessed.

Preserve the original attempt when it helps explain a failure. Play recorded
(`recording:{}`) and note what the frames showed. Apply the smallest relevant
native source edit, build a new cartridge and replay the attempt onto it, rather
than repeating the route by hand:

```text
chromatic_rom_build {}
chromatic_emulator_replay {"romPath":"<new ROM outputPath>"}
chromatic_emulator_step {"inputs":[{"buttons":["right","a"],"frames":8,"sample":true},{"buttons":[],"frames":1}]}
```

The replay boots the new ROM as the attempt booted and plays its recorded inputs
in one call, comparing every frame with the attempt's, then leaves the session at
the end of the route for the next step. A frame that differs stops it with the
recorded and new images: decide whether the change was intended. Inspect the
functional result yourself: a changed animation hash is not automatically a
regression, and a completed tool call is not a gameplay pass. A rebuild cannot
reuse an opaque checkpoint from different ROM bytes or a different worker; the
replay is how play resumes after one. See
[replay after a rebuild](recorded-playtesting.md#replay-after-a-rebuild).

## Stop and retain only what you need

Reuse the active preview URL or emulator/capture session for the same task. When temporary testing is complete, close only the session this task owns with `chromatic_web_preview_close`, `chromatic_emulator_close`, or `chromatic_device_capture {"action":"close"}`. Preserve user play (including paused games), ongoing recordings, and unresolved saves or commands; inspect status and retain recovery evidence before closing. Never scan processes, kill by name, claim an unfamiliar port, or clean up another task's session. An unknown action is not safe to replay.

`chromatic_emulator_status {}` reports the current session. `chromatic_emulator_close {}` stops
or cancels emulator work and waits for cleanup without deleting recordings.
Close before selecting another project. There is no paced/continuous play mode.
Recording `maxWallTimeMs` bounds cumulative emulator execution time, excluding
idle time between calls; frame and byte limits still apply.

See [recordings and checkpoints](recorded-playtesting.md) for retained-input
export, interval review, optional GIF clips, limits, and archive compatibility.
Use the runtime validation guide to verify the packaged
MCP path and report actual platform coverage.

## Migrating older callers

`chromatic_emulator_step` takes exact held-button sets, alone or as an ordered `inputs`
list, and returns sampled frames;
`chromatic_emulator_observe` reads the current frame without advancing play. Migrate older
callers to the direct loop above.

The removed public tools are `emulator_input`, `emulator_timeline`,
`emulator_capture`, `emulator_contact_sheet`, `emulator_recent`,
`emulator_control`, `playtest_save`, and `playtest_replay`. There are no legacy
aliases or separate packaged replay runner. Native authoring/build tools,
official browser previews, persistent PyBoy, bounded diagnostics, recording,
checkpoints, and clips remain available; implementation regression coverage
remains in the development suite.

The emulator surface has 11 tools: `run`, `step`, `observe`, `status`, `close`,
`inspect`, `debug`, `checkpoint`, `recording`, `review`, and `clip`, each prefixed
`emulator_`.
