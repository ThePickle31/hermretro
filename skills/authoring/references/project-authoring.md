# Native game project authoring

## Project and resource layout

Modern native game projects store a small JSON project manifest next to granular resource files. An upstream template has this shape:

```text
MyGame/
├── MyGame.gbsproj
├── project/
│   ├── settings.gbsres
│   └── scenes/
│       └── outside/
│           ├── scene.gbsres
│           ├── actors/merchant.gbsres
│           └── triggers/door.gbsres
├── assets/
│   ├── backgrounds/
│   ├── sprites/
│   ├── music/
│   ├── sounds/
│   ├── fonts/
│   ├── avatars/
│   └── tilesets/
└── plugins/
```

Do not assume older releases have the same format. A `.gbsproj` can contain `_resourceType: "project"`, `name`, `author`, `_version`, and `_release`; granular settings, scenes, actors, and triggers carry their own `_resourceType`. Assets can also have adjacent `.gbsres` metadata files. Inspect the actual project before choosing a write strategy.

Example scene fields observed in an upstream template:

```json
{
  "_resourceType": "scene",
  "id": "94c18861-b352-4f49-a64d-52f2e3415077",
  "type": "TOPDOWN",
  "name": "Outside",
  "width": 32,
  "height": 32,
  "backgroundId": "1b7fa267-d716-40f0-b0d0-f4f966610e07",
  "script": [],
  "collisions": "..."
}
```

The scene's `x` and `y` are editor-canvas positions; its `width` and `height` describe gameplay tiles. An actor's `x` and `y` are in-scene positions, usually with `coordinateType: "tiles"`. Do not confuse canvas layout coordinates with gameplay coordinates.

Actor script arrays include `script`, `startScript`, `updateScript`, and hit-script variants. An interaction such as dialogue belongs in `script`; unconditional initialization belongs in `startScript`. Scene scripts, triggers, prefabs, and custom events can also own events.

## Semantic tool calls

Engine tool names are mostly `<domain>_<operation>` identifiers, without `gbstudio_`
(the device tools are just `device`, `setup`, `flash` and `play`); Hermes exposes each
one as `chromatic_<name>`, such as `chromatic_project_select` or `chromatic_flash`. A default session has no authorized
workspace or selected project. For an existing project, explicitly select its
absolute path, then inspect it:

```text
chromatic_toolchain_doctor {}
chromatic_session_status {}
chromatic_project_select {"projectPath":"/absolute/path/to/games/MyGame/MyGame.gbsproj"}
chromatic_project_discover {}
chromatic_project_inspect {}
chromatic_project_inventory {"resourceTypes":["scene","actor","trigger","asset","variable"],"detail":"standard"}
```

For a new project, leave `destinationPath` out: hermretro creates it in its games folder (`<plugin>/games/<name>`). For a folder the user names, use an absolute
new destination.
Its real canonical parent directory must already exist; creation neither makes
missing parents nor overwrites an existing destination, even an empty one:

```text
chromatic_project_create {"name":"My Game","template":"starter"}
```

The minimal `starter` is the only template.

This authorizes only the created `MyGame` project, not its parent or siblings.
It remains unselected unless `select: true` is explicit; otherwise select the
returned project descriptor before authoring or building.

For sibling projects, configure their common `GB_STUDIO_WORKSPACE_ROOT` before
server startup. It authorizes a fixed workspace without selecting a project;
creation, discovery, and selection may then use paths relative to it:

```text
chromatic_project_discover {"projectPath":"games/MyGame/MyGame.gbsproj"}
chromatic_project_select {"projectPath":"games/MyGame/MyGame.gbsproj"}
```

Discovery never authorizes or selects a project; attempting the relative flow
without an authorized workspace fails closed, including relative creation.
Neither create nor select calls expand an existing authorization boundary.
`GB_STUDIO_PROJECT_ROOT` explicitly selects the configured descriptor or
project directory; without a separately authorized workspace its authority
ends at that directory.
Unselected project operations fail with `PROJECT_SELECTION_REQUIRED`. Selecting
the bundled starter requires `allowStarter: true`; `chromatic_project_create` instead
copies the chosen template into the authorized new destination.

Use native engine-field tools for reusable project configuration rather than
rewriting settings-resource JSON by hand:

```text
chromatic_engine_field_inspect {"limit":50}
chromatic_engine_field_update {"updates":[{"id":"<existing-engine-field-id>","value":1}],"expectedRevision":"<returned-resource-revision>"}
```

Resolve the actual field identifier from the selected project, retain numeric
checkbox values, and omit `expectedRevision` only when an optimistic
precondition is unnecessary.

`chromatic_project_inspect` is compact and revision-aware. Normalized inventory returns
separate arrays for scenes, actors, triggers, assets, palettes, and variables;
scene `actorIds`/`triggerIds` refer to those collections. Filter/paginate when
possible and refresh after `STALE_CURSOR`. The old nested shape is available only
with `chromatic_project_inventory {"layout":"legacy","detail":"full"}`.

The selected project's session-owned in-memory world index performs one complete
cold census for exact totals, then serves focused warm reads and incrementally
updates committed mutation paths. Reuse IDs returned by scene/actor mutations;
do not rebuild a complete inventory after each actor. It creates no index/cache
files in the authored project. Optional telemetry is available through
`chromatic_session_status {"includeIndexStats":true}`. The versioned project revision is
`sha256-merkle-v2`; project revision tokens/cursors from before the upgrade become
stale once, while individual resource revisions remain exact-byte SHA-256.

The public revision covers the selected descriptor, `project/**`, and
`assets/**`. Plugin-owned native resources and event-handler identities also
affect semantic freshness separately. Server-authored changes are immediately
visible; external editor changes are eventually watcher-observed. Use expensive
`chromatic_project_refresh {"mode":"strong"}` only when authoritative whole-project
verification is required, including globally sensitive destructive checks;
an ordinary warm read cannot prove that a concurrent external edit has already
been delivered.

`chromatic_world_dependencies` separates executable effective gameplay dependencies from
conservative structural authored references; commented-out events do not become
active runtime dependencies. Use this genre-neutral relationship graph to
inspect references before changing an actor, scene, script, or authored global
variable.

```text
chromatic_world_dependencies {"node":{"type":"variable","id":"0"},"direction":"incoming","depth":2,"limit":25}
```

Relationship analysis is static authored-resource evidence, not proof that an
actual cartridge was built or played. Semantic query cursors
expire when project revision, selection generation, semantic generation, or the
query itself changes.

Create an RPG-style scene and then use its returned ID:

```text
chromatic_scene_create {"name":"Moonlit Market","type":"TOPDOWN","width":20,"height":18}
chromatic_actor_create {"sceneId":"<returned-scene-id>","name":"Lantern Merchant","x":8,"y":7,"direction":"down","dialogue":"Fresh lantern oil, traveler?"}
chromatic_actor_update {"sceneId":"<scene-id>","actorId":"<actor-id>","x":9,"y":7}
chromatic_trigger_create {"sceneId":"<scene-id>","name":"North Gate","x":10,"y":0,"width":2,"height":1}
```

Actor and trigger updates preserve the existing resource ID, `_index`,
filename, unrelated script arrays, and unknown metadata. Scene tile bounds and
trigger rectangle footprints are validated; actor sprite references must refer
to actual registered assets. Deletion rejects detectable authored references.

An actor's or trigger's `symbol` names its compiled scripts (`actor_door` compiles
`actor_door_interact`, `actor_door_update`, …), so it is unique across the whole
project, compiled names included, and follows the name: a new one gets
`actor_<name>` or `trigger_<name>` (`_2`, `_3`, … when taken, as for two doors in
two scenes), and renaming it gives it a new one when the name's symbol changes or
its current symbol is shared. Setting `symbol` yourself is refused with
`INVALID_PROPERTY`. A project made before this can hold two resources with one
symbol, or a custom script whose symbol matches an actor's compiled name, which
GB Studio compiles as one script: each is a `DUPLICATE_SYMBOL` diagnostic naming
the owners and their ids, and `chromatic_rom_build` refuses to build until all
but one are renamed. `chromatic_project_inspect` shows only its first five
diagnostics (`health.byCode` counts them all); list every one with
`chromatic_project_inventory {"resourceTypes":["diagnostic"]}`, following
`nextCursor`. These three read the whole project from disk first, so they check
a file edited outside the tools at once.

`chromatic_scene_inspect` returns both the whole-project `revision` for `chromatic_scene_apply` or
`chromatic_scene_delete` and the exact `sceneRevision` for `chromatic_trigger_create` or a scene-owned
script edit. For an actor-, trigger-, or scene-owned script, use that same target's
`chromatic_script_inspect.revision` to guard `chromatic_script_edit`, `chromatic_script_transition`, or
`chromatic_dialogue_update`; a successful dialogue update returns the owner revision for a
subsequent edit. A project revision does not guard an individual script resource.
`chromatic_script_inspect` names its script with `sceneId` and optional `actorId`, `triggerId`,
`scriptKey` and `branchPath` (or the same fields as `target`); `chromatic_script_edit` and
`chromatic_script_transition` take them as `target`.

For related edits, `chromatic_scene_apply` accepts 1–100 ordered typed operations such as
`actor.create`, `trigger.update`, `event.edit`, `collision.edit`, or
`variable.upsert`; later operations can refer to resources created earlier in
the same batch; deleting a resource and creating one with the same `id` in one
batch replaces it. `changedPaths` lists only files whose content changes. Use
`dryRun` for validation and `expectedRevision` when guarding
against external edits. Its returned `transactionGuarantee` distinguishes
`legacy-single-file-atomic` from `distributed-best-effort-rollback`; distributed
resource edits are not instantaneously atomic across files. An external change
that prevents safe rollback becomes `TRANSACTION_RECOVERY_CONFLICT` instead of
silently replacing authored content.

Update an existing interaction while preserving the actor:

```text
chromatic_dialogue_update {"sceneId":"<scene-id>","actorId":"<actor-id>","text":"The north gate opens at sunrise."}
chromatic_dialogue_analyze {"sceneId":"<scene-id>","actorId":"<actor-id>","includeSuggestion":true}
chromatic_dialogue_update {"sceneId":"<scene-id>","actorId":"<actor-id>","text":"A deliberately longer instruction for the player.","validation":"reject"}
chromatic_dialogue_update {"sceneId":"<scene-id>","actorId":"<actor-id>","text":"A deliberately longer instruction for the player.","wrap":"word","paginate":true}
```

A trigger uses `triggerId` instead of `actorId`. Analysis uses the selected
project font and preserves existing page boundaries. `chromatic_actor_create` and
`chromatic_dialogue_update` accept optional `validation: "warn" | "reject"`,
`wrap: "none" | "word"`, and `paginate: boolean`. By default both preserve the
requested text and pages exactly; when a selected font exists, their successful
response adds at most eight `fitWarnings` plus:

```text
dialogueFit: { valid, confidence, font: { id, name, variableWidth },
               pageCount, lineCount, maximumMeasuredLinePx,
               diagnosticCount, diagnosticCounts }
```

`validation: "reject"` returns `DIALOGUE_OVERFLOW` before creating/updating any
actor or native dialogue resource. Word wrapping/pagination transforms text
only when explicitly requested, preserves original authored page boundaries,
and retains unrelated event arguments. Extension-defined event commands remain
opaque; script editing preserves them without assuming their argument layout.
When no font is selected, omitted options preserve legacy behavior; do not
pretend font-aware validation ran. `chromatic_dialogue_preview` remains a labeled static
authored projection, not a cartridge screenshot. Use actual IDs from inventory;
never invent a reference to a sprite, background, scene, actor, or variable.

Add a native nested event, typed transition, authored global variable, or bounded
hexadecimal byte-run collision edit:

```text
chromatic_variable_set {"name":"gate_open","symbol":"var_gate_open"}
chromatic_script_edit {"action":"insert","target":{"sceneId":"<scene-id>","actorId":"<actor-id>"},"event":{"command":"EVENT_IF","args":{"condition":{"type":"eq","valueA":{"type":"variable","value":"<variable-id>"},"valueB":{"type":"number","value":1}}},"children":{"true":[{"command":"EVENT_TEXT","args":{"text":"The gate is open."}}],"false":[{"command":"EVENT_ACTOR_SET_DIRECTION","args":{"actorId":"$self$","direction":{"type":"direction","value":"up"}}}]}}}
chromatic_script_transition {"target":{"sceneId":"<scene-id>","triggerId":"<trigger-id>"},"destinationSceneId":"<destination-id>","x":10,"y":13,"direction":"up"}
chromatic_collision_edit {"sceneId":"<scene-id>","edits":[{"shape":"rectangle","x":2,"y":3,"width":4,"height":1,"value":15}]}
```

Every tool that writes a script (`chromatic_script_edit`, `chromatic_scene_apply`,
the create and update tools' `properties`) gives each event without an `id`,
nested ones included, a stable unique one (read it back from the result or
`chromatic_script_inspect`); supply your own only to name an event you refer to
later. Arguments GB Studio compiles as script
values must be typed: an actor direction is `{"type":"direction","value":"up"}`
and a position `{"type":"number","value":3}` in `EVENT_ACTOR_SET_DIRECTION`,
`EVENT_IF_ACTOR_DIRECTION`, `EVENT_ACTOR_SET_POSITION`,
`EVENT_ACTOR_SET_POSITION_RELATIVE`, `EVENT_ACTOR_MOVE_TO`,
`EVENT_ACTOR_MOVE_RELATIVE`, `EVENT_IF_ACTOR_AT_POSITION` and the
`EVENT_SWITCH_SCENE` coordinates. A plain value there, a direction other than
`up`, `down`, `left` or `right`, or an actor direction event without its
`direction` is refused with `INVALID_EVENT` instead of failing the build later;
a variable or expression value is accepted, and a commented-out event is not
checked. `EVENT_SWITCH_SCENE`'s own `direction` stays a plain string. A command
that is not a GB Studio event is refused the same way, naming the nearest real
events; GB Studio would build the game without it. An event GB Studio lists but
can no longer compile (`EVENT_WEAPON_ATTACK`) is refused too, also when an edit
moves an old one or a patch's branches hold one, naming its replacement and how
to convert; a single-file project from before GB Studio 2.0.0 r14 keeps it, since
GB Studio converts it on load. A project with plugin events
(`plugins/*/**/events/event*.js`) keeps any command, and its build fails with
`UNKNOWN_EVENT_COMMAND` when GB Studio has no compiler for one, or
`SCRIPT_EVENT_COMPILE_FAILED` when no plugin compiles `EVENT_WEAPON_ATTACK`.

`chromatic_event_describe` answers what an event takes, from GB Studio's own event definitions: with no arguments
its categories, with `query`, `category` or `includeDeprecated` matching events (40 at a time; `nextCursor` gives
the rest), with `events` (up to five) every arg's type, default, allowed values and the conditions under which it is
used, child branches, warnings, deprecation with the replacement and how to convert, what the event needs first
(`requires`), and an example event (`detail: "compact"` for the shapes alone). The
[event cookbook](event-cookbook.md) has working scripts for HUDs, pickups, hazards, gated exits, menus, threads,
held buttons and sound effects; [GB Studio behaviours](gb-studio-behaviours.md) lists what builds but misbehaves in
play. `chromatic_rom_build` adds warnings for text in a `LOGO` scene (`TEXT_IN_LOGO_SCENE`), a `$0$` text token
(`TEXT_VARIABLE_TOKEN`), actors or the player under a right-hand menu (`ACTORS_OVER_MENU`) and deprecated events
(`DEPRECATED_EVENT`), following custom scripts and prefabs, and sprite palette slots no sprite tile uses
(`UNUSED_SPRITE_PALETTE_SLOTS`); the ROM still builds. A build GB Studio compiled without an event it does not know
fails with `UNKNOWN_EVENT_COMMAND`, and one that stops on an event's compile with
`SCRIPT_EVENT_COMPILE_FAILED`.

`chromatic_script_edit` also supports `update`, `delete`, and `move`, including
`branchPath` segments identified by stable event ID and branch name. Preserve
extension-defined custom event commands and unknown event arguments.
`chromatic_variable_set` authors editable global project metadata; it does not write
emulator memory or map a variable name to a hardware address.
Collision edits preserve untouched opaque byte values and support `replace`,
`or`, and `andNot`; native collisions are hexadecimal byte runs, never base64.

Register project-local PNG resources and author scene palettes. The direct
`chromatic_palette_paint` example below is for a background without a bound tilemap recipe:

```text
chromatic_asset_import {"assetPath":"assets/backgrounds/market.png","kind":"background","background":{"autoColor":false}}
chromatic_asset_import {"assetPath":"assets/sprites/merchant.png","kind":"sprite","sprite":{"profile":"directional"}}
chromatic_palette_create {"name":"Market Lanterns","colors":["#071821","#306850","#86c06c","#e0f8cf"]}
chromatic_palette_assign {"sceneId":"<scene-id>","target":"background","slot":0,"paletteId":"<palette-id>"}
chromatic_palette_paint {"backgroundId":"<background-id>","sceneId":"<scene-id>","edits":[{"x":2,"y":3,"width":4,"height":1,"slot":0}]}
chromatic_graphics_analyze_scene {"sceneId":"<scene-id>"}
```

Imports currently support distributed projects and never read outside the same
selected project or overwrite existing PNG/sidecar resources. Sprite profiles
must match real 16×16 static, 48×16 directional, 96×16 directional animated, or
compatible existing-template resources. Background and sprite palette tables
are separate; configured scene slots are not necessarily consumed, and the
UI/font slot is protected by default.

For a bound background, use `chromatic_tilemap_inspect` and then `chromatic_tilemap_edit` with
`replace_cells`, exact preimages and the current revision. A palette-only edit
retains the inspected pixel hash; direct `chromatic_palette_paint` would leave the recipe
out of sync. See [native tilemaps](tilemaps.md#replace-selected-cells).

When replacing background art, import the new PNG first, then preserve the old
palette assignments with a separate revision-checked operation:

```text
chromatic_asset_update {"assetId":"<new-background-id>","copyTileColorsFrom":"<old-background-id>","expectedRevision":"<current-project-revision>","dryRun":true}
```

Review the changed path, then apply with `dryRun:false`. Both backgrounds must
use manual color and have matching PNG and metadata dimensions. The destination
grid must be empty or already identical. This preserves existing UI-slot cells;
it does not authorize painting new ones. Keep later palette edits outside the
preserved UI cells. Scene assignment is a separate edit.

Patch, rather than replace, settings:

```text
chromatic_settings_update {"settings":{"colorMode":"mixed"}}
chromatic_settings_update {"settings":{"defaultFontId":"<existing-font-asset-id>"}}
chromatic_settings_update {"settings":{"startMoveSpeed":2}}
```

`startMoveSpeed` is the player's move speed in pixels per frame in `TOPDOWN`, `SHMUP` and `POINTNCLICK`
scenes (GB Studio's choices are 0.25, 0.5, 1, 2, 3 and 4; 1 is the default). Other scene types ignore it:
`PLATFORM` movement is the platformer engine fields (`plat_walk_vel`, `plat_run_vel` and the rest) and
`ADVENTURE` movement is `adv_walk_vel` and `adv_run_vel`, all read and changed with
`chromatic_engine_field_inspect` and `chromatic_engine_field_update`.

The requested `defaultFontId` must resolve to an actual project font. An invalid
ID returns `FONT_NOT_FOUND` before writing project settings.

`mono` targets original Game Boy; `mixed` supports original hardware with GBC color enhancements; `color` is GBC-only. Inspect project settings and the compiled cartridge header before asserting compatibility.

## Dialogue representation

Upstream resource files represent ordinary dialogue as:

```json
{
  "id": "<stable-event-uuid>",
  "command": "EVENT_TEXT",
  "args": {
    "text": "Meow!"
  }
}
```

Existing interactions may contain a dialogue event followed by flags, conditionals, custom-event calls, or branching child events. Update the existing text event in place when possible. A new event gets its unique ID from the tool that adds it; preserve event order and unrelated branches. Never replace the entire `script` merely to rewrite a sentence.

`chromatic_dialogue_analyze` recursively scans native `EVENT_TEXT` events within scene,
actor, trigger, and nested branch scripts. It resolves the actual
`settings.defaultFontId` rather than assuming any available font. Fixed fonts
use their actual cell width; variable-width fonts use their native
magenta-padding convention. Preserve project-defined custom event commands as
opaque script data; do not claim to understand an unknown extension's text
layout. The supported variable-width font distinguishes narrow `i`/`l`/`.`
glyphs, spaces, and wide `W`/`M`/`A` glyphs; never substitute a blanket
character-count rule for actual font measurement.

The conservative standard fit profile uses 128 pixels, at most three visible
lines, and reserves 24 pixels when an avatar is present. Existing string-array
page boundaries remain separate. Word wrapping, pagination, or replacement
suggestions occur only when explicitly requested; bounded default fit warnings
never silently rewrite authored text. Interpolation/control-token widths and
exact native runtime window/scroll behavior may remain uncertain.

`chromatic_dialogue_preview` writes one static 160 × 144 authored projection or a labeled
static multi-page sheet using available project font/UI resources. Its metadata
must identify `provenance: "static-dialogue-preview"`,
`genuineEmulatorFrame: false`, and `runtimeVerified: false`. Validate actual
runtime text placement by rebuilding the real project and observing genuine
`chromatic_emulator_step` samples or an `chromatic_emulator_observe` framebuffer.

## Scene-mode starting points

Existing templates use these identifiers:

- `TOPDOWN`: grid-based overworlds, towns, and RPG exploration.
- `ADVENTURE`: smoother free-movement adventures and related combat layouts.
- `PLATFORM`: side-view jumping, ladders, and platforming behaviors. New projects start with GB Studio's
  defaults: coyote time (`FEAT_PLATFORM_COYOTE_TIME`) and dropping through one-way platforms
  (`FEAT_PLATFORM_DROP_THROUGH`) on.
- `SHMUP`: horizontal or vertical scrolling shooters; the player's starting direction sets which
  ([scene types](scene-types.md#shoot-em-up)).
- `POINTNCLICK`: cursor-driven scenes and object interactions.
- `LOGO`: a still full-screen picture (a splash or logo). Text there draws with glitches, so a title, menu or
  ending with words is another type, such as `TOPDOWN` with the player hidden.

These modes are starting behaviors, not hard genre ceilings. Existing project settings can also disable scene modes or register plugin-defined modes. Inspect the project's actual available types before choosing.

## Preservation checklist

Preserve resource IDs, symbols, `_index`, `_version`, `_release`, `backgroundId`, `spriteSheetId`, collision encodings, palette IDs, prefabs, script event IDs, branch ordering, plugin files, and unknown fields. Keep writes restricted to the active selected project. Generated ROMs and emulator captures must not overwrite authored resources or existing tracked cartridges. Check whether the game editor currently has unsaved edits before claiming filesystem changes are visible in its open UI.
