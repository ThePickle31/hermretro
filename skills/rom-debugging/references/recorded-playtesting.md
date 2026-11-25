# Recordings, checkpoints, and clips

The hermretro plugin can retain recordings,
checkpoints, and clips from real play. Use [stepped playtesting](stepped-playtesting.md)
for the edit → build → play → diagnose → fix → retest loop. This reference covers
optional retained evidence and same-build checkpoints; it does not introduce
another playing path.

## Retain an attempt

Enable recording on a fresh boot:

```text
chromatic_emulator_run {"romPath":"<returned ROM outputPath>","restart":true,"initialFrames":120,"recording":{}}
chromatic_emulator_recording {"action":"status"}
chromatic_emulator_recording {"action":"export","actionOffset":0,"limit":64}
```

The default output is a unique directory under the authorized workspace's
`artifacts/playtests/`. An explicit `recording.outputPath` must be an unused
authorized directory. Retain the returned absolute `recordingPath`.
All boots, including unrecorded boots, preserve adjacent cartridge save files.

While recording, the last frame of every input in an `inputs` list is kept as evidence, sampled or not: a
64-input list keeps up to 64 frames plus the periodic ones, even though only the sampled frames come back in
the result. Size recording limits for that.

Export reports bounded pages of normalized input history and retained evidence.
By default it returns up to 64 actions. Use `nextActionOffset` for the next
action page. Evidence always contains the latest `min(limit, 32)` samples;
`actionOffset` does not page that evidence. `actionCount` and `evidenceCount`
are full retained totals, and `truncation` identifies omitted entries.
Exporting does not play the game or judge its behavior; to play the history
again on a rebuilt ROM, [replay it](#replay-after-a-rebuild).

```text
chromatic_emulator_recording {"action":"stop","outcome":"failed","reason":"The player cannot pass through the opened door."}
chromatic_emulator_close {}
```

The example outcome is the caller's observation, not an automatic grade.
`stop` finalizes evidence and ends the session's play: steps, input and
checkpoints are refused until `chromatic_emulator_run` boots again
(`restart:true`, or `recording:{}` to record a new attempt). A recording that
fails at a recording limit is finalized the same way. To carry on from where
the stopped attempt ended, replay it with `chromatic_emulator_replay`, passing
the `recordingPath` and `branchId` that `stop` returned: without them a replay
prefers the source of an earlier replay that ended early. Then check that
`replay.replayedActions` equals `replay.source.actionCount`; a difference stops
the replay before the end ([replay after a rebuild](#replay-after-a-rebuild)).
Optional outcomes are `passed`, `failed`, `needs-review`, and `cancelled`,
with a reason of at most 1,000 characters. Failed and cancelled attempts retain
those statuses; other completed recordings use `stopped` with a separate
functional outcome. Closing cancels active work without deleting the attempt.

## Review an interval already played

`chromatic_emulator_review` reads committed normalized inputs and existing sampled PNGs.
It does not advance play, deliver input, capture a new frame, or append a journal
event. It also works after close without loading a ROM.

When `chromatic_emulator_step` returns `recordingSpan`, copy its `recordingPath`,
`sessionId`, `branchId`, `fromActionIndex`, `toActionIndex`, `fromFrame`,
`toFrame`, and `prefixPin` into the review request. One span covers the whole
call, every input of an `inputs` list included. With `detail:"full"` the span
also has `fromPrefixPin`; it is not an input field. Do not reconstruct
normalized indices from the number of requested steps or inputs.

Review selects `(fromActionIndex,toActionIndex]` on one exact session and
branch. Equal indices select an explicitly empty interval. Limits are 4,096
normalized actions, 3,600 native frames, and 2 MiB of response metadata.
`maxImages` defaults to four and accepts 1–8. With at least two requested
images, selection includes the first and last retained images and evenly
spaced retained records between them. `includeImages:false` changes only inline
image delivery, not evidence selection or verification.

Set `imageLayout:"contact-sheet"` to compose those SAME verified retained PNGs
into one inline sheet, with source hashes, frame/action labels, tile mapping and
existing gaps/provenance preserved. Individual images remain the default;
`includeImages:false` suppresses either layout. An empty interval with no retained
frames produces no fabricated sheet. The complete review plus sheet metadata
still has the existing 2 MiB limit. No new frame, journal event or file is written,
and post-close review does not reopen the ROM.

For an already-authorized retained interval, keep its exact returned recording,
session, branch and action bounds; do not step merely to produce an overview:

```text
chromatic_emulator_review {"recordingPath":"<existing returned recordingPath>","sessionId":"0123456789abcdef0123456789abcdef","branchId":"branch-0001","fromActionIndex":0,"toActionIndex":3,"maxImages":8,"imageLayout":"contact-sheet"}
```

The IDs and action indices above are examples. Replace them with the exact
returned identities and owner-selected bounds; do not invent a retained interval. Sheet integrity
and labels do not establish gameplay quality, unsampled states or heard audio.

The result separates exact retained `inputs`, available `physicalEvents`,
verified `frames`, and `coverage`. Missing endpoints, unsampled intervals,
or missing physical-delivery records remain unavailable. Imported checkpoint
prefixes can lack physical events; copied legacy frame sequence numbers are
not unique event identities. PNG dimensions and SHA-256 are verified, while
`rgbaSha256` remains the recorded pixel hash.

A prefix pin authenticates committed bytes, not authorization or a gameplay
outcome. Earlier pins remain usable after later events are appended, and
finalized recordings still require valid complete tails. Review reports
`semanticValidity:"not-adjudicated"`: inspect the actual evidence before
claiming an interaction or other outcome succeeded.

## Replay after a rebuild

`chromatic_emulator_replay` plays a recorded attempt's inputs onto a ROM, usually
the one `chromatic_rom_build` just made, in one call:

```text
chromatic_emulator_replay {"romPath":"<new ROM outputPath>"}
chromatic_emulator_replay {"romPath":"<new ROM outputPath>","recordingPath":"<an earlier recordingPath>","toActionIndex":42}
chromatic_emulator_replay {"romPath":"<new ROM outputPath>","onDivergence":"continue"}
```

It boots the ROM with the attempt's boot frames and hardware mode, then plays
its normalized inputs (button sets and frame counts) and compares every frame
with the same moment of the attempt: a recording keeps a short hash of each
frame it plays, besides the images it retains. The result's `replay` reports:

- `status`: `matched`, or `diverged` with `divergence`: the first differing
  `frame`, the `actionIndex` that played it (0 for the boot),
  `lastMatchedFrame`, the hashes of the images and, with `continue`, how many
  compared frames differed (`differingFrames`).
- `coverage`: `every-frame`; `retained-frames` for an attempt recorded before
  per-frame hashes, where only its retained images (by default every fourth
  frame and each step's end) were compared, so a difference between them can
  go unseen; `partial` for a branch whose checkpoint came from such an attempt.
- `source`: the replayed recording, branch, ROM hash and action count, and
  `sameRuntime` (false after a PyBoy or worker update; frames normally still match).
- `replayedActions` up to `toActionIndex`, and `comparedFrames`.
- `deterministic`: false, with `knownNondeterminism:["host-clock-rtc"]`, when
  the attempt's or the new cartridge has a real-time clock. PyBoy reads that
  clock from the computer's, so a game that reads it can differ on an
  unchanged ROM: the comparison is best effort.

Images, in order: `expected` (the attempt's retained image of that frame, when
it kept one) and `actual` (the replay's frame there) when they differ, then
`end`, the frame the session is at now. `scale` enlarges them,
`colorCorrection:"chromatic"` shows them in the Chromatic's colors (hashes stay
the native frames'), and `includeImages:false` omits them.

By default a difference stops the replay at that frame, even inside a step. A
change you made on purpose (new art, text, a moved actor) also differs: look at
the images, then replay the same attempt with `onDivergence:"continue"` to
reach the end of the route, naming it from the result's `replay.source`
(`{"romPath":…,"recordingPath":"<replay.source.recordingPath>","branchId":"<replay.source.branchId>","onDivergence":"continue"}`),
or with `toActionIndex` to stop before the changed part. A replay only presses
the recorded buttons; when the new ROM behaves differently (a door now opens
one frame later), later inputs can land differently, so check the `end` frame
before continuing.

A replay that starts ends the current session; a refused one (a wrong
`toActionIndex` or branch, a `recording.maxFrames` shorter than the route, an
`outputPath` inside another recording or the archives) leaves it running. A
replay needs no open session: after `chromatic_emulator_close` or a restart,
name the attempt with `recordingPath`. The new session stays open where the
replay ended, with the last recorded buttons still held, and is recorded as a
new attempt with the source's limits (pass a `recording` object to change them
or `false` to record nothing); that attempt notes which recording, branch, ROM
and action boundary it replayed. Until a replay has played its source's whole
route, that source stays the default of the next replay, so a replay stopped
by a difference is never what the next one plays. After a whole route, the
replay's own `recording.recordingPath` becomes the default. Pass `recordingPath`
to replay another attempt, and `branchId` for a branch other than its current
one. Step, save checkpoints and review there as usual: a checkpoint saved after
the replay belongs to the new ROM.

## The test plan, replayed

For a game with `docs/game/TEST-PLAN.md`, `chromatic_playtest` makes the plan
executable: each check is bound to the recorded attempt that passed it, and
one call replays every bound check on the game's ROM as it is now.

Bind a check as soon as it passes, from a recording made from a fresh boot
(`chromatic_emulator_run` with `restart:true` and `recording:{}`):

```text
chromatic_playtest {"action":"bind","check":"T3","recording":"<recordingPath>","toActionIndex":<recordingSpan.toActionIndex>}
chromatic_playtest {"action":"bind","check":"T4","recording":"<recordingPath>","toActionIndex":57,"expect":{"scene":"Cellar","variables":{"Oil":2}}}
```

- `recording` is a `recordingPath` or session id inside the project; it may
  still be recording. One recording can bind several checks, each at its own
  `toActionIndex` (the `recordingSpan.toActionIndex` of the step where that
  check passed; required while the recording is still being made, else all
  of its actions).
- F1 binds only the whole run from power-on to the ending, stopped with
  `chromatic_emulator_recording {"action":"stop","outcome":"passed"}` once the
  ending shows, with no checkpoint restores and no `toActionIndex`.
- `expect` says what the replay must end in. Without it, every compared frame
  must match the recording (`frames:"match"`). With `scene` (the scene's
  name) or `variables` (names or symbols and values), those decide instead and
  the frames may change, so a check survives art and layout edits; they are
  read where the inputs end, which needs the ROM `chromatic_rom_build` made in
  this chat from the current source.
- Binding a check again replaces its binding and its result;
  `{"action":"unbind","check":"T3"}` removes both. When a check's words change
  in the plan, its binding is `stale` and is not replayed: play the check again
  and bind the new recording. The answer lists the open checks still `stale`
  or `unbound`.

After every rebuild, run them all instead of choosing what to replay:

```text
chromatic_playtest {}
chromatic_playtest {"checks":["T3","T4"]}
```

Each check answers `passed`; `sampled` (its frames matched, but the recording
kept only some of them to compare: record it again from a fresh boot and bind
it); `failed` (the replay showed something else: its `divergence` frame, the
`observed` scene and variables, the `problems`); or `error` (it could not be
judged: a refused replay, a recording folder that now holds another attempt, a
ROM in ROM debug mode). `evidence` holds the saved `expected`, `actual` and
`end` images. A failure you caused on purpose (new art, a moved door) is not a
regression: play that check again with `recording:{}` and bind the new
recording. Each check is one replay that judges itself in the same call, so
nothing comes between; each replay ends the emulator session, and the last one
stays open where it ended. When the run ended an attempt that was still being
recorded, `endedSession` names it (it is kept, stopped). Nothing is kept when a
build finished during the run or a call was refused: run it again.

F1's replay is recorded (in `artifacts/playtest-runs/`, which keeps the newest
four within the folder's budget, never a bound one) and stopped in the same
call with its result as the outcome. When it passed or failed, `finishRun`
names it: give it to `chromatic_build_report` as `finishRun` with F1's result.
The report is held to the results on its ROM: a check that failed cannot be
reported `passed`, and one replayed cannot be reported `not run`. A check that
answered `error` is reported `passed` only with that check's `evidence`: the
recording of this ROM that shows it passing, which you played yourself.

Bound recordings stay in `artifacts/playtests/`: never archive or delete one,
and record check runs with a smaller budget
(`recording:{"maxBytes":16777216}`, 16 MiB) so the folder's 1 GiB of reserved budgets
holds them all (see the limits below).

## Checkpoints are for the same build

Saving needs two things, or it is refused:

- An active recording: the ROM was started with `recording:{}` and the
  recording has not been stopped. Stopping it with `chromatic_emulator_recording`
  ends what can be saved in that session.
- A sampled neutral frame: no buttons held, and the last step ended with `[]`
  for at least one frame, so the releases reached the emulated hardware. End
  the step before a save with a neutral input:

```text
chromatic_emulator_step {"inputs":[{"buttons":["right"],"frames":20},{"buttons":[],"frames":1}]}
chromatic_emulator_checkpoint {"action":"save","label":"Before the jump"}
chromatic_emulator_checkpoint {"action":"restore","checkpointId":"<returned-checkpoint-id>"}
chromatic_emulator_observe {}
```

A restore preserves the original route and creates a new recorded branch.
Checkpoint IDs and state files are opaque. Identity includes the ROM, active
CGB mode, PyBoy version, worker protocol, and worker implementation hash.
Changing the plugin worker can therefore invalidate an old checkpoint even
when the ROM is unchanged. A damaged, stale, or incompatible state is refused.

A checkpoint restores onto the ROM it was saved on: the worker compares the
exact ROM hash first, so a rebuild with identical bytes takes it with no
symbols at all, and hermretro's toolchain rebuilds an unchanged project to
identical bytes. A ROM that differs from it only in GB Studio's 4-byte save
signature and the header's global checksum also counts as the same build. The
signature hashes the project and the code it brings (engine, plugins), so an
editor-only change (a scene's place on the map) changes it alone, and a GB
Studio without repeatable builds (a desktop GB Studio, or a toolchain from
before them) changes it on every rebuild. The worker places the signature from
the linker symbols (`<rom>.debug/symbols.noi`) that `chromatic_rom_build`
captured with that exact ROM in this session, and ignores just those bytes. A
restore across such a rebuild therefore needs verified symbols from both builds: the build the checkpoint was
saved on and the one now running, each run as `chromatic_rom_build` returned
it. A ROM with none matches only its own bytes: a C (GBDK) build, a build with
`captureDebugArtifacts:false`, a build whose default capture was skipped (its
result says `sourceDebug.available:false`, for example when the source changed
during the build), a ROM from an earlier session, or symbols left beside it by
another build. To restore a checkpoint from an earlier recording (archived or
not) onto such a rebuild, boot the new ROM with `recording:{}` and pass the
checkpoint's `recordingPath`:

```text
chromatic_emulator_run {"romPath":"build/game.gbc","recording":{}}
chromatic_emulator_checkpoint {"action":"restore","checkpointId":"<id>","recordingPath":"<the save's recordingPath>"}
```

Any other changed byte (an edit, a setting, a new asset) is a different
build and the restore is refused: [replay](#replay-after-a-rebuild) the attempt
to retest it. The game's own battery save still checks the signature, so a
save written by one build is ignored by the other as on hardware; that is GB
Studio's behaviour, not a failed restore. For the same reason a branch
restored from another build's checkpoint replays from a clean boot only up to
that restore: past it the replay is refused (its battery RAM held the other
build's signature); replay with `toActionIndex` up to the restore, or restore
the checkpoint again. Checkpoints are not battery-save backups or evidence of
physical save-hardware behavior.

## Extract a supporting GIF

`chromatic_emulator_clip` uses existing archived frames without reopening or advancing
the ROM. Select the interval needed to explain the issue:

```text
chromatic_emulator_clip {"recordingPath":"<returned recordingPath>","outputPath":"artifacts/clips/door-before.gif","startFrame":120,"endFrame":156,"maxFrames":64}
```

A GIF uses at most 600 source images and reports source-frame/timing metadata.
Its output is no-clobber and must remain inside the recording directory or the
authorized workspace's top-level `artifacts/` subtree. Sampling gaps remain
gaps in the evidence; a clip does not establish unsampled motion or audio.

For a short montage, pass ordered cuts instead of top-level frame bounds:

```text
chromatic_emulator_clip {"recordingPath":"<returned recordingPath>","outputPath":"artifacts/clips/jump-montage.gif","cuts":[{"startFrame":120,"endFrame":156},{"startFrame":132,"endFrame":148}]}
```

Cuts preserve order and repeats, require exact retained endpoints, and reject
more than 16 intervals, 600 selected image occurrences, or 60 seconds of summed
native game time. They are not silently downsampled. The returned `cuts` map
source frames to output time and list sampling gaps; `timing` labels held samples
at native game time with decision pauses omitted. Missing motion is never
interpolated. Record with `sampleEveryFrames:1` prospectively when every native
frame is needed. Actual encoded GIF frame count and duration can differ from
source sample count because identical images merge and GIF time is quantized.
This exporter never replays input, captures new evidence, or annotates inferred
controls. It also works after the emulator closes.

## Limits, archives, and sharing

| Recording option | Default | Maximum |
| --- | ---: | ---: |
| `maxBytes` | 64 MiB | 512 MiB |
| `maxFrames` | 36,000 native ticks | 216,000 native ticks |
| `maxWallTimeMs` | 900,000 ms of emulator execution | 3,600,000 ms |
| `recentFrameCount` | 12 retained frames | 64 frames |
| `sampleEveryFrames` | Every 4 frames | Every 3,600 frames |

Execution time excludes idle time between calls. `executionWallTimeMs` reports
that work; game time follows executed native frames. Neither measures cartridge
CPU-cycle performance. The minimum byte budget is 64 KiB. Use
`sampleEveryFrames:1` when consecutive recorded frames matter.

Frame limits count work across branches, not only the current rewindable frame.
Byte accounting includes evidence and derived clips. Within one recording
parent, new attempts are refused at 64 directories or when reserved byte
budgets would exceed 1 GiB. This is not a machine-wide quota, and old attempts
are not pruned automatically.

Each attempt owns `recording.json`, an append-only `events.jsonl`, sampled
`frames/`, opaque `checkpoints/`, and a derived-output quota ledger. Preserve
the worker-owned ignore-all `.gitignore` and `.npmignore` markers, including
in custom output directories. Do not redirect recording or clip storage through
symlinks/junctions or rewrite its journals.

Schema-v1 archives remain readable through recording status/export, review,
and clip tools after close or a server restart. Reader compatibility does not
make old checkpoints compatible with a different worker. Preserve old recipe
files as user data; the plugin has no recipe runner. Retest a rebuild with
`chromatic_playtest` (the test plan's bound checks) or `chromatic_emulator_replay`
of a recorded attempt.

Generated evidence remains separate from authored game assets. Keep failed
attempts until they are understood, delete only with the owner's permission,
and inspect contents before sharing. Distribute only ROMs, images, and save
data you own or have permission to share.

## Reversible recording maintenance

### Diagnose access without opening a recording

```json
{"action":"access_diagnostic"}
```

This explicit `chromatic_emulator_recording` action accepts no other fields. It reads only
the authorized root's fixed access metadata (at most 4 KiB), not recording
contents. It does not create directories or markers, acquire or release access,
start an emulator or artifact worker, query processes, or queue behind a pending
worker. Unsafe, redirected, malformed, changing or unreadable metadata remains
`unresolved` without a retry. The observation is not an atomic filesystem snapshot.

The response separates the current observation from the **last acquisition
failure recorded by this service**. A new service cannot reconstruct an earlier
failure. Future failed acquisitions also return bounded `recordingAccessFailure`
details alongside the existing error: operation, time, category and available
filesystem code/errno. Raw error messages, stacks and the lease token are omitted.
An `already-exists` category is not proof that its owner is alive; other errors
such as permission or storage failure retain their own category.

An observed PID is only an unverified lease claim. The old lease format has no
process-start identity or host/client mapping. `matches-this-services-saved-lease`
means this service retains the release capability and the observed file identity
and bytes match; PID equality alone is never sufficient. Local service/transport
fields describe only the responding instance. No result establishes process
liveness, global quiescence or permission to recover; `recoveryAuthorized` is
always false. Even absence does not authorize a new run.

Use the original owning client's ordinary `chromatic_emulator_close` only when that client
is still addressable and closure is selected. A fresh caller cannot close another
instance's lease. If the original client is inaccessible, preserve the evidence
and resolve its host/client lifecycle first. There is no public takeover,
force-unlock or orphan-finalization action. Do not remove a lease, kill a PID,
retry a refused call, or restart a ROM to try to recover access. A turn interruption
or inactive session is not a receipt for the original client's transport closure.

### Archive, retrieve and restore

`chromatic_emulator_recording` accepts `archive`, `retrieve`, and `restore`, each with an
explicit `recordingPath` and no other operation fields. Maintenance is filesystem
only: it does not boot a ROM or launch an emulator. It requires POSIX ownership
checks and same-filesystem directory moves within the authorized project.

First close recording readers/writers and their emulator/artifact workers, and
settle every outstanding request and transport. This does not require terminating
the MCP server or stopping its unrelated web previews. Recording access must be
quiescent, including older versions without the new advisory access lease. Supported clients hold that lease while a worker is open; competing
clients and maintenance refuse it. Stale leases and unresolved cleanup are never
automatically cleared. This is coordination between supported clients using the
same authorized project root, not a census of unrelated programs or protection
against unmanaged filesystem writers. Close legacy clients explicitly before use.

```json
{"action":"archive","recordingPath":"artifacts/playtests/original-attempt"}
```

Archive requires a finalized, integrity-valid `stopped`, `cancelled`, or `failed`
recording. Live and interrupted records are ineligible. All files and directories,
including frames, checkpoints, ledgers and required ignore markers, are verified
within the existing 512 MiB recording maximum and a 20,000-member maintenance
limit. Symlinks, hard links, special files, writable-by-others paths and changes
during inspection are refused.

The destination is an exclusively created
`artifacts/recording-archives/<unique-id>/recording` in the same project. There is
no arbitrary output-root option or overwrite mode. The directory move preserves
all recording bytes, modes and provenance. A protected mapping directory remains
at the ORIGINAL path. Keep it and the archive container together; historical
closure/index records containing that path are not rewritten.

```json
{"action":"retrieve","recordingPath":"artifacts/playtests/original-attempt"}
```

Retrieve verifies both mapping copies, complete inventory digest, modes, manifest
and finalized journal, and returns the original/archive paths and session identity.
Supported status/export/review calls also resolve the original path through this
verified mapping. Direct archive paths undergo the same checks. External exported
clips remain at their original paths; they are neither copied nor deleted. Restore
before creating new derived clips, because archived bytes are immutable.

The original parent's ordinary admission check no longer finds this recording's
`recording.json` in an immediate child. Its original `maxBytes` reservation is
therefore released without changing any quota or historical limit. This does NOT
reclaim disk space: `bytesReclaimed` is zero. Recording bytes and new mapping
metadata remain on disk and still require storage accounting.

```json
{"action":"restore","recordingPath":"artifacts/playtests/original-attempt"}
```

Restore verifies again, checks the unchanged parent quota, parks the exact mapping
directory in the archive container, and returns the recording to its original
path. It refuses unrelated content or a quota filled by newer recordings. The
original reservation becomes chargeable again. Mapping metadata stays for audit.

An incomplete move/publication is a failure: bytes and recovery mapping remain
retained and the lease stays unresolved. Stop for owner reconciliation; do not
repeat the call, remove a lease, or overwrite a reported path. There is no automatic
pruning, deletion, cross-filesystem copy, quota increase, or old-runtime relabeling.
Source/unit coverage does not expose the new actions in an installed host. Use
the normal installation owner and fresh deployed validation before maintaining
any real retained recording.
