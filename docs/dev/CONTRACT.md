# Internal contract: names shared by backend, desktop page and skills

## Identity

- Plugin id: `hermretro`. Display name: `hermretro`.
- Toolset: `chromatic`.
- Where things register (`__init__.register`): the 85 tools, 6 skills, 6 hooks and the `hermretro.guide` prompt
  section only in the profile named `hermretro` (`studio_profile.is_studio`; `HERMRETRO_EVERY_PROFILE=1` for
  plugin development); the page's RPCs in every profile the plugin is on. Checked by `tests/backend/hermes/test_registration.py`;
  every registration, in order, is pinned in `tests/repo/registration.json`.
- Who declares what: each backend feature, in its own folder (`backend/<feature>/rpcs.py`, `tools.py`,
  `hooks.py`; the table in `ARCHITECTURE.md`, "The agent half"). Adding an RPC: `@rpc("name")` in the feature's
  `rpcs.py` and a section below; `node tools/bundle/bundle.mjs` regenerates the page's name list. Adding a plugin tool: a `Tool(...)` in the
  feature's `tools.py` (with its Build-page step words), `plugin.yaml` `provides_tools`, the page's
  `step-words.js` and a line here. Then refresh the snapshot: `python tests/repo/test_registration_snapshot.py --write`.

## Events between backend features

Declared by the owning feature in its front door (`EVENTS`), emitted only by it, heard in other features'
`listeners.py` (`backend/system/events.py`; a failing listener is logged and never breaks the emitter).

| Event | Payload | Emitted when | Heard by |
|---|---|---|---|
| `library.build_reported` | `game` (library id, str; `null` without a project), `assets` (absolute image paths, list of str) | `chromatic_build_report` accepted a build card | assets (keeps the shown images) |
| `library.game_presented` | `game` (library id, str), `root` (project folder, str) | `chromatic_present_game` showed a game | — |
| `setup.tools_removed` | `root` (the emptied download folder, str) | `remove_tools` emptied the download folder | — |
| `setup.studio_profile_ready` | `profile` (profile name, str) | `studio_profile` finished the profile | — |
| `assets.image_restored` | `path` (the image's absolute path, str) | `asset_restore` put a kept version back | — |
| `history.build_kept` | `game` (library id, str), `root` (the real project folder, `pathlib.Path`) | a successful build was kept as a snapshot | — |
- Tool names: every original engine tool `X` is exposed as `chromatic_X`
  (`project_select` → `chromatic_project_select`, `flash` → `chromatic_flash`). 81 tools, plus four
  plugin-owned tools that are not engine tools (not in the pinned manifest): `chromatic_studio_device_cli`,
  `chromatic_present_game` (shows the built game in the Studio emulator beside the chat; see
  `docs/dev/STUDIO-PAGES.md`), `chromatic_game_info` (the game card, below) and `chromatic_build_report`
  (the Build page's build card, below). 85 in total.
- Skills are loaded as `skill_view("hermretro:<skill>")`:
  `setup`, `game-planning`, `authoring`, `pixel-art`, `rom-debugging`, `deployment`.

## Backend RPC (desktop → Python)

Called with `host.request('plugin.hermretro.<name>', params)`. RPC names are global and flat: one namespace,
`plugin.hermretro.<name>`, for every feature, with no feature or page prefix and no dots in `<name>` (`builds`,
not `history.builds`). One name is declared once across all features: the page-name generator
(`tools/bundle/rpc_names.py`) and `tests/backend/hermes/test_declare.py` fail on a second, and `python tools/retrodev
new rpc <feature> <name>` refuses a taken one.
A disabled or missing backend answers JSON-RPC error `-32601`.
Which profile the page asks is chosen by what the handler reads, not by its feature: one reading the Build
conversations or the plugin data folder (`host._data_dir()`, one per profile: history snapshots, asset versions) is
called with `callStudioOnly` (the hermretro profile only: `build`, `builds`, `build_restore`, `asset`, `asset_info`,
`asset_restore`, `assets`); the others with `callStudio` or `callBackend` (`page/app/backend.js`).
The page's copy of these names, `RPC_<NAME>` from `page/app/rpc.js`, is generated from the `@rpc` declarations into
`page/app/rpc-names.js` by `tools/bundle/rpc_names.py` (`node tools/bundle/bundle.mjs` runs it; the bundle check
fails when it is stale); the agent tool names it reacts to are in
`page/app/tools.js`.

### `status` — params `{ chat?: string }`

```json
{
  "ok": true,
  "plugin": { "id": "hermretro", "version": "<plugin.yaml version>",
              "installed_in": { "profile": "default", "linked": false } },
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
for the conversation named by `chat` (the focused chat's id). `plugin.installed_in` names the profile Hermes installed
this copy into (the studio profile only links it), where the page runs Hermes's `plugins.manage update`; it is
`{ "profile": null, "linked": true }` for a checkout linked in from elsewhere, which Hermes does not update. It is not called `session_id` on purpose: the gateway authorizes that name as a live session and rejects the call (`not_found`) for a draft chat. It never starts a worker.

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
The engine's `device` tool (`engine/modretro-chromatic/dist/chromatic.js`, `ChromaticService`): `status` answers at
once without touching USB (`{success, sessionId, platform, arch, backend: {supported, target | reason}, drivers,
acceptingOperations, operations, ...}`); `list_devices` starts a scan and answers `{operationId, state: "running", ...}`;
`operation_status` with that `operationId` answers, once `state` is `succeeded`, a `result` of `{devices: [{player,
location, ..., deviceToken, expiresAt}], conflicts, unmatched, diagnostics, selection, identityScope}`.
A page read that needs the engine is a broker control op (`backend/broker/control.py`) running
`engine = self.new_engine("<name>")`, `engine.call_tool(...)`, `engine.close()`, as `doctor` does, called from an
RPC through `host.ensure_broker()`; `doctor` reads no hardware, so a device read must also refuse unless the RPC's
`ctx.get_config("hardware_enabled")` is on (the gate `Broker.call` applies to the hardware tools).

### `studio_profile` — no params

Finishes the dedicated `hermretro` profile after the page has created it with Hermes's own
`profiles.create` (parameters come from `status.profile.create`). Returns
`{ ok, profile, plugin, providers[], disabled_toolsets[], soul_written, workspace }` or `{ ok: false, code, error }`
with `code` one of `NOT_CREATED`, `NAME_TAKEN`, `LINK_BLOCKED`, `LINK_FAILED`, `HERMES_COMMAND_FAILED`.
Safe to call again, and single-flight: a call made while another runs in the same process waits for it and gets its
answer (`shared: true`) or its error. `status` reports `profile: { name, is_studio, studio: { name, exists,
installed, ours, conflict }, create? }`; `conflict` is a `hermretro` profile someone else made (finishing it is
refused with `NAME_TAKEN`), so the page names it before any download.

### `install` — params `{ action: "status" | "start" | "cancel" }`

The page's own toolchain install (first-run onboarding and the Setup page's toolchain step), with no chat.
`start` has the broker run the engine's `toolchain_prepare` for `["build", "emulator"]` in a throwaway worker on
a background thread and returns at once; a second `start` joins the running install, and `start` is refused with
`NO_SPACE` when the disk cannot hold it. `cancel` asks the engine to stop through MCP's own `notifications/cancelled`
(never a kill); the install keeps `state: "running"` with `cancelling: true` until the engine has released its setup
lock, then reports `cancelled` (or `failed` with `SETUP_LOCK_KEPT` when the engine kept its lock, which is never
removed). `status` and `cancel` are passive and never start the broker; with no broker running, `status` reports the
last install from its journal (`<deps root>/page-install.json`), a `running` one as `interrupted`. All return:

```json
{
  "ok": true,
  "manifest": { "items": [{ "id": "gbdk", "component": "gbdk", "name": "GBDK compiler", "version": "4.5.0",
                 "source": "github.com/gbdk-2020/gbdk-2020", "bytes": 6870728, "purpose": "...", "approx": false }],
                "bytes": 708271425, "disk_bytes": 2300000000, "measured_on": "linux-x64", "exact": true },
  "root": "/abs/.hermes/hermretro/.cache/toolchain",
  "space": { "free_bytes": 50000000000, "needed_bytes": 2300000000, "enough": true },
  "install": { "state": "idle | running | done | failed | cancelled | interrupted", "started_at": 0, "finished_at": 0,
               "code": null, "error": null, "hint": null, "seeded": false, "fraction": 0.4,
               "downloaded_bytes": 281000000, "current": "cli", "elapsed_seconds": 151, "quiet_seconds": 12,
               "cancelling": false, "elsewhere": false,
               "run": { "components": { "gbdk": { "state": "done | running | failed | pending", "status": "prepared",
                        "version": "4.5.0", "reused": false, "error": null,
                        "checks": [{ "file": "gbdk-linux64.tar.gz", "sha256": "...", "reused": false }] } } } }
}
```

`manifest` lists every download (pins from the engine's dependency catalog, sizes measured on `measured_on`).
`run` is read from the engine's own `last-run.json`; `fraction` combines finished components with bytes arriving
in the toolchain's `downloads/` and `cache/` folders. While it runs, a chat's `chromatic_toolchain_prepare` is
refused with `OPERATION_IN_PROGRESS` (and the other way round; `elsewhere` is true while a chat holds that lock), and
the broker neither retires nor idles out. `code` names a known cause (`NETWORK`, `NO_SPACE`, `SETUP_LOCKED`,
`SETUP_LOCK_KEPT`, `STALLED`, `CANCELLED`, `INTERRUPTED`, or the engine's stage) and `hint` its next step. The install
is stopped (`STALLED`, through the same cancellation) only after 30 minutes with no change in the toolchain folder or
the worker's output, not because bytes stopped growing; `quiet_seconds` is how long that has been.

### `remove_tools` — no params

Setup's "Remove downloaded tools": empties `<hermretro home>/.cache` (toolchain, prepared engine, ModRetro's CLI
and their receipts; only its lock file stays); games and the library stay, and links inside are removed, never
followed. Asks a running broker to stop, then holds the broker's election lock for the whole removal (no broker
can start meanwhile). Returns `{ ok, removed_bytes, left_bytes, root }` or `{ ok: false, code, error }` with `code`
`BUSY` (a game's chat has a live worker, an install runs, or the broker did not stop within 15 s),
`CUSTOM_LOCATION` (`HERMRETRO_DEPS_ROOT` / `GB_STUDIO_SETUP_ROOT` set), `UNEXPECTED_LOCATION` or `PARTLY_REMOVED`
(some files could not be deleted; a retry finishes them). Setup can then install again.

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

The page at `/hermretro` has one segmented control over its pages (`PAGES` in `page/pages/index.js`): **Build** (one game,
one conversation; the page opens here), **Setup** (the step wizard over `status` / `doctor` / `studio_profile`),
**Prompts** (the prompt Reader; prompts go into a chat composer, never sent), **Games** (the library shelf)
and **Emulator** (ModRetro's real player in a `SandboxedFrame`). Full contract, result shapes and the
page ↔ frame messages: `docs/dev/STUDIO-PAGES.md`. All RPCs answer `{ ok: false, error }` on failure
instead of throwing.

| RPC | Params | Result |
|---|---|---|
| `games` | none | `{ ok, games[], pending[], demo, device, gamesDir }`: the library (`<hermretro home>/library/games.json`, see `backend/system/paths.py`). Each game (`Registry.describe` in `backend/library/games.py`): `id, title, projectRoot, kind, state, rom: { path, sha256, size, builtAt } \| null, webExport, web: { sha256, builtAt } \| null, thumb, cover` (whether `thumb` is the cover art), `card` (below, or null), `displayTitle, chat, session, error`; what each means: `docs/dev/STUDIO-PAGES.md`, "`games` → library". Read a game's ROM, web export or state from here rather than adding a per-game RPC |
| `game_thumb` | `{ id, png }` | `{ ok }`: stores a title screen for the shelf |
| `player` | `{ id? }` (none or `demo`: the demo cartridge) | `{ ok, url, romSha256, title, demo? }` on the loopback player server |
| `presentations` | `{ since? }` | `{ ok, now, presentations[] }`: what `chromatic_present_game` showed, for a desktop that missed `tool.complete` |
| `captures` | `{ id }` | `{ ok, captures[] }`: screenshots and videos saved from the player |
| `capture_image` | `{ id, png }` | `{ ok, path }`: saves a frame for Ask Hermes / annotate |
| `builds` | `{ game }` | `{ ok, builds[] }` newest first, or `NO_GAME`: the game's build history (below) |
| `build_restore` | `{ game, id }` | `{ ok, restored, backup, changed, removed, problems? }`, or `NO_GAME` / `MISSING` / `TOO_LARGE` |

`captures` reads `<project>/captures/` (the player's screenshots and videos; `backend/library/README.md`, "Captures").
Save states are the engine's: `<project>/save-states/<build digest>/<sha256>.gbstate.json`, written by its web preview
(`engine/modretro-chromatic/dist/web-preview-states.js`), at most 8 kept per build; no RPC reads them
(`backend/library/README.md`, "Save states", has the fields).

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
  Optional: about (≤4000), tags (≤12, ≤24 chars), controls (≤12, button ≤20 chars, action ≤60 chars).
  `game.json` is at most 64 KB.
- **Cover:** a PNG of at most 512 KB, exactly 160×144, every pixel opaque, 3–32 colours (pixel art, drawn natively, never
  Image Generation), not an unchanged copy of an image under `assets/`. Read by `backend/library/game_cover.py`
  with the standard library (8-bit and palette PNGs, not interlaced).
- `chromatic_game_info` `{ title?, tagline?, description?, about?, genres?, tags?, controls?, cover?,
  project? }`: with no fields it reports the card; otherwise it checks every field and stores all or
  nothing (`INVALID_GAME_INFO` with `problems`), copying `cover` into the project. Answers `{ ok, card,
  file, complete, missing, problems, nextStep }`.
- `games[].card` = `{ title, tagline, description, about, genres, tags, controls, complete, missing,
  hasCover, coverForBuild }`; with a valid cover, `thumb` is the cover (else the captured title screen).

## The game object

One entry of the `games` RPC's `games[]` (`Registry.describe` in `backend/library/games.py`, then `rpc_games` in
`backend/library/rpcs.py`, which reshapes `chat` and `session` and drops `updatedAt`):

| Field | What it holds |
|---|---|
| id, title, displayTitle | The game's id, its project's title, and the card's title when set (else `title`) |
| projectRoot, kind | The project folder; `gbstudio` (it has a `.gbsproj`) or `gbdk` |
| state, error | `ready`, `changed` (sources newer than the ROM), `unbuilt` or `failed`; `error` only when `failed` |
| rom | `{ path, sha256, size, builtAt }` of the last build's ROM (else the web export's, else the newest in `build/`), or null |
| webExport, web | Whether a web export exists; its ROM `{ sha256, builtAt }`, or null |
| thumb, cover | A data URL for the shelf (the cover, else the captured title screen, else null); whether it is the cover |
| card | `game_card.public()` (`backend/library/game_card.py`), or null without `game.json`: `title`, `tagline`, `description`, `about` (text or null), `genres`, `tags` (lists of text), `controls` (`{ button: what it does }`, `{}` when none), `complete`, `missing` (the fields still needed to present), `hasCover`, `coverForBuild` (the ROM sha the cover was set for, or null) |
| chat | `{ sessionId, title, conversationId, profile, thisProfile }` of the chat working on it (the last to select it), or null |
| session | The Build conversation bound to it: `{ storedId, createdAt, thisProfile, profileName, exists }`, or null |

The Build page's rail gets the same objects (`shell.gameList`, `page/app/studio-page.js`), with `title` replaced by
`displayTitle`, `session` null once the page released it, and `buildSession` (the bound stored session id) added
(`build-page.js`).
