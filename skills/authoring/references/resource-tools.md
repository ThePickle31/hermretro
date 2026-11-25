# Author native project resources

Use the smallest focused tool that preserves GB Studio's native resource IDs,
unknown fields, event branches, source assets, and neighboring authored files.
[Project authoring](project-authoring.md) has worked examples for each.

## The tools by resource

- `chromatic_scene_create`, `chromatic_scene_update`, `chromatic_scene_inspect`, `chromatic_scene_apply`, and
  `chromatic_scene_delete` manage native scenes and bounded coordinated scene edits.
- `chromatic_actor_create`, `chromatic_actor_update`, `chromatic_actor_inspect`, and `chromatic_actor_delete`, together
  with `chromatic_trigger_create`, `chromatic_trigger_update`, `chromatic_trigger_inspect`, and
  `chromatic_trigger_delete`, preserve resource identities and unrelated scripts.
- `chromatic_script_inspect`, `chromatic_script_edit`, and `chromatic_script_transition` inspect nested visual
  events, make focused event edits, and author typed native scene transitions.
- `chromatic_world_dependencies` traces reusable indexed project relationships without
  assuming a particular genre, game mechanic, or custom event.
- `chromatic_variable_inspect`, `chromatic_variable_set`, and `chromatic_variable_delete` manage authored
  global-variable metadata; they do not map names to hardware addresses or
  mutate running emulator memory. For `chromatic_variable_set`, omit `variableId` to choose the first free
  ID in the editor's default 0–511 range. Explicit IDs may be higher, but must
  be nonnegative decimal strings that JavaScript can represent exactly as safe
  integers, without leading zeros or other formatting. Higher IDs do not appear
  in the stock editor's variable selector. The compiler assigns memory slots
  separately; accepting metadata does not establish compiled-memory fit.
- `chromatic_engine_field_inspect` and `chromatic_engine_field_update` manage engine overrides,
  preserve numeric checkbox values, and accept expected resource revisions.
- `chromatic_collision_inspect` and `chromatic_collision_edit` preserve native hexadecimal
  run-length collision grids and untouched opaque cell values.
- `chromatic_asset_import`, `chromatic_asset_inspect`, `chromatic_asset_update`, and `chromatic_asset_delete` manage
  genuine project-local PNG assets and associated native resource metadata. `chromatic_asset_import`
  takes one asset or several (`assets`) and returns each one's graphics analysis. It also imports
  music (`.uge`, `.mod`) and sound effects (`.wav`, `.vgm`, `.vgz`), and `chromatic_music_compose` writes
  a song from note lists or a bundled track; see [music and sound](music-and-sound.md).
  For replacement background art, `chromatic_asset_update.copyTileColorsFrom` copies an
  existing background's exact palette assignments, including UI cells, into
  empty metadata of the same dimensions. Supply `expectedRevision`; preview
  with `dryRun`. Neither PNG is changed.
- `chromatic_native_graphics_update` applies a complete inert atlas contract to the
  supported private-title renderer without accepting an arbitrary file path or
  C source. See native title atlas for its revision,
  preservation, and dependency-profile limits.
- `chromatic_sprite_inspect`, `chromatic_sprite_edit`, `chromatic_sprite_preview`, and
  `chromatic_sprite_contact_sheet` support animation authoring and static visual review.
- `chromatic_palette_inspect`, `chromatic_palette_create`, `chromatic_palette_update`, `chromatic_palette_assign`, and
  `chromatic_palette_paint` manage native palettes, scene slots, and tile assignments.
  Use direct `chromatic_palette_paint` only on unbound backgrounds. For a bound tilemap,
  use `chromatic_tilemap_inspect` and revisioned `chromatic_tilemap_edit.replace_cells`, preserving
  inspected pixel hashes when only palette assignments change.
- `chromatic_graphics_analyze` and `chromatic_graphics_analyze_scene` inspect hardware and engine
  budgets; `chromatic_graphics_preview_scene` produces a static authored-art projection.
  For an authored overview, `chromatic_graphics_preview_scene` also accepts ordered `sceneIds`
  (1–16 distinct scenes) and `columns` (1–8) instead of `sceneId`. It writes a new
  labeled STATIC / NOT GAMEPLAY sheet. Both forms are enlarged 2x unless integer
  `magnification` (1–4) says otherwise.
- `chromatic_dialogue_analyze`, `chromatic_dialogue_update`, and `chromatic_dialogue_preview` operate on
  native dialogue, the selected project font, and static text-box previews.
- `chromatic_settings_update` patches only requested project settings and rejects an
  unknown selected font before modifying authored resources.

## Relationships

Relationship queries use stable project resource identities:

```text
chromatic_world_dependencies {"node":{"type":"variable","id":"0"},"direction":"incoming","depth":2,"limit":25}
```

Follow the top-level `nextCursor` with `cursor` to page relationships. Coverage
diagnostics have a separate `coverage.pagination.nextCursor`, passed as
`coverageCursor` with the same query. Their pages contain whole limitations and
reviewed custom-event evidence, exact totals and returned counts; `coverage.complete`
always describes aggregate semantic coverage, not whether a page is full. All
responses stay within 32 KiB. A coverage-cursor request prioritizes diagnostics
and may return no relationships when both streams cannot fit together. Advance
each cursor independently; do not treat an empty page as the end of the other
stream. Freshness or query changes invalidate either cursor.

Distinguish executable relationships from conservative structural preservation
edges. Preserve extension-defined event arguments instead of assigning unknown
custom events privileged semantics. Dependency evidence never proves that a
cartridge was compiled or that runtime behavior was observed.

## Batched scene edits

`chromatic_scene_apply` accepts 1–100 ordered operations, an optional `dryRun`, and an
expected project revision. A batch may reference actors or triggers created
earlier in that batch. Distributed native project resources receive deterministic
best-effort rollback on recoverable failures, not instantaneous cross-file
atomicity. Concurrent external rollback conflicts surface as
`TRANSACTION_RECOVERY_CONFLICT` instead of overwriting user changes.

For a long batch, write the operations to a JSON file (a list of operations, or an object whose `operations` is
that list) and pass its path as `operationsPath` instead of `operations`. The file must be inside the game's project
or the profile's scratch folder (`<Hermes home>/cache/scratch`), at most 1 MiB; a relative path is read from the
project folder. hermretro reads it in place of inline `operations`; everything else about the call is the same.
Leave the file unchanged between the `dryRun` call and the one that applies it, so what is applied is what was checked.

## Dialogue, assets and custom events

Dialogue writes preserve requested text and existing page boundaries by
default. With a selected project font, successful writes return at most eight
`fitWarnings` and a compact `dialogueFit` summary. Explicit
`validation: "reject"` fails with `DIALOGUE_OVERFLOW` before writing; text is
rewritten only when `wrap: "word"` or `paginate: true` is explicitly requested.
Setting an unknown `defaultFontId` fails with `FONT_NOT_FOUND` before changing
project settings.

For new assets, choose the actual resource type and sprite profile, preserve
the project's `mono`, `mixed`, or `color` mode, and follow the distinct native
background/sprite source-color and transparency conventions. Never silently
resize, recolor, overwrite, or import a file outside the selected project.

Write game-specific behavior with existing native `EVENT_TEXT` and other
installed commands where appropriate. Preserve opaque project-defined custom
event definitions and arguments. Add an extension only when requested behavior
cannot be expressed cleanly through the existing project.
