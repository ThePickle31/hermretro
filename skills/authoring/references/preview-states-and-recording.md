# Preview states, captures and recording

These work on the browser player that [`chromatic_web_preview`](browser-preview.md) opens.

## Screenshots and video

Use the camera icon beside the handheld for a **Screenshot** of the current
game canvas. The record icon starts **Record video** with game audio; the Stop
control shows elapsed time while recording and finishing. Keep the preview
visible while recording. Muted or paused game audio stays silent. These controls
do not send game inputs or change emulation timing, and need no microphone or
display-capture permission.

The existing local preview server saves captures in the selected project's
`captures/<build-identity>/` folder, outside the authored source and web export.
The Saved toast offers Open, Download, and Copy path without changing the player
layout. Reopen the latest capture saved in this page session from
**⋯ More actions → Last capture**. Files remain after the page closes; their
browser links work while this preview is open. Nothing is sent to an external
service. If a save
fails or its result is uncertain, the original browser copy stays available for
download and is never retried automatically. Download it before leaving or
choosing **Discard unsaved**.

Video timing JSON keeps monotonic event times, media chunk timecodes, and bounded
document-visibility observations separate from emulated frames. Visibility
observations can help compare a timing gap with tab activity; they do not prove
its cause. Browser codec support varies; interrupted recordings are
labeled partial and may not play completely. Each recording retains at most
128 MiB of media; reaching that limit stops capture and preserves available
bytes as partial evidence. Screenshots are limited to 8 MiB and 4,194,304 pixels,
with neither dimension above 4096. Metadata is limited to 2 MiB per capture.

## Saved progress

Automatic saving captures changed play about every five seconds without pausing
the game. The newest eight states for each build persist in the selected
project's `save-states/<identity>/` directory, outside the web export.
Reopening the preview restores the latest state paused, ready to annotate.
Choose an earlier capture time from **⋯ More actions → Saved states** to reopen
that moment. **Restart game** starts again and skips recovery once; it does not delete
saved history. If recovery fails, automatic saving pauses to preserve that history.

States require the exact ROM, WebAssembly runtime, and source revision that
created them. A new build uses a separate history. Older build histories remain
on disk; states are not migrated between builds.

Hermes uses the existing `chromatic_web_preview` tool for state operations:

| Action | Result |
| --- | --- |
| `open` (default) | Build or reuse the official preview. |
| `status` | Inspect the open preview and connected browser views. |
| `capture_state` | Pause a connected view and save its current state. |
| `list_states` | List saved states for the current build. |
| `restore_state` | Reopen a listed state in a connected view, paused. |

```text
chromatic_web_preview {"action":"status"}
chromatic_web_preview {"action":"capture_state","viewId":"<returned viewId>"}
chromatic_web_preview {"action":"list_states"}
chromatic_web_preview {"action":"restore_state","viewId":"<returned viewId>","stateId":"<listed state ID>"}
```

Capture and restore use the already-open browser player. `viewId` is optional
when one view is unambiguous; choose one from `status` when several are open.
Restore requires a `stateId` from `list_states`. Build options `outputPath`,
`force`, and `timeoutMs` apply only to `open`.

## Watch browser play for a fixed duration

Use the existing `chromatic_web_preview` tool for the browser emulator. `chromatic_device_capture` is only for physical hardware. Recording needs a player view the user has open (not yet verified inside Hermes); preserve a person's active play.

1. Read `chromatic_web_preview` with `action: "status"`. Select a visible, running, idle player and copy its listener ID, view ID, ROM/runtime hashes, source revision, and recording generation into `recordingBinding`.
2. Call `action: "start_recording"` with that binding and optional `recordingDurationMs` (1,000–600,000; default 180,000). The immediate receipt is a queued job, not proof that recording began. Save its `recordingId`.
3. Poll `action: "recording_status"` with the original ID. `stop_recording` requests an early stop. The visible capture controls operate the same recorder, so a person's Stop takes priority.
4. Wait for `finished`: recorder stopped, tracks released, file committed, and the browser acknowledged that exact saved result. `read_capture` verifies the original file and returns its receipt; it does not decode media. Then close only your temporary preview.

Keep the view visible. Lost connection, hidden views, size limits, or interrupted finalization can yield partial or UNKNOWN results. Never retry an uncertain start or upload; read its original status. A project-wide unresolved journal blocks conflicting jobs across restarts. Preserve the original browser download and journal for diagnosis. This tool has no reset or reconciliation shortcut.

Closing a preview uses a fresh acknowledgment from every recording-capable view, blocks new capture starts locally, and waits up to a fixed 30 seconds for finalization. A human capture that started first refuses ordinary close. An UNKNOWN close retains the listener for inspection; process shutdown is bounded and may preserve an unresolved recording rather than claim a completed save.
