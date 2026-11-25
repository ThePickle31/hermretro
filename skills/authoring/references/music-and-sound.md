# Music and sound

A game plays one song at a time with hUGEDriver (GB Studio 4 compiles every song for it; the project's
`musicDriver` setting changes nothing) and sound effects over it. Songs loop. A song keeps playing across scene
changes until another `EVENT_MUSIC_PLAY` or an `EVENT_MUSIC_STOP`.

Bring every song and sound in with a tool: `chromatic_music_compose` writes a song from notes or a bundled track,
`chromatic_asset_import` registers a `.uge`, `.mod`, `.wav`, `.vgm` or `.vgz` file. Both write the `.gbsres`
sidecar with an ID that stays the same (made from the file's path), so an event that names the song keeps working.
Without a sidecar GB Studio gives the file a new ID on every load and no event can name it. Never write a `.gbsres`
yourself and never play a song with a raw GBVM line.

## Write a song from notes

```json
{"assetPath": "assets/music/village.uge", "name": "Village", "ticksPerRow": 8,
 "instruments": {"pulse1": "pluck", "pulse2": "soft", "wave": "mellow"},
 "sections": [
   {"name": "A",
    "pulse1": "B4:4 D5:4 G5:6 F#5:2 | E5:4 G5:4 B5:6 A5:2",
    "pulse2": "G4:8 B4:8 | G4:8 B4:8",
    "wave": "G2:6 G2:2 D3:8 | E2:6 E2:2 B2:8",
    "noise": "kick:4 hat:2 hat:2 snare:4 hat:4 | kick:4 hat:2 hat:2 snare:4 hat:4"},
   {"name": "B", "pulse1": "E5:4 G5:4 C6:8 | D5:8 .:4 A4:4", "wave": "C3:8 G2:8 | D3:8 A2:8"}],
 "order": ["A", "A", "B", "A"]}
```

- **Rows.** Each channel is a list of rows separated by spaces; `|` is ignored, so use it for bar lines. A row is a
  note in scientific pitch (`C4`, `F#3`, `Bb5`; A4 is 440 Hz), `.` to rest or `-` to hold. `:N` makes it last N rows
  (`C4:4` is the note and three holds). A note rings until the next note or rest; an instrument with a decaying
  envelope fades on its own.
- **Channels.** `pulse1` (melody, C2–B7), `pulse2` (harmony, C2–B7), `wave` (bass, C1–B6, sounding at the written
  pitch) and `noise` (drums: `kick`, `snare`, `hat`). A channel left out of a section is silent there; a shorter
  channel holds to the section's longest.
- **Tempo.** A row lasts `ticksPerRow` frames (1/60 s). With 4 rows to a beat (16 to a 4/4 bar): 6 is 150 BPM,
  7 about 128 (the default), 8 about 112, 10 about 90.
- **Instruments.** Pulse: `lead` (bright, long fade), `soft` (quiet, long fade), `pluck` (short), `square` (steady,
  no fade), `thin` (narrow, medium fade). Wave: `bass` (full triangle), `mellow` (softer triangle), `saw`,
  `hollow` (square). Set one per channel for the song in `instruments`, or per section with
  `{"notes": "...", "instrument": "pluck"}`.
- **Form.** Up to 16 named sections of at most 256 rows, played in `order` (default: each once), up to 4,096 rows
  in all. A song compiles into one 16 KiB ROM bank: each distinct 64-row block of a channel costs 192 bytes, so
  repeat sections through `order` (when every section is a multiple of 64 rows, a repeat costs nothing) rather
  than writing new ones; a song that
  does not fit is refused (`INVALID_SONG`). The result gives the song's `id`, its `loopSeconds`, its compiled
  `romBytes` and a `playEvent`.
- **Changes.** Writing the same `assetPath` again needs `overwrite: true`. It replaces the notes and keeps the ID,
  so every event that plays the song still works.

### Bundled tracks

`{"bundled": "<track>"}` writes a finished original track to `assets/music/<track>.uge` (another `assetPath` is
allowed). They are hermretro's own music under its MIT license, so a game may ship them.

| Track | For | Tempo |
|---|---|---|
| `bright-start` | title screen | 150 BPM |
| `meadow-walk` | overworld | 112 BPM |
| `cave-echo` | dungeon, night | 90 BPM |
| `victory-lap` | win, ending | 150 BPM |

## Import music and sound files

```json
{"assets": [
  {"assetPath": "assets/music/theme.uge", "kind": "music", "sourcePath": "audio/theme.uge"},
  {"assetPath": "assets/sounds/coin.wav", "kind": "sound", "sourcePath": "audio/coin.wav"}]}
```

- `music`: a hUGETracker `.uge` (up to version 6) or a four-channel ProTracker `.mod` (GB Studio converts it), under
  `assets/music`. A song must compile into one 16 KiB ROM bank.
- `sound`: a `.wav` (PCM of 8 bits or more, or float, any number of channels; GB Studio mixes it to mono, resamples
  it to 8 kHz and plays it on the wave channel; at least 32 samples and at most about 3.6 s, one 16 KiB ROM bank) or
  a `.vgm`/`.vgz` that holds Game Boy sound (VGM 1.61 or newer, register writes and waits only, ending with its end
  marker, within one bank), under `assets/sounds`.
- Name files with a lowercase extension (`.uge`, `.mod`, `.wav`, `.vgm`, `.vgz`; all-uppercase also works except
  `.UGE`), and no file or folder name starting with a dot: GB Studio skips or misreads the rest. A file in a
  subfolder keeps that path in its sidecar (`assets/music/town/theme.uge` is `town/theme.uge`).
- Leave out `sourcePath` to register a file already at `assetPath`. The tool checks each file the way GB Studio
  reads it and refuses one it cannot play (`INVALID_AUDIO`, saying why); a batch with one bad file imports none.
- `chromatic_asset_inspect` reads a song or sound back with its sidecar and format details.
- **Moving or renaming.** Move a file and its `.gbsres` together (same new name plus `.gbsres`) and it keeps its ID
  and every event that plays it. The ID was made from the old path, so registering a new file at the old path later
  needs an explicit new `id`, or the import refuses it as `DUPLICATE_RESOURCE_ID`.

## Play it

Add the result's `playEvent` to a script with its own new `id`, for example first in a scene's start script:

```json
{"action": "insert", "target": {"sceneId": "<scene id>"}, "index": 0,
 "event": {"id": "<new UUID>", "command": "EVENT_MUSIC_PLAY", "args": {"musicId": "<song id>"}}}
```

A sound effect is `{"command": "EVENT_SOUND_PLAY_EFFECT", "args": {"type": "<sound id>", "priority": "medium"}}`.
The built-in effects need no file: `"type": "beep"` (`pitch` 1–8), `"tone"` (`frequency` in Hz) or `"crash"`, each
with `duration` in seconds and `wait` to pause the script until it ends. While an effect plays it takes over the
channels it uses (a `.wav` the wave channel) and the song resumes on them after.

## Check that it plays

Build, run the ROM and step past the point that should make sound, then call `chromatic_emulator_audio`. It reads
the sound hardware's registers on that frame: `active` is true when the sound hardware is on and the game drives a
channel (enabled, its DAC on, sent to a speaker). Each channel reports `active`, `enabled`, `dac`, `panned`, and
`startVolume` (the pulse and noise envelopes' starting volume) or `outputLevel` (the wave channel). The registers
show what the game drives, not what comes out: a pulse or noise note whose envelope has faded keeps its channel
active until the next note or cut. A song keeps its channels active between notes; a short effect ends within
frames, so check right after it starts. When a scene that should have music
is silent, compare the event's `musicId` with the song's `id` and check that the scene's script runs the event.
