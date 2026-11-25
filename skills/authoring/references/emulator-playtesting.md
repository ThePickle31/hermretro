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

```text
chromatic_emulator_run {"romPath":"<returned ROM outputPath>","initialFrames":120,"recording":{}}
chromatic_emulator_observe {}
chromatic_emulator_step {"inputs":[{"buttons":["right"],"frames":20,"sample":true},{"buttons":[],"frames":1}]}
chromatic_emulator_inspect {"view":"oam","visibleOnly":true,"limit":40}
chromatic_emulator_audio {}
chromatic_emulator_close {}
```

Start every run with `recording:{}`. Checkpoints need an active recording, a
recorded attempt can be replayed onto a rebuild, and the one run from power-on
to the ending must be recorded from its first frame: the build report names it
([finishable](../../rom-debugging/SKILL.md#finishable)).

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

An unchanged `chromatic_emulator_run` reuses the current session without repeating
`initialFrames`. Request `restart:true` for an intentional fresh boot; changed
ROM bytes or hardware mode boot fresh automatically. Every boot preserves
adjacent cartridge saves. Close before switching projects; `chromatic_emulator_close`
also cancels outstanding emulator work and waits for cleanup.

## Memory and live state

`chromatic_emulator_inspect` provides bounded OAM or allowlisted VRAM, WRAM, OAM, and
HRAM views: at most 40 objects or 2,048 bytes. It does not infer named variables.
Source-mode `chromatic_emulator_debug` reads variables by name and live player, actor,
dialogue, menu and script state; it requires an exact authenticated official build
and unchanged source. Neither tool permits memory writes, cartridge/boot ROM
dumps, arbitrary host files, or a shell.

## After a rebuild

Use optional [recordings and checkpoints](../../rom-debugging/references/recorded-playtesting.md) to preserve
failure evidence, export retained input history, review an interval, or extract
a supporting clip. After editing and rebuilding, replay a recorded attempt onto
the new ROM with `chromatic_emulator_replay {"romPath":"<new ROM outputPath>"}`
instead of playing the route again by hand: it stops at the first frame that
differs and leaves the session where the replay ended. Checkpoints require
matching ROM and worker identity; they do not transfer to a rebuild.

## What the frames prove

Inspect actual samples for movement, interactions, collision boundaries, art,
and readability. They establish only the frames and inputs exercised, not
unsampled behavior, audio, saves, physical hardware, or CPU-cycle performance.
`chromatic_emulator_audio` says which sound channels the game drives on the
current frame (each enabled, its DAC on, sent to a speaker); it does not judge
how the music sounds.
