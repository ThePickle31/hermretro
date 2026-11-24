---
name: rom-debugging
description: "Build, inspect, and debug Game Boy or Game Boy Color ROMs. Use for native project or GBDK build failures, browser previews, direct emulator playtesting, and source or cartridge diagnostics."
version: 1.0.34
license: MIT
metadata:
  hermes:
    tags: [chromatic, modretro, game-boy, rom, emulator, debugging]
    related_skills: [hermretro:authoring, hermretro:deployment, hermretro:setup]
---

# ModRetro Chromatic ROM debugging

Work from the user's actual cartridge and project. Select the intended project
explicitly; an unconfigured `chromatic_project_select` needs its absolute `.gbsproj` path,
and `chromatic_project_create` leaves it unselected unless called with `select:true`.
Never fall back to the bundled starter. See the [project selection rules](../authoring/references/agent-guide.md#start-and-select-the-intended-project)
when no authorized project or workspace is selected. If compiler or optional
PyBoy availability is uncertain, use `chromatic_toolchain_doctor`; report unavailable
checks rather than substituting a sample ROM or silently installing a runtime.
Use authorized ROMs and output roots; preserve existing user saves and evidence.

If the Chromatic tools cannot start or dependencies are missing, use the [setup skill](../setup/SKILL.md).
Select build and/or emulator components for the requested checks; ROM inspection
alone needs only the runtime.

## Browser previews

Show the game to the user in the **hermretro emulator** beside the chat: once everything agreed with the user is in it and you have tested it, call `chromatic_present_game`, optionally with a short `note` on what to try. Do not open `chromatic_web_preview` URLs, including screenshot Open links, yourself, and do not reload the player with `drive_preview`. Only if the user says they cannot see the emulator, open `studio.playerUrl` from that result with `desktop_preview` (`action: "open"`); without desktop tools, give the user that URL. Give `chromatic_device_capture` URLs to the user without claiming they opened (not yet verified inside Hermes). Never launch an external browser yourself.

If the browser is unavailable, locked or unreachable, retain its state and
continue gameplay with the public PyBoy loop below on the intended exact ROM;
browser access is not a prerequisite. Use the setup skill's `emulator` component
if needed. Keep browser UI/annotation and physical-device/capture checks
separate. See [headless fallback](references/stepped-playtesting.md#when-browser-play-is-unavailable)
for retained evidence and scoped failures.

Reuse the active preview URL or emulator/capture session for the same task. When temporary testing is complete, close only the session this task owns with `chromatic_web_preview_close`, `chromatic_emulator_close`, or `chromatic_device_capture {"action":"close"}`. Preserve user play (including paused games), ongoing recordings, and unresolved saves or commands; inspect status and retain recovery evidence before closing. Never scan processes, kill by name, claim an unfamiliar port, or clean up another task's session. An unknown action is not safe to replay.

### A preview URL refuses the connection

Preview URLs belong to the engine worker (one per chat) that opened them. A plugin
update, a restart, an idle worker shutdown, or a fresh chat can leave an old browser tab pointing at a closed server.
On every platform, including Windows, inspect `chromatic_web_preview {"action":"status"}`
in the owning session before reusing a URL. A connection-refused page alone is
not evidence of browser policy, a missing emulator, or a device-driver problem.

If there is no live preview in the current session, select the user's original
project and call `chromatic_web_preview {"action":"recover"}` to reopen its verified export without compiling. If no unchanged export exists, use `chromatic_web_preview {}` to build and open it, then present
the game again with `chromatic_present_game`. Do not invent the port, reuse a historical URL, or rebuild
with `force:true` just to reopen a server. Preserve any unresolved recording or
save from the old owner; opening a new preview does not recover unsaved state.
If a live listener is reported but the browser still fails, retain the exact
error and inspect the current owner; do not reset security settings or loop on
reload. An explicit access refusal must not be bypassed through another caller.

## Build and choose the right evidence

- Build the selected project with `chromatic_rom_build` and inspect its returned cartridge
  with `chromatic_rom_inspect`. Preserve compiler stderr and exit status on failures. A
  classified official-CLI `DEP0190` is a known deprecation; a failed process,
  missing/invalid ROM, or mismatched artifact is not a successful build. A GBDK
  `sourcePath` probe proves only its C source compiled.
- For direct model playtesting, use the optional PyBoy `chromatic_emulator_*` tools. The
  model making the change should choose each bounded input, inspect the actual
  returned frames, and decide what to do next; the emulator stays paused between
  calls.
- For interactive human play or annotation, `chromatic_web_preview {}` opens or reuses the
  selected project's official Binjgb browser export; show it to the user with
  `chromatic_present_game`. [Browser playback](references/emulation-and-regression.md#official-browser-play),
  [saved progress](../authoring/references/agent-guide.md#saved-progress), and
  [frame annotation](../authoring/references/agent-guide.md#annotate-a-game-preview) cover
  those modes. A browser export, a native `chromatic_rom_build`, PyBoy, and physical
  hardware each establish different facts. For physical Chromatic play or
  flashing, use [Chromatic deployment](../deployment/SKILL.md).

## Direct play and regression checks

Example: hold right, add A for two frames, then release every button:

```text
chromatic_emulator_run {"romPath":"<absolute ROM outputPath returned by the build>","restart":true,"initialFrames":120}
chromatic_emulator_observe {}
chromatic_emulator_step {"buttons":["right"],"frames":12,"sampleCount":4}
chromatic_emulator_step {"buttons":["right","a"],"frames":2,"sampleCount":2}
chromatic_emulator_step {"buttons":[],"frames":1,"sampleCount":1}
```

Every step supplies the **complete held-button set** and advances 1–3,600
frames. The set persists: repeated buttons stay held without a new press; `[]`
releases all buttons but still advances frames. `chromatic_emulator_observe {}` is inert:
it reads the genuine 160 × 144 framebuffer without advancing frames, delivering
input, or changing a recording. Use short steps near uncertain timings and
consecutive samples for flicker; a sampled frame proves nothing about gaps.

If images fail, check `execution` separately from `imageDelivery`. The input may
have advanced even if no image arrived or transport left execution unknown. Do
not repeat it to recover evidence; use inert observation or `chromatic_emulator_review`
of a retained interval. See [stepped playtesting](references/stepped-playtesting.md)
for execution status, contact sheets, cancellation, and cleanup.

Preserve the first failure and its inputs. After a source fix, build the new
cartridge and repeat the relevant button sets and frame counts from comparable
starting conditions; inspect behavior separately from animation/hash changes.
An unchanged ROM reuses its session; use `restart:true` for an intentional fresh
boot and `chromatic_emulator_close {}` before selecting another project. Enable
`recording:{}` on a fresh boot when the input history matters. For branching an
existing attempt, see [recordings and checkpoints](references/recorded-playtesting.md):
first send a neutral frame, and restore only into the identical ROM and runtime,
including the worker hash. A checkpoint from before a rebuild cannot be used for
the regression run.

## Diagnose and report

For named variables, the current scene, or authored collision/event references,
build with `captureDebugArtifacts:true`, start that exact ROM with
`debugMode:"source"`, and call `chromatic_emulator_debug` while paused. It requires
authenticated same-build artifacts and unchanged source; unsupported or
optimized-out data stays unavailable. For bounded OAM/VRAM/WRAM/HRAM inspection,
use `chromatic_emulator_inspect`. See [hardware and source diagnostics](references/emulation-and-regression.md#bounded-hardware-and-source-diagnostics)
or [cartridge headers, hardware limits, and common failures](references/hardware-and-cartridge.md).

Distinguish authored source, typechecks or generated imagery, static dialogue or
art previews, a compiled native cartridge, and actual observed runtime frames.
Neither sampled images nor host-side throughput prove audio, saves, physical
hardware behavior, or cartridge CPU-cycle performance. Report what ran, what
the frames showed, and what remains unverified. hermretro runs on Linux and macOS
only.

## In hermretro

- Builds open nothing for the user. With "Keep the playable copy current" on (the default), each
  successful project `chromatic_rom_build` also refreshes the playable web copy, and the result's `player`
  and `nextStep` report it. If `player.ready` is false, say the playable copy could not be updated and
  why. If `nextStep` says the preview still belongs to an older build, follow it and do not claim the new
  build is in a player. `chromatic_present_game` returns `BUILD_FIRST` until the copy is the engine's own copy of
  the current build; its `nextStep` says what to do.
- Playtest the ROM the user will play: the emulator beside the chat loads the web copy
  (`build/web/rom/*.gbc`), which holds the last build's own ROM byte for byte, unless the project has
  batteryless saves on (GB Studio then compiles the web copy without them). Pass its path to
  `chromatic_emulator_run` when you test right before presenting.
- The player saves the user's screenshots and recordings under `<project>/captures/`. **Ask Hermes** and
  marked annotations put a message with `Screenshot: <path>` into this game's chat: open that file.
- Each chat has its own engine worker for one project. After a long idle period it is shut down; the next
  call restores the selection, and its `notice` says the emulator, preview and held buttons were reset.
  Call `chromatic_*` tools directly, never from `execute_code`; delegated subagents can only inspect.
- An emulator lease left on a game by a worker that was killed (a Hermes restart, a crash) is cleared by
  hermretro itself once it proves the owning process is gone: `chromatic_emulator_run` then just works, and
  its `notice` names the lease it cleared. If `chromatic_emulator_run` is still refused with "Recording access
  is live or unresolved", the owner is still running: another chat's emulator on this game, or another app
  using the same project. Tell the user which game it is and that its emulator is open elsewhere. Do not
  delete the lease, kill a process or ask the user to restart Hermes.
- Links into `../<skill>/` are sibling hermretro skills: open them with
  `skill_view("hermretro:<skill>", file_path="references/<file>")`.
