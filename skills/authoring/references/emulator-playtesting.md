# Playtest real ROMs

Follow [Stepped playtesting](../../rom-debugging/references/stepped-playtesting.md) for the canonical
edit → build → play → diagnose → fix → retest loop. The editing model chooses
each next input from real emulator frames; no separate player is required.

PyBoy is installed separately. Check metadata first and explicitly request the
`emulator-import` probe when executable health matters before promising gameplay
verification. Authorized packaged setup isolates Python/uv storage in its owned
root and reuses a healthy environment. It never changes global Python or a live
binding. Do not rerun setup merely to start another session; an import probe
still does not establish that the user's ROM has run.

The run starts in source mode when the last `chromatic_rom_build` built this
ROM (it captures debug artifacts by default), so a step's `debug` and
`chromatic_emulator_debug` read named variables and live state with no second
build.

```text
chromatic_emulator_run {"romPath":"<returned ROM outputPath>","initialFrames":120,"recording":{}}
chromatic_emulator_observe {}
chromatic_emulator_step {"inputs":[{"buttons":["right"],"frames":20,"sample":true},{"buttons":[],"frames":1}],"debug":{}}
chromatic_emulator_inspect {"view":"oam","visibleOnly":true,"limit":40}
chromatic_emulator_audio {}
chromatic_emulator_close {}
```

Record (`recording:{}`) only the runs that need it: the one run from power-on
to the ending, recorded from its first frame because the build report names it
([finishable](../../rom-debugging/SKILL.md#finishable)), and an attempt you
will save checkpoints in or replay onto a rebuild. `recording:{}` always boots
fresh, and a project's recordings folder holds about 16 at the default 64 MiB
before new ones are refused, so leave it off for quick looks.

## Steps and observations

A step takes one complete held-button set with its frames, or an ordered
`inputs` list of them run in one call, at most 3,600 frames in all. The set
persists; repeating it does not add release/press edges. Send a sequence as one
`inputs` list, never as repeated identical calls in one turn: Hermes drops the
repeats. The result is compact, with the last frame sampled; `sample:true` on an
input or `sampleCount` adds samples (eight at most), `scale` enlarges images
and `detail:"full"` returns every field. `chromatic_emulator_observe` only reads the current frame: it does not
advance, deliver input, or change the recording journal. `includeImages:false`
omits images; optional `imageLayout:"contact-sheet"` lays out the SAME current
image in memory. Individual PNGs remain the default. The same layout option on
`chromatic_emulator_step` composes only its already-requested samples, without extra steps.
Add `debug` (`chromatic_emulator_debug`'s selectors) to a step to get the live
player, dialogue or menu state, named actors and named variables on its last
frame in the same result, instead of a separate debug call after each step.

An unchanged `chromatic_emulator_run` reuses the current session without repeating
`initialFrames`. Request `restart:true` for an intentional fresh boot; changed
ROM bytes or hardware mode boot fresh automatically. Every boot preserves
adjacent cartridge saves. Close before switching projects; `chromatic_emulator_close`
also cancels outstanding emulator work and waits for cleanup.

## Memory and live state

`chromatic_emulator_inspect` provides bounded OAM or allowlisted VRAM, WRAM, OAM, and
HRAM views: at most 40 objects or 2,048 bytes. It does not infer named variables.
Source-mode `chromatic_emulator_debug`, and a step's `debug`, read variables by name and live player, actor,
dialogue, menu and script state; it requires an exact authenticated official build
and unchanged source. Neither tool permits memory writes, cartridge/boot ROM
dumps, arbitrary host files, or a shell.

## After a rebuild

Use optional [recordings and checkpoints](../../rom-debugging/references/recorded-playtesting.md) to preserve
failure evidence, export retained input history, review an interval, or extract
a supporting clip. After editing and rebuilding, replay a recorded attempt onto
the new ROM with `chromatic_emulator_replay {"romPath":"<new ROM outputPath>"}`
instead of playing the route again by hand: it stops at the first frame that
differs and leaves the session where the replay ended. For a game with a test
plan, `chromatic_playtest {}` replays every check bound to a recording in one
call ([the test plan, replayed](../../rom-debugging/references/recorded-playtesting.md#the-test-plan-replayed)). Checkpoints require
the same build and worker: a rebuild without an edit takes them when both
builds captured their debug symbols in this session, one after an edit does not.

## What the frames prove

Inspect actual samples for movement, interactions, collision boundaries, art,
and readability. They establish only the frames and inputs exercised, not
unsampled behavior, audio, saves, physical hardware, or CPU-cycle performance.
`chromatic_emulator_audio` says which sound channels the game drives on the
current frame (each enabled, its DAC on, sent to a speaker); it does not judge
how the music sounds.
