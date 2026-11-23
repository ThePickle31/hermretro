---
name: authoring
description: "Create or edit native game projects, scenes, events, and gameplay for Game Boy or Game Boy Color."
version: 1.0.34
license: MIT
metadata:
  hermes:
    tags: [chromatic, modretro, game-boy, gb-studio, authoring]
    related_skills: [hermretro:game-planning, hermretro:pixel-art, hermretro:rom-debugging, hermretro:setup]
---

# ModRetro Chromatic authoring

Work in the creator's genuine `.gbsproj` / `.gbsres` project so the result stays editable in the game editor and builds to a real cartridge.

If the plugin needs setup or its tools cannot start, use the [setup skill](../setup/SKILL.md) first. Creating or iterating a playable game needs `runtime,build`, including its browser preview. Use runtime alone only for source inspection or edits that do not require a build; add `emulator` for local stepped play. Carry necessary authorized setup through installation and callable tools, then return to the requested game. Do not stop at a passive doctor report or ask the user to install Node/npm manually.

## Browser previews

Show the game to the user in the **hermretro emulator** beside the chat: when it is ready to try (after your own testing), call `chromatic_present_game`, optionally with a short `note` on what to try. Do not open `chromatic_web_preview` URLs, including screenshot Open links, yourself, and do not reload the player with `drive_preview`. Only if the user says they cannot see the emulator, open `studio.playerUrl` from that result with `desktop_preview` (`action: "open"`); without desktop tools, give the user that URL. Give `chromatic_device_capture` URLs to the user without claiming they opened (not yet verified inside Hermes). Never launch an external browser yourself.

A missing, locked or unreachable browser does not block gameplay checks. Retain
its state and continue with public PyBoy `chromatic_emulator_run`, `chromatic_emulator_step` and
`chromatic_emulator_observe` on the intended exact ROM. Follow the [headless fallback](../rom-debugging/references/stepped-playtesting.md#when-browser-play-is-unavailable)
for setup, retained evidence and the separate browser/physical acceptance limits.

For new or iterated projects, build with `chromatic_rom_build` early and after each
meaningful change, and follow its `nextStep`; nothing opens for the user after a
build. A build is a checkpoint for you, not a hand-off: keep authoring until
everything agreed with the user is in the game. For a new game that is the whole
approved list (`docs/game/FIRST-BUILD.md`) or brief, built in one go. Only then
playtest it and present it with `chromatic_present_game`, at a safe point: do not interrupt human play, saves or recordings, and resolve
unknown outcomes first. Do not arbitrarily reload or autoplay.

## Select the intended project

`chromatic_session_status {}` reports the current selection without granting access. Confirm it is the project the user intends; if none is selected or a different one is active, use `chromatic_project_select` with the intended absolute `.gbsproj` path before reading or editing project resources. To start a game, use `chromatic_project_create` without `destinationPath` (it goes in the Studio's games folder; pass an absolute unused destination under an existing canonical parent only for a folder the user names) and `select:true` when continuing in it. `starter` is included. `wrecklight` creates an editable adventure copy; compact installations require its matching local `templateSourcePath`. Never edit the source template. Discovery grants no access and neither creation nor selection expands an existing authorization boundary. See [project selection](references/agent-guide.md#start-and-select-the-intended-project) for the authorization rules, or the [Wrecklight remix guide](references/wrecklight-remix.md) for that template.

## Author native resources

- Start with `chromatic_project_inspect {}` and narrow `chromatic_project_inventory` or focused scene/script reads to the part being changed. `chromatic_scene_apply` uses the project `revision`; script edits use the exact target's `chromatic_script_inspect.revision`, and `chromatic_trigger_create` uses `chromatic_scene_inspect.sceneRevision`. Restart after `STALE_CURSOR`. For concurrent editor changes or a destructive global reverse-reference decision, see [revisions and the world index](references/agent-guide.md#inspect-efficiently-and-manage-revisions); the latter needs `chromatic_project_refresh {"mode":"strong"}`.
- Prefer semantic tools such as `chromatic_scene_apply`, `chromatic_script_edit`, `chromatic_script_transition`, and `chromatic_collision_edit`. Preserve unknown fields, stable resource/event IDs, script branches, collision bytes, plugins, and format versions. If a tool cannot express the change, inspect neighboring resources and make the smallest compatible native edit. A distributed `chromatic_scene_apply` has best-effort rollback, not cross-file atomicity.
- Use the project's actual `mono`, `mixed`, or `color` mode. Actor coordinates are normally gameplay tiles; scene `x`/`y` are editor-canvas positions. Keep assets inside the selected project, preserve authored PNGs/sidecars and the reserved UI palette, and keep generated outputs separate from authored resources and existing tracked cartridges.
- Preserve native `EVENT_TEXT` wording and page boundaries by default; request wrapping or pagination only when the user wants a rewrite. Guard `chromatic_dialogue_update` with the same owner's `chromatic_script_inspect.revision`; use `validation:"reject"` when overflow must block the write. Unknown custom events remain opaque. See [dialogue and resource examples](references/project-authoring.md#dialogue-representation).

For example, to make a door go to another room: find both scene IDs, inspect the trigger and destination collision, insert a typed `chromatic_script_transition` using a valid landing tile, then build and directly check that entering and leaving the door works if gameplay verification is in scope.

## Choose the relevant detail

- [Native resource layout and tool examples](references/project-authoring.md): scenes, actors, events, variables, collision, palettes, settings, and focused edits.
- [Native tilemaps](references/tilemaps.md): fixed-size rooms built from named 8 × 8 tiles. Capture exact existing patterns or deliberately fill; mutations need the current revision. Ordinary edits preserve protected cells; exclusive replacement operations require inspected preimages. Decoration must not infer or clear collisions.
- [Extensions and builds](references/extensions-and-build.md): custom events, scene modes, project-local plugins, official CLI and GBDK. Use existing visual events and scene modes when they express the mechanic; engine ejection needs authorization.
- [Packaged setup](../setup/references/setup.md): dependency details. `chromatic_toolchain_doctor` metadata readiness is not executable health; the setup skill preserves the user's authorized scope.
- [Pixel art](../pixel-art/SKILL.md) for image/palette work; [ROM debugging](../rom-debugging/SKILL.md) and [stepped playtesting](../rom-debugging/references/stepped-playtesting.md) for compilation, input-driven bugs, and real framebuffer evidence.

Verify the change at the level the request needs: reread the native resources, build the actual project when compilation matters, and inspect genuine emulator frames when behavior matters. A static preview or compiler probe does not show that the game was built or played; state any missing evidence.

## In hermretro

- Call `chromatic_*` tools directly, never from inside `execute_code` (refused with `IDENTITY_REQUIRED`).
  A delegated subagent can only inspect a project; selecting, creating, editing, building and emulator
  play run in the main conversation (`PARENT_ONLY`, `LEASE_REQUIRED`).
- Each chat has its own engine worker bound to one project folder: once a project is selected, another
  folder fails with `PATH_OUTSIDE_PROJECT`, so use a new chat for it. If another chat is editing or
  building the same project, edits fail with `PROJECT_WRITER_BUSY`: wait, or continue in that chat.
- `chromatic_project_create` and `chromatic_project_create_blank` without `destinationPath` create
  `<plugin>/games/<name>`. Created, selected and built projects appear on the Studio's Games page.
- With the plugin setting "Keep the playable copy current" on (the default), each successful
  `chromatic_rom_build` also refreshes the playable web copy; its result's `player` and `nextStep` say so.
  If `player.ready` is false, say the playable copy could not be updated and why. `chromatic_present_game`
  returns `BUILD_FIRST` until the copy is the engine's own copy of the current build; its `nextStep` says what to do. An emulator the user already has
  open offers a newer build with a banner. You never see that player: do not claim what it shows.
- In the player the user can mark part of the screen or press **Ask Hermes**: the frame is saved under
  `<project>/captures/` and a message with `Screenshot: <path>` is put into this game's chat. Open that file.
- For a new game, the approved list (`docs/game/FIRST-BUILD.md`) or, with `hermretro:game-planning`,
  the brief and `docs/game/TEST-PLAN.md` say what the first build holds; check every item against the
  exact ROM before presenting, and name anything missing in the build report.
- Before presenting, fill in the game card with `chromatic_game_info` (cover art, title, tagline,
  description, genres); `chromatic_present_game` refuses with `GAME_INFO_INCOMPLETE` until it is complete.
  End every turn that changed or built the game with one `chromatic_build_report` (the Build page's card).
- The references say MCP for the engine behind the `chromatic_*` tools.
- Links into `../<skill>/` are sibling hermretro skills: open them with
  `skill_view("hermretro:<skill>", file_path="references/<file>")`.
