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

## Tools for each task

| Task | Tools | Details |
| --- | --- | --- |
| Pick or start the game | `chromatic_session_status`, `chromatic_project_select`, `chromatic_project_create`, `chromatic_project_create_blank` | [project selection](references/project-selection.md) |
| Read game data | `chromatic_project_inspect`, `chromatic_project_inventory`, `chromatic_scene_inspect`, `chromatic_actor_inspect`, `chromatic_trigger_inspect`, `chromatic_script_inspect`, `chromatic_variable_inspect`, `chromatic_collision_inspect`, `chromatic_asset_inspect`, `chromatic_sprite_inspect`, `chromatic_palette_inspect`, `chromatic_tilemap_inspect`, `chromatic_world_dependencies` | [revisions](references/revisions.md) |
| Scenes, actors, triggers | `chromatic_scene_apply` (inline `operations`, or `operationsPath` for a JSON file), `chromatic_scene_create`, `chromatic_scene_update`, `chromatic_actor_create`, `chromatic_actor_update`, `chromatic_trigger_create` | [resource tools](references/resource-tools.md), [project authoring](references/project-authoring.md) |
| Events and scripts | `chromatic_event_describe` (any event's args and an example), `chromatic_script_edit`, `chromatic_script_transition` (scene switches), `chromatic_dialogue_update` | [event cookbook](references/event-cookbook.md), [GB Studio behaviours](references/gb-studio-behaviours.md) |
| Variables, settings, player speed | `chromatic_variable_set`, `chromatic_settings_update`, `chromatic_engine_field_update` | [project authoring](references/project-authoring.md) |
| Walls and rooms | `chromatic_collision_edit`; `chromatic_tilemap_atlas_create`, `chromatic_tilemap_create`, `chromatic_tilemap_edit` for rooms built from tiles | [tilemaps](references/tilemaps.md) (grid games: which route) |
| Art | `chromatic_asset_import` (several at once with `assets`, `sprite.paletteIndex`, the `metasprite` profile; returns the graphics analysis), `chromatic_sprite_edit`, `chromatic_palette_create`, `chromatic_palette_assign` | [pixel-art skill](../pixel-art/SKILL.md) |
| Look at art | `chromatic_sprite_preview`, `chromatic_sprite_contact_sheet` (`scale`), `chromatic_graphics_preview_scene` (`magnification`), all with `colorCorrection: "chromatic"` | [display colours](../pixel-art/references/hardware-and-imports.md#display-colors-the-chromatic-is-the-reference) |
| Music and sound | `chromatic_music_compose`, `chromatic_asset_import` (`.uge`, `.mod`, `.wav`, `.vgm`), `chromatic_emulator_audio` | [music and sound](references/music-and-sound.md) |
| Build | `chromatic_rom_build`, `chromatic_rom_inspect` | [building](references/building.md) |
| Play and check | `chromatic_emulator_run`, `chromatic_emulator_step` (one `inputs` list per sequence, `scale`), `chromatic_emulator_observe` (look without advancing), `chromatic_emulator_debug` (live player, actors, dialogue, variables by name), `chromatic_emulator_inspect` | [emulator playtesting](references/emulator-playtesting.md), [stepped playtesting](../rom-debugging/references/stepped-playtesting.md) |
| Retest after a rebuild | `chromatic_emulator_replay` (replays a recording on the new ROM, stops where frames differ) | [replay after a rebuild](../rom-debugging/references/recorded-playtesting.md#replay-after-a-rebuild) |
| Hand the game over | `chromatic_game_info`, `chromatic_present_game`, `chromatic_build_report` | [In hermretro](#in-hermretro) |

## Working in the studio

- Hermes may load the `chromatic_*` tools on demand. When they are not in your tool list, pass the names you are
  about to use (from the table above) to `tool_describe`, at most 10 per call, and run each with its own
  `tool_call`: one `chromatic_*` call per `tool_call`. No `tool_search` is needed for a name you know. Independent
  `tool_call`s can go in one turn; one that needs another's result (a revision, the emulator's state) waits for the
  next turn.
- Read the table above, then open a reference page only when you reach the step that needs it, not every page up
  front: whatever you load fills the context until a compaction drops it.
- After a context compaction, your next `chromatic_*` result carries `hermretroContext`: the project, the last
  build, the emulator's ROM and frame, the recording (its path, session and branch) and the skill pages you had
  loaded. Load this skill again and, of those pages, only the ones your next step needs: the summary keeps what you
  did, not how the tools work.
- Read game data through the inspect tools above, never with `cat`, `grep` or a script over `.gbsres` or
  `.gbsproj` files, and never open another game's project as an example: the event cookbook and
  `chromatic_event_describe` have working events. The game's other files (`docs/game/`, your PNGs, captures) are
  yours to open.
- For any helper code (drawing a PNG, computing collision rectangles, writing a `chromatic_scene_apply`
  operations file), write a script file in the game's own `scratch/` folder and run it; create the project first.
  `scratch/` stays on this machine and out of builds, publishes and build history. Give each file a name of its own
  for the job (`scratch/door-collision.py`, not `scratch/script.py`): another chat on the same game uses the same
  folder. One-shot chats refuse `python -c` and heredocs.

If the plugin needs setup or its tools cannot start, use the [setup skill](../setup/SKILL.md) first. Creating or iterating a playable game needs `runtime,build`, including its browser preview. Use runtime alone only for source inspection or edits that do not require a build; add `emulator` for local stepped play. Carry necessary authorized setup through installation and callable tools, then return to the requested game. Do not stop at a passive doctor report or ask the user to install Node/npm manually.

## Browser previews

Show the game to the user in the **hermretro emulator** beside the chat: once everything agreed with the user is in it and you have tested it, call `chromatic_present_game`, optionally with a short `note` on what to try. Do not open `chromatic_web_preview` URLs, including screenshot Open links, yourself, and do not reload the player with `drive_preview`. Only if the user says they cannot see the emulator, open `studio.playerUrl` from that result with `desktop_preview` (`action: "open"`); without desktop tools, give the user that URL. Give `chromatic_device_capture` URLs to the user without claiming they opened (not yet verified inside Hermes). Never launch an external browser yourself.

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

`chromatic_session_status {}` reports the current selection without granting access. Confirm it is the project the user intends; if none is selected or a different one is active, use `chromatic_project_select` with the intended absolute `.gbsproj` path before reading or editing project resources. To start a game, use `chromatic_project_create` without `destinationPath` (it goes in the Studio's games folder; pass an absolute unused destination under an existing canonical parent only for a folder the user names) and `select:true` when continuing in it. `starter` is included. `wrecklight` creates an editable adventure copy; compact installations require its matching local `templateSourcePath`. Never edit the source template. Discovery grants no access and neither creation nor selection expands an existing authorization boundary. See [project selection](references/project-selection.md) for the authorization rules, or the [Wrecklight remix guide](references/wrecklight-remix.md) for that template.

## Author native resources

- Start with `chromatic_project_inspect {}` and narrow `chromatic_project_inventory` or focused scene/script reads to the part being changed. `chromatic_scene_apply` uses the project `revision`; script edits use the exact target's `chromatic_script_inspect.revision`, and `chromatic_trigger_create` uses `chromatic_scene_inspect.sceneRevision`. Restart after `STALE_CURSOR`. For concurrent editor changes or a destructive global reverse-reference decision, see [revisions and the world index](references/revisions.md); the latter needs `chromatic_project_refresh {"mode":"strong"}`.
- Prefer semantic tools such as `chromatic_scene_apply`, `chromatic_script_edit`, `chromatic_script_transition`, and `chromatic_collision_edit`. Preserve unknown fields, stable resource/event IDs, script branches, collision bytes, plugins, and format versions. Never write `.gbsres` or `.gbsproj` files yourself: if no tool can express the change, tell the user what is missing. A distributed `chromatic_scene_apply` has best-effort rollback, not cross-file atomicity.
- Use the project's actual `mono`, `mixed`, or `color` mode. Actor coordinates are normally gameplay tiles; scene `x`/`y` are editor-canvas positions. Keep assets inside the selected project, preserve authored PNGs/sidecars and the reserved UI palette, and keep generated outputs separate from authored resources and existing tracked cartridges.
- Preserve native `EVENT_TEXT` wording and page boundaries by default; request wrapping or pagination only when the user wants a rewrite. Guard `chromatic_dialogue_update` with the same owner's `chromatic_script_inspect.revision`; use `validation:"reject"` when overflow must block the write. Unknown custom events remain opaque. See [dialogue and resource examples](references/project-authoring.md#dialogue-representation).

For example, to make a door go to another room: find both scene IDs, inspect the trigger and destination collision, insert a typed `chromatic_script_transition` using a valid landing tile, then build and directly check that entering and leaving the door works if gameplay verification is in scope.

## Choose the relevant detail

Open each page when a step needs it.

- [Native resource layout and tool examples](references/project-authoring.md): scenes, actors, events, variables, collision, palettes, settings, and focused edits.
- [Resource tools](references/resource-tools.md): every authoring tool by resource, relationship queries, `chromatic_scene_apply` batches and operations files.
- [Event cookbook](references/event-cookbook.md): working event JSON for a HUD, pickups, hazards and collision groups, gated exits, menus, threads, held buttons, sound effects and scene switches. `chromatic_event_describe` gives any other event's args, defaults and an example; never read GB Studio's source for them.
- [GB Studio behaviours](references/gb-studio-behaviours.md): what builds but misbehaves in play (sprite palette entry 2, text in `LOGO` scenes, locked start scripts, sprites over menus, `$00$` text tokens, top-down respawns, collision boxes, button presses).
- [Native tilemaps](references/tilemaps.md): when a grid game should use recipe tilemaps or a drawn PNG with collision, and rooms built from named 8 × 8 tiles. Mutations need the current revision; replacement operations require inspected preimages; decoration never changes collisions.
- [Building](references/building.md), [emulator playtesting](references/emulator-playtesting.md), [browser preview](references/browser-preview.md) with its [states and recording](references/preview-states-and-recording.md) and [evidence and annotation](references/preview-evidence-and-annotation.md).
- [Operating contract](references/operating-contract.md) (what each kind of evidence proves), [recovering a failed step](references/recovery.md), [platform and setup boundaries](references/platform-and-setup.md).
- [Music and sound](references/music-and-sound.md): write songs from note lists or a bundled track (`chromatic_music_compose`), import `.uge`, `.mod`, `.wav` and `.vgm` files with `chromatic_asset_import`, play them from events, and check the sound hardware with `chromatic_emulator_audio`.
- [Extensions and builds](references/extensions-and-build.md): custom events, scene modes, project-local plugins, official CLI and GBDK. Use existing visual events and scene modes when they express the mechanic; engine ejection needs authorization.
- [Packaged setup](../setup/references/setup.md): dependency details. `chromatic_toolchain_doctor` metadata readiness is not executable health; the setup skill preserves the user's authorized scope.
- [Pixel art](../pixel-art/SKILL.md) for image/palette work; [ROM debugging](../rom-debugging/SKILL.md) and [stepped playtesting](../rom-debugging/references/stepped-playtesting.md) for compilation, input-driven bugs, and real framebuffer evidence.

Verify the change at the level the request needs: reread the native resources, build the actual project when compilation matters, and inspect genuine emulator frames when behavior matters. A static preview or compiler probe does not show that the game was built or played; state any missing evidence.

## In hermretro

- Call `chromatic_*` tools directly (or through `tool_call`), never from inside `execute_code` (refused with `IDENTITY_REQUIRED`).
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
  For a game with `docs/game/TEST-PLAN.md` it needs each open check's result on this ROM (`checks`) and a
  `difficulty` statement from your own [finishable](../rom-debugging/SKILL.md#finishable) run, or it is refused;
  name that run's recording as `finishRun` (F1 `passed` or `failed` needs it).
  When the ending was unreachable, the run was skipped or the game has no ending, report that (F1 `failed` or
  `not run`, and why in `difficulty`), as `hermretro:game-planning` step 6 says.
- The references say MCP for the engine behind the `chromatic_*` tools.
- Links into `../<skill>/` are sibling hermretro skills: open them with
  `skill_view("hermretro:<skill>", file_path="references/<file>")`.
