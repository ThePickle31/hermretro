# Internal contract: names shared by backend, desktop page and skills

## Identity

- Plugin id: `hermretro`. Display name: `hermretro`.
- Toolset: `chromatic`.
- Where things register (`__init__.register`): the 85 tools, 6 skills, 6 hooks and the `hermretro.guide` prompt
  section only in the profile named `hermretro` (`studio_profile.is_studio`; `HERMRETRO_EVERY_PROFILE=1` for
  plugin development); the page's RPCs in every profile the plugin is on. Checked by `tests/test_registration.py`.
- Tool names: every original engine tool `X` is exposed as `chromatic_X`
  (`project_select` → `chromatic_project_select`, `flash` → `chromatic_flash`). 81 tools, plus four
  plugin-owned tools that are not engine tools (not in the pinned manifest): `chromatic_studio_device_cli`,
  `chromatic_present_game` (shows the built game in the Studio emulator beside the chat; see
  `docs/dev/STUDIO-PAGES.md`), `chromatic_game_info` (the game card, below) and `chromatic_build_report`
  (the Build page's build card, below). 85 in total.
- Skills are loaded as `skill_view("hermretro:<skill>")`:
  `setup`, `game-planning`, `authoring`, `pixel-art`, `rom-debugging`, `deployment`.

## Backend RPC (desktop → Python)

Called with `host.request('plugin.hermretro.<name>', params)`.
A disabled or missing backend answers JSON-RPC error `-32601`.
The page's copy of these names is `desktop-src/core/rpc.js`; the agent tool names it reacts to are in
`desktop-src/core/tools.js`.

### `status` — params `{ chat?: string }`

```json
{
  "ok": true,
  "plugin": { "id": "hermretro", "version": "0.0.4" },
  "platform": { "system": "linux | darwin", "machine": "x64 | arm64", "rosetta": false, "supported": true,
                "qualified": true },
  "node": { "found": true, "version": "26.13.0", "required": "22" },
  "engine": { "present": true, "version": "1.0.34", "verified": true, "detail": "" },
  "hardware_enabled": false,
  "broker": { "running": true },
  "project": null
}
```

`project` is `null` or `{ "root": "/abs/path", "name": "folder", "emulator_active": false, "writer": true }`
for the conversation named by `chat` (the focused chat's id). It is not called `session_id` on purpose: the gateway authorizes that name as a live session and rejects the call (`not_found`) for a draft chat. It never starts a worker.

### `doctor` — params `{ probe?: boolean }`

```json
{
  "ok": true,
  "ready": { "authoring": true, "projectBuild": true, "cBuild": true, "play": true, "desktop": false },
  "components": [
    { "id": "cli", "label": "GB Studio CLI", "status": "ready", "required": "4.3.2",
      "detected": "4.3.2", "optional": false, "detail": "" }
  ],
  "missing_required": [],
  "setup_root": "/abs/path"
}
```

`status` is `ready`, `missing`, `incompatible` or `unknown`. `optional: true` marks the GB Studio
desktop editor. On failure both methods return `{ "ok": false, "error": "message" }` instead of throwing.

## Hardware

Off by default. Setting `hardware_enabled` (plugin settings, `config_schema`) turns the five hardware
tools on: `chromatic_device`, `chromatic_setup`, `chromatic_play`, `chromatic_flash`,
`chromatic_device_capture`. While off they return a denial explaining how to enable them.
Developer Mode activation always stays in the official ModRetro Updater.

### `studio_profile` — no params

Finishes the dedicated `hermretro` profile after the page has created it with Hermes's own
`profiles.create` (parameters come from `status.profile.create`). Returns
`{ ok, profile, plugin, providers[], disabled_toolsets[], soul_written, workspace }` or `{ ok: false, code, error }`
with `code` one of `NOT_CREATED`, `NAME_TAKEN`, `LINK_BLOCKED`, `LINK_FAILED`, `HERMES_COMMAND_FAILED`.
Safe to call again. `status` reports `profile: { name, is_studio, studio: { name, exists, installed, ours },
create? }`.

### `install` — params `{ action: "status" | "start" }`

The page's own toolchain install (first-run onboarding and the Setup page's toolchain step), with no chat.
`start` has the broker run the engine's `toolchain_prepare` for `["build", "emulator"]` in a throwaway worker on
a background thread and returns at once; a second `start` joins the running install. `status` is passive and
never starts the broker. Both return:

```json
{
  "ok": true,
  "manifest": { "items": [{ "id": "gbdk", "component": "gbdk", "name": "GBDK compiler", "version": "4.5.0",
                 "source": "github.com/gbdk-2020/gbdk-2020", "bytes": 6870728, "purpose": "...", "approx": false }],
                "bytes": 708271425, "disk_bytes": 2300000000, "measured_on": "linux-x64", "exact": true },
  "root": "/abs/.hermes/hermretro/.cache/toolchain",
  "install": { "state": "idle | running | done | failed", "started_at": 0, "finished_at": 0, "code": null,
               "error": null, "seeded": false, "fraction": 0.4, "downloaded_bytes": 281000000, "current": "cli",
               "run": { "components": { "gbdk": { "state": "done | running | failed | pending", "status": "prepared",
                        "version": "4.5.0", "reused": false, "error": null,
                        "checks": [{ "file": "gbdk-linux64.tar.gz", "sha256": "...", "reused": false }] } } } }
}
```

`manifest` lists every download (pins from the engine's dependency catalog, sizes measured on `measured_on`).
`run` is read from the engine's own `last-run.json`; `fraction` combines finished components with bytes arriving
in the toolchain's `downloads/` and `cache/` folders. While it runs, a chat's `chromatic_toolchain_prepare` is
refused with `OPERATION_IN_PROGRESS` (and the other way round), and the broker neither retires nor idles out.

### `activity` — params `{ chat?: string, stored?: string, limit?: number }`

Was for the panes beside the chat, which are gone (the Build page shows the agent's work); kept for older
desktop halves and for the broker's own use. `chat` and `stored` are the focused chat's runtime and durable ids; either may
match. Served from the broker's memory: no engine call, never starts the broker or a worker.

```
{ ok, running, matched: "chat" | "recent" | null,
  lane: { project_root, project_name, alive, busy, current_tool, preview_url } | null,
  frame: { t, tool, frame, src /* data URL */ } | null,
  build: { t, ok, seconds, rom, sha256, error } | null,
  events: [{ t, tool, kind, ok, seconds, error? }] }
```

`matched: "recent"` means the chat has no worker and the most recently active one in the profile is shown.

## Studio pages (desktop) and their RPCs

The page at `/hermretro` has one segmented control with five pages: **Home** (hero, Continue,
quick starts, studio status), **Setup** (the step wizard over `status` / `doctor` / `studio_profile`),
**Prompts** (the prompt Reader; prompts go into a chat composer, never sent), **Games** (the library shelf)
and **Emulator** (ModRetro's real player in a `SandboxedFrame`). Full contract, result shapes and the
page ↔ frame messages: `docs/dev/STUDIO-PAGES.md`. All RPCs answer `{ ok: false, error }` on failure
instead of throwing.

| RPC | Params | Result |
|---|---|---|
| `games` | none | `{ ok, games[], demo, device }`: the library (`<hermretro home>/library/games.json`, see `adapter/paths.py`); each game also has `card` (below, or null), `cover` (whether `thumb` is the cover art) and `displayTitle` |
| `game_thumb` | `{ id, png }` | `{ ok }`: stores a title screen for the shelf |
| `player` | `{ id? }` (none or `demo`: the demo cartridge) | `{ ok, url, romSha256, title, demo? }` on the loopback player server |
| `presentations` | `{ since? }` | `{ ok, now, presentations[] }`: what `chromatic_present_game` showed, for a desktop that missed `tool.complete` |
| `captures` | `{ id }` | `{ ok, captures[] }`: screenshots and videos saved from the player |
| `capture_image` | `{ id, png }` | `{ ok, path }`: saves a frame for Ask Hermes / annotate |
| `builds` | `{ game }` | `{ ok, builds[] }` newest first, or `NO_GAME`: the game's build history (below) |
| `build_restore` | `{ game, id }` | `{ ok, restored, backup, changed, removed, problems? }`, or `NO_GAME` / `MISSING` / `TOO_LARGE` |

`chromatic_present_game` `{ note?, project? }` is the agent's way to show a finished game: it needs a fresh
web export (else `BUILD_FIRST`) and a complete game card (else `GAME_INFO_INCOMPLETE` with `missing`,
`problems` and `guidance`), records the presentation and returns `{ ok, studio: { gameId, playerUrl,
title, note, presentedAt } }`; the desktop then opens the emulator in a tab docked right of the chat. Builds
open nothing. Setting `live_player` ("Keep the playable copy current", default on) makes every successful
`rom_build` refresh that web export, so a presentation finds it fresh.

## The build card (`chromatic_build_report`)

The agent calls `chromatic_build_report` once at the end of every turn that changed or built the game
(after `chromatic_rom_build`, its own playtest and `chromatic_present_game`), never in a subagent
(`PARENT_ONLY`). The Build page draws the call as the turn's build card, so the written reply after it stays
one or two sentences. It stores nothing: the page reads the tool call and its result.

```
args   { title (1–48), summary (1–280), changes?: [{ kind: added|changed|removed, text (1–100), asset? }] (≤8),
         tested?: [1–80] (≤6), untested?: [1–80] (≤6), notes?: [1–160] (≤3), suggestions?: [1–40] (≤4), project? }
result { ok: true, report: { title, summary, changes[], tested[], untested[], notes[], suggestions[] },
         project /* root or null */, message, warnings? }
     | { ok: false, code: "INVALID_REPORT", problems[], error }
```

All or nothing: any invalid field (unknown keys included) refuses the whole report. Strings are trimmed and
their whitespace collapsed. `asset` (absolute, or relative to the project) becomes an absolute path inside
the project; one outside it or missing is left out of that change and listed in `warnings`. Without a
resolvable project the report is still accepted (`project: null`) and only absolute assets are kept. Each
kept asset's current version is saved like a delivered image, so the card keeps showing it after a rewrite.

## Build history (snapshots)

After each successful `chromatic_rom_build` (Hermes's `post_tool_call`: result without `error`/`isError`
and `structuredContent.success === true`, not a `sourcePath` build) of a game in the library, the plugin
copies the project to `<plugin data>/snapshots/<game id>/<ms>/files/` with `<ms>/snapshot.json`
`{ at, game, root, files, bytes, reason: "build" | "before-restore", from?, fingerprint, builds: [ms…] }`.
Never copied, compared, deleted or restored: top-level `build/`, `artifacts/`, `.git/`, `node_modules/`,
`captures/`, `save-states/`, temporary files (`*.part`, `*.tmp`, …) and every symlink. A project over 64 MB
or 20 000 files is skipped. When the files are identical to the newest snapshot (path + size + SHA-256 of
each), no copy is made and the build's time is appended to that snapshot's `builds`. The newest 30 are kept.

- `builds { game }` → `{ ok, builds: [{ id, at, builds, files, bytes, reason, from? }] }`, newest first.
- `build_restore { game, id }` first keeps the current files as a `before-restore` snapshot (`from` = the
  restored id; reused when identical to the newest), then deletes project files the snapshot lacks and
  writes back every file that differs (temp sibling + rename; never through a link). Restored files get a
  new modification time, so the game counts as changed and needs a rebuild, which records a new build.

## The game card (`game.json` + `cover.png`)

Every game has a card at its project root, next to the `.gbsproj`: `game.json` and `cover.png`. A starter
`game.json` (title only) is written when a project is created, and by `chromatic_game_info` or
`chromatic_present_game` when missing. Neither file counts as game source, so writing them never marks a
built game as changed. Unknown keys are kept (later fields need no migration).

```
{ version: 1, title, tagline, description, about, genres: [..], tags: [..], controls: { button: action },
  cover: "cover.png", coverSha256, coverForBuild /* ROM sha when the cover was set */, createdAt, updatedAt }
```

- **Required to present:** title (1–60), tagline (8–90), description (40–400), 1–3 genres from `Action,
  Adventure, Arcade, Exploration, Platformer, Puzzle, Racing, Role-playing, Rhythm, Shooter, Simulation,
  Sports, Strategy, Story, Other`, and a cover. Placeholder words (TODO, TBD, lorem ipsum, …) do not count.
  Optional: about (≤4000), tags (≤12, ≤24 chars), controls (≤12).
- **Cover:** a PNG, exactly 160×144, every pixel opaque, 3–32 colours (pixel art, drawn natively, never
  Image Generation), not an unchanged copy of an image under `assets/`. Read by `adapter/game_card.py`
  with the standard library (8-bit and palette PNGs, not interlaced).
- `chromatic_game_info` `{ title?, tagline?, description?, about?, genres?, tags?, controls?, cover?,
  project? }`: with no fields it reports the card; otherwise it checks every field and stores all or
  nothing (`INVALID_GAME_INFO` with `problems`), copying `cover` into the project. Answers `{ ok, card,
  file, complete, missing, problems, nextStep }`.
- `games[].card` = `{ title, tagline, description, about, genres, tags, controls, complete, missing,
  hasCover, coverForBuild }`; with a valid cover, `thumb` is the cover (else the captured title screen).
