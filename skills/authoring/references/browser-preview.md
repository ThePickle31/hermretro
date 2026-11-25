# Open the official playable browser preview

Show the game to the user in the **hermretro emulator** beside the chat: once everything agreed with the user is in it and you have tested it, call `chromatic_present_game`, optionally with a short `note` on what to try. Do not open `chromatic_web_preview` URLs, including screenshot Open links, yourself, and do not reload the player with `drive_preview`. Only if the user says they cannot see the emulator, open `studio.playerUrl` from that result with `desktop_preview` (`action: "open"`); without desktop tools, give the user that URL. Give `chromatic_device_capture` URLs to the user without claiming they opened (not yet verified inside Hermes). Never launch an external browser yourself.

Browser availability is not a prerequisite for gameplay testing. If the browser
is missing, locked or unreachable, retain its state and continue with public
PyBoy `chromatic_emulator_run`, `chromatic_emulator_step` and `chromatic_emulator_observe` on the intended exact
ROM. Follow [headless fallback](../../rom-debugging/references/stepped-playtesting.md#when-browser-play-is-unavailable)
for setup and retained evidence; browser UI/annotation and physical capture
still require their own checks.

For new or iterated projects, build with `chromatic_rom_build` early and after each
meaningful change, and follow its `nextStep`; nothing opens for the user after a
build. A build is a checkpoint, not a hand-off: present it with `chromatic_present_game` only once
everything agreed with the user is in the game, at a safe point. Do not interrupt human play, saves or recordings;
resolve unknown outcomes before updating. Do not arbitrarily reload or autoplay.

After a confirmed close, the same plugin instance tries its last port again and uses another free port if it is occupied. The reopened view always gets a new private URL; old links are invalid. This does not discover, adopt, or stop other listeners.

Reuse the active preview URL or emulator/capture session for the same task. When temporary testing is complete, close only the session this task owns with `chromatic_web_preview_close`, `chromatic_emulator_close`, or `chromatic_device_capture {"action":"close"}`. Preserve user play (including paused games), ongoing recordings, and unresolved saves or commands; inspect status and retain recovery evidence before closing. Never scan processes, kill by name, claim an unfamiliar port, or clean up another task's session. An unknown action is not safe to replay.

Saved states, captures and timed recordings are on [preview states and recording](preview-states-and-recording.md);
what a preview result proves and frame annotation on [preview evidence and annotation](preview-evidence-and-annotation.md).

## The official export

For human-controlled browser play, use the selected project's official GB Studio
export through the plugin:

```text
chromatic_web_preview {}
```

`chromatic_web_preview {}` defaults to `action:"open"`. It runs the official `make:web`
compiler when needed and serves its genuine Binjgb/WebAssembly player and
cartridge. The compact handheld view keeps the original core and canvas. Use
the arrow keys to move, **Z/X** for A/B, **Enter** for Start, and **P** for
Select, or use the on-screen controls. Pause/resume and sound stay in the
toolbar. **⋯ More actions** contains Fullscreen, Restart game, Saved states
with capture timestamps, and the last saved capture.

Use **Emulation / Device** above the player to switch views. Your emulator stays
mounted and pauses in Device view; returning restores its previous play/pause
state. Device capture starts off. Open **Settings → Connection** to enable it,
select a Chromatic, and connect; USB audio is a separate choice. Switching views
does not connect or flash hardware. Finish an active recording or resolve its
uncertain status before switching away.

The plugin also adds native annotations in supporting browsers while retaining
the original exported files. The returned `url` is a reusable, capability-authenticated
`http://127.0.0.1:<port>/<secret>/` address. Treat that full URL as private.
The listener rejects invalid capabilities, foreign Host/Origin values, and
path escapes; player-state requests use private same-origin routes.

## Reuse and rebuild

An unchanged authored project reuses its authenticated export without rewriting
the HTML, runtime, WebAssembly, or ROM, including across MCP sessions when the
trusted toolchain cache is available. Within one live session, repeated calls
reuse the same server and URL. Authored project or project-local plugin changes
rebuild the real export while retaining the existing live preview URL. Load a
successful new build in the same owned tab only at the safe point described
above; a completed build does not mean the browser has loaded it. Ordinary
warm calls use indexed revisions; request `force: true` only when authoritative
whole-project verification and an intentional rebuild are necessary.

```text
chromatic_web_build {"outputPath":"build/browser-preview"}
chromatic_web_preview {"outputPath":"build/browser-preview"}
chromatic_web_preview {"outputPath":"build/browser-preview","force":true}
chromatic_web_preview_close {}
```

When an existing export must not be rebuilt, pass `cacheOnly:true` with
`force:false`. A missing, stale, or unverifiable export then fails before
compiler staging; ordinary preview calls retain their existing rebuild behavior.

`chromatic_web_build` exports without starting a server. Optional output directories stay
inside the selected project's generated `build/` directory; source resources
are not rewritten. `chromatic_web_preview_close` stops the listener and invalidates its
URL without deleting the reusable official export. Binjgb runs the interactive
browser preview; optional PyBoy remains a separate headless backend for exact
agent-controlled frames, inputs, and screenshots. Do not claim one backend's
observations as the other backend's evidence.

## Open a ready view

Hermes manages project selection and preparation before opening a view. For game preview, select or create the requested project, prepare missing build dependencies, and wait for a successful preview result before opening its URL. Never open an empty setup placeholder or ask the user to repeat the same request through an in-view button. For physical capture, select the project used to store its captures first; a compiled game is not required to watch the connected device. Keep the current working view if a replacement cannot open. Real access failures and unresolved operations remain explicit and must not be silently retried.
