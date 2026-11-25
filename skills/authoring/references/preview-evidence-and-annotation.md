# Preview evidence and annotation

What a [browser preview](browser-preview.md) result establishes, and annotating its frames.

## Read the preview evidence

`chromatic_web_build` and `chromatic_web_preview`'s `open` action return `exportIdentity.rom`
(relative path, SHA256 and bytes), the index identity and the complete validated
export inventory's digest/count/bytes.
These identify the ROM the export plays: the exact bytes of the last successful
`chromatic_rom_build` of the same sources, else (no such build, or batteryless saves on) this
web compilation's own output.
`sourceRevision` already includes project-plugin contents; `sourceIdentityScope`
states whether the other inputs came from the selected indexed revision or direct
descriptor/resource/asset hashes. The before/after fingerprint check is not a
continuous source lock, nor evidence that the browser has loaded the output.

`execution.args` is the actual staging invocation; the legacy top-level `args`
describes its published destination. Child PID and available spawn/exit/close,
stream bounds and stop reason are reported without claiming descendant observation.
Cache reuse reports `execution.status: "unrun"` and `exitCode: null`.
`resources` retains created stage/scratch/backup paths, identities, bounded
post-compiler size samples and independent cleanup outcomes, including failures.
Samples are not peak/APFS/RAM quotas; trusted attestation-key allocation remains
explicitly unobserved, separate from scratch and artifact totals. A cleanup warning
retains affected directories; a failed rollback retains the previous export.

`chromatic_web_preview` with `action:"open"` preserves the build result and adds the
in-process listener identity, start time and reuse state; it is not another
child process. Failures expose
`currentPreview`, including unresolved close ownership. `chromatic_web_preview_close` reports
whether a listener existed and its close was observed; a repeated empty close is
not a new observed close. Build and listener metadata do not establish gameplay
or visible browser behavior. State acknowledgments report the capture, storage,
or restore operation; verify reopening, audio and mute, fullscreen, and player
interaction in the actual browser before claiming those user-visible outcomes.

## Annotate a game preview

In a supporting host browser (not yet verified inside Hermes), **Annotate game** opens native annotation
mode on the existing player. Selecting the canvas freezes a frame. The picker
offers visible hardware sprites, small adjacent sprite groups, background/window
tiles, and a whole-frame fallback. Sprite grouping is an inference from OAM
positions and palettes; it does not establish character names or source asset IDs.
Raster effects and unusual priority modes can make hardware bounds approximate.
The original framebuffer is the visual reference.

The native color controls preview the selected object's captured pixels.
Color comparison/reset uses the original capture. **Resume game** requests an
exit from native annotations and continues only after that exit is confirmed.
If the host keeps the editor open, use **Esc** (again if the editor has focus),
or hold **Space** and click the player control. Color previews do not change
ROM bytes, live emulator memory, assets, dialogue, or source palettes. The
annotation host owns comments, saved annotations, and sending feedback to the
conversation.

Use the delivered annotation's exact ROM hash, source revision, frame and
hardware context to locate the requested change in the selected project.
Inspect the actual source before choosing an asset or actor: tile/OAM locations
are not source mappings. After editing, rebuild with `chromatic_web_preview` and load the
successful result at a safe point, preserving current play, saves and recordings.
An older annotation continues to describe its captured build;
do not apply its locations blindly to a new ROM.

The adapter is served by the existing authenticated preview listener. It adds
no simulator executable, MCP tool, dependency, or separate server. Its isolated
Binjgb inspection copy reads captured VRAM/OAM without changing the running
player. The official player retains emulation, input, audio, display settings,
and rewind. `preview.annotations` reports adapter injection only;
actual native support is detected in the page. Ordinary browsers still play the
game. If the host rejects annotation mode while the agent controls the browser,
return control to the user and let them open it normally.

Test doubles cover the callback contract only. Native acceptance requires the
actual host to select an object, preview/compare/reset colors, save and reopen an
annotation, then send it and inspect the received conversation context.
