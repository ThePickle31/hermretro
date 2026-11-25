# Internal contract: names shared by backend, desktop page and skills

## Identity

- Plugin id: `hermretro`. Display name: `hermretro`.
- Toolset: `chromatic`.
- Where things register (`__init__.register`): the tools, skills, hooks and the `hermretro.guide` prompt
  section only in the profile named `hermretro` (`studio_profile.is_studio`; `HERMRETRO_EVERY_PROFILE=1` for
  plugin development); the page's RPCs in every profile the plugin is on. Registering in the `hermretro` profile also
  replaces a `SOUL.md` an earlier release shipped (`studio_profile.refresh_soul`: its hash is in `OLDER_SOULS`; an
  edited one or a link is kept). Fresh creation seeds `agent.max_turns` to 1000 and installs the studio SOUL
  before publishing the profile. Repair keeps any existing turn limit, including a cleared one, and any custom
  or missing SOUL. Checked by `tests/backend/setup/test_studio_profile.py` and
  `tests/backend/hermes/test_registration.py`.
- Who declares what: each backend feature, in its own folder (`backend/<feature>/rpcs.py`, `tools.py`,
  `hooks.py`; the table in `.agents/skills/hermretro-dev-architecture/references/architecture.md`, "The agent half"). Adding an RPC: `@rpc("name")` in the feature's
  `rpcs.py` and a section below; `node tools/bundle/bundle.mjs` regenerates the page's name list. Adding a plugin tool: a `Tool(...)` in the
  feature's `tools.py` (with its Build-page step words), `plugin.yaml` `provides_tools`, the page's
  `step-words.js` and a line here.

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
  (`project_select` → `chromatic_project_select`, `flash` → `chromatic_flash`). Besides them, the
  plugin-owned tools that are not engine tools (not in the pinned manifest): `chromatic_studio_device_cli`,
  `chromatic_present_game` (shows the built game in the Studio emulator beside the chat; see
  `.agents/skills/hermretro-dev-page/references/player.md`), `chromatic_game_info` (the game card, below) and `chromatic_build_report`
  (the Build page's build card, below).
- Skills are loaded as `skill_view("hermretro:<skill>")`:
  `setup`, `game-planning`, `authoring`, `pixel-art`, `rom-debugging`, `deployment`.

## Backend RPC (desktop → Python)

Called with `host.request('plugin.hermretro.<name>', params)`. RPC names are global and flat: one namespace,
`plugin.hermretro.<name>`, for every feature, with no feature or page prefix and no dots in `<name>` (`builds`,
not `history.builds`). One name is declared once across all features: the page-name generator
(`tools/bundle/rpc_names.py`) and `tests/backend/hermes/test_declare.py` fail on a second.
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
for the conversation named by `chat` (the focused chat's id). When the handshake cannot be confirmed,
`broker.running` is `null`. `plugin.installed_in` names the profile Hermes installed
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

### `studio_profile` — params `{ create? }`

Finishes an existing `hermretro` profile, or with `create: true` prepares a new one and publishes it after its
initial preferences and finish marker have been written. If a deleted profile left a directory with no identity
and no gateway owner, creation keeps that directory under a hidden sibling in `profiles/` and publishes the new
profile under the studio name. Returns
`{ ok, profile, plugin, providers[], provider_sync, disabled_toolsets[], soul_written, workspace }` or
`{ ok: false, code, error }` with `code` one of `NOT_CREATED`, `NAME_TAKEN`, `LINK_BLOCKED`, `LINK_FAILED`,
`HERMES_COMMAND_FAILED`. A model-provider plugin Hermes installed into the studio profile on its own is removed and
linked to the installing profile's copy, keeping the studio's settings for it. `provider_sync` is
`{ changed[], kept[], claude_login }` (`backend/setup/provider_sync.py`): the units copied from the installing profile
and those kept because they were changed in the studio profile itself, by name only, never a value. Units: the
sections `model`, `providers`, `custom_providers`, `fallback_providers` whole; the route fields of `delegation` and of
each `auxiliary.<task>`; each provider plugin setting; `env:<NAME>` for the providers' .env keys and any key a copied
unit names (`${NAME}`, `key_env`); `claude_config_dir`. A unit the studio still holds as last copied follows the
installing profile, removals included. `status` runs the same sync in the background (linking and turning on a
provider plugin turned on since) whenever the installing profile's config or .env changed since the last one, only
for the profile that made the studio profile.
Safe to call again, and single-flight: a call made while another runs in the same process waits for it and gets its
answer (`shared: true`) or its error. `status` reports `profile: { name, is_studio, studio: { name, exists,
installed, ours, conflict, claude_login } }`; `conflict` is a `hermretro` profile someone else made (finishing it is
refused with `NAME_TAKEN`), so the page names it before any download. `claude_login` is null unless the finished
studio profile uses the Claude Subscription DirectSDK provider, then `{ provider, signed_in, via }` with `via` one of
`token` (`CLAUDE_CODE_OAUTH_TOKEN` in its .env), `folder` (its `claude_config_dir`) or null (none: the page offers
`studio_claude_sign_in`). `signed_in` is Claude Code's own answer (`claude auth status`, asked at most once a minute
per login). While it is false the Setup wizard keeps the profile step open.

### `studio_claude_sign_in` — no params

Gives the studio profile a Claude login of its own: Claude Code's browser sign-in (`claude auth login --claudeai`)
into `<studio profile>/claude`, then selects that folder as its `claude_config_dir`. Needed on macOS when the
installing profile uses Claude Code's default login, whose Keychain entry a second profile cannot reach
(`backend/setup/claude_login.py`). Waits up to ten minutes for the browser. Returns `{ ok, claude_login }` or
`{ ok: false, code, error }` with `code` one of `NOT_CREATED`, `CLAUDE_NOT_FOUND`, `SIGN_IN_TIMEOUT`, `SIGN_IN_FAILED`.

### `install` — params `{ action, admission?, run_id?, retire_legacy? }`

The page's own toolchain install (first-run onboarding and the Setup page's toolchain step), with no chat.
`start_admitted` has the broker run the engine's `toolchain_prepare` for `["build", "emulator"]` in a throwaway worker on
a background thread and returns the admitted run. Another start joins the running install. Start is refused with
`NO_SPACE` when the disk cannot hold even the estimate, or `WORKER_STILL_RUNNING` while an earlier installer worker's
exit is unconfirmed. Each run has a `run_id`; `cancel` acts only on the running install with that `run_id` (any
other, such as a stale Cancel for a run that finished while a retry runs, returns the status and stops nothing).
Cancelling takes three steps: the broker sends the engine MCP's own `notifications/cancelled` for the
`toolchain_prepare` request; it waits up to 120 s for the engine to release its setup lock (the install keeps
`state: "running"` with `cancelling: true` meanwhile); then it closes the worker, and that close falls back to
SIGTERM and then SIGKILL for the worker's process group when the worker does not exit on its own. The result is
`cancelled`, or `failed` with `SETUP_LOCK_KEPT` when this run's engine kept its lock (never removed by hermretro), or
`WORKER_STILL_RUNNING` when even the close could not confirm the worker exited: then the user quits and reopens
Hermes before trying again. While the worker is still alive, status reports `install.worker_left: true` even in a
terminal state. The page blocks Start, Update and Reload, the broker stays up, and a chat's
`chromatic_toolchain_prepare` and `remove_tools` are refused. For a retained broker without the liveness field,
the gateway checks the journal's recorded worker group. A retained v0.0.9 broker can report a running install
without a `run_id`; the gateway marks the result `legacy_progress: true` so the page shows progress with the busy
guards in place. A broker from before cancel answers `cancel` with `CANCEL_UNSUPPORTED` (`ok: false`; its install
goes on). `status` and `cancel` never start the broker.
With no broker running, `status` reports the last install from its journal
(`<deps root>/page-install.json`), a `running` one as `interrupted`. An unanswered broker request returns
`UNAVAILABLE`. `prepare_start` returns `{ ok: true, admission: { boot_id, deadline } }`. The deadline is on the
gateway host's monotonic clock and the boot UUID stays stable across gateway restarts. The page saves both values
before submitting `start_admitted`. The gateway echoes `admission` in the Start
reply and bounds both startup and the broker request by the admission. The broker checks expiry under the install
lock before admitting the run. After a lost acknowledgement or page remount, the page includes the saved
admission in status requests. A confirmed status can echo `expired_admission` when the grant was already unusable
before the status read, including after reboot. An older numeric grant can be reconciled by status and can hold
the page for at most the 60-second admission window. Start requires a boot-bound grant. The page requires a
fresh idle result before changing the plugin. A known legacy handshake failure
returns `BROKER_LEGACY`. An explicit Update or Reload can request `retire_legacy: true` to use the broker's
ordinary shutdown guard and wait for its exit. A busy reply prevents the action.

Older pages can still use `start` or `start_fenced` with its Unix-millisecond `expires_at` and
`start_expires_at` reply. Older brokers can still answer status and cancel. Starts require the broker to
advertise the matching deadline support. Status and cancel return:

```json
{
  "ok": true,
  "manifest": { "items": [{ "id": "gbdk", "component": "gbdk", "name": "GBDK compiler", "version": "4.5.0",
                 "source": "github.com/gbdk-2020/gbdk-2020", "bytes": 6870728, "purpose": "...", "approx": false }],
                "bytes": 708271425, "disk_bytes": 2300000000, "measured_on": "linux-x64", "exact": true },
  "root": "/abs/.hermes/hermretro/.cache/toolchain",
  "space": { "free_bytes": 50000000000, "needed_bytes": 2300000000, "enough": true, "estimate": "fresh | reuse | unknown",
             "warning": null },
  "install": { "state": "idle | running | done | failed | cancelled | interrupted", "run_id": "9f2c…", "started_at": 0, "finished_at": 0,
               "code": null, "error": null, "hint": null, "seeded": false, "fraction": 0.4,
               "downloaded_bytes": 281000000, "current": "cli", "elapsed_seconds": 151, "quiet_seconds": 12,
               "cancelling": false, "elsewhere": false, "worker_left": false,
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
`SETUP_LOCK_KEPT`, `WORKER_STILL_RUNNING`, `STALLED`, `CANCELLED`, `INTERRUPTED`, or the engine's stage) and `hint` its
next step, read from the engine's structured result (its error codes such as `DOWNLOAD_FAILED`, `ENOSPC`, and the
tails of captured command output) before the message is shortened. `SETUP_LOCKED` is a lock this run never took (the
engine's plan reported it, or another setup took it first): its hint says to check that the owner recorded in the
lock's `owner.json` has stopped before moving it aside. `space.needed_bytes` is the full install unless the folder
holds a ready component receipt or cached downloads; then it is a lower estimate, and `warning` says the fit is
uncertain while less than the full size is free. The install
is stopped (`STALLED`, through the same cancellation) only after 30 minutes with no change in the toolchain folder or
the worker's output, not because bytes stopped growing; `quiet_seconds` is how long that has been.

### `remove_tools` — no params

Setup's "Remove downloaded tools": empties `<hermretro home>/.cache` (toolchain, prepared engine, ModRetro's CLI
and their receipts; only its lock file stays); games and the library stay, and links inside are removed, never
followed. Asks a running broker to stop, then holds the broker's election lock for the whole removal (no broker
can start meanwhile). Returns `{ ok, removed_bytes, left_bytes, root }` or `{ ok: false, code, error }` with `code`
`BUSY` (a game's chat has a live worker, an install runs, or the broker did not stop within 15 s),
`UNAVAILABLE` (the handshake or shutdown could not be confirmed),
`CUSTOM_LOCATION` (`HERMRETRO_DEPS_ROOT` / `GB_STUDIO_SETUP_ROOT` set), `UNEXPECTED_LOCATION` or `PARTLY_REMOVED`
(some files could not be deleted; a retry finishes them). Setup can then install again.

### `activity` — params `{ chat?: string, stored?: string, limit?: number }`

Was for the panes beside the chat, which are gone (the Build page shows the agent's work); kept for older
desktop halves and for the broker's own use. `chat` and `stored` are the focused chat's runtime and durable ids; either may
match. Served from the broker's memory: no engine call, never starts the broker or a worker.

```
{ ok, running, matched: "chat" | null,
  lane: { project_root, project_name, alive, busy, current_tool, preview_url } | null,
  frame: { t, tool, frame, src /* data URL */ } | null,
  build: { t, ok, seconds, rom, sha256, error } | null,
  events: [{ t, tool, kind, ok, seconds, error? }] }
```

`matched: null` means the chat has no worker; another chat's is never shown.

## Studio pages (desktop) and their RPCs

The page at `/hermretro` has one segmented control over its pages (`PAGES` in `page/pages/index.js`): **Build** (one game,
one conversation; the page opens here), **Setup** (the step wizard over `status` / `doctor` / `studio_profile`),
**Games** (the library shelf, with New game opening the form on Build)
and **Emulator** (ModRetro's real player in a `SandboxedFrame`). Full contract, result shapes and the
page ↔ frame messages: `.agents/skills/hermretro-dev-page/` (its references). All RPCs answer `{ ok: false, error }` on failure
instead of throwing.

| RPC | Params | Result |
|---|---|---|
| `games` | none | `{ ok, games[], unavailable[], pending[], demo, device, gamesDir }`: the library (`<hermretro home>/library/games.json`, see `backend/system/paths.py`). Each game (`describe` in `backend/library/shelf.py`): `id, title, projectRoot, kind, state, rom: { path, sha256, size, builtAt } \| null, webExport, web: { sha256, builtAt } \| null, thumb, cover` (whether `thumb` is the cover art), `card` (below, or null), `layout: { ok, problems[], warnings[] }` (the game folder's layout, `backend/library/layout.py`), `displayTitle, chat, session, error`; what each means: `.agents/skills/hermretro-dev-page/references/player.md`, "`games` → library". |
| `game_build_status` | `{ id }` | `{ ok, game: { id, title, projectRoot, rom, webExport, web, chat, session }, device: { hardwareEnabled } }`: one game's artifacts and chat routing, with the same field shapes as `games` (chat title is null). `INVALID` for an invalid id, `NO_GAME` for an absent entry or project folder, `UNAVAILABLE` for a read failure. |
| `game_thumb` | `{ id, png }` | `{ ok }`: stores the first title screen for the shelf and preserves any existing thumbnail |
| `player` | `{ id? }` (none or `demo`: the demo cartridge) | `{ ok, url, romSha256, title, demo?, skins, skin }` on the loopback player server (`skins`: `{ id, name, swatch }` of each device skin; `skin`: the default) |
| `presentations` | `{ since?, cursorOnly? }` | `{ ok, now, presentations[] }`. Each record has `{ gameId, title, t, note, sessionId, conversationId, profile, thisProfile, buildConversation }`. With `cursorOnly: true`, returns the backend time and an empty list without reading the library. |
| `captures` | `{ id }` | `{ ok, captures[] }`: screenshots and videos saved from the player |
| `capture_image` | `{ id, png }` | `{ ok, path }`: saves a frame for Ask Hermes / annotate |
| `builds` | `{ game, stored? }` | `{ ok, builds[] }` newest first, or `NO_GAME`: the game's build history (below) |
| `build_restore` | `{ game, id, buildRef?, buildAt? }` | `{ ok: true, restored, backup, changed, removed }`. `PARTIAL` returns `ok: false`, the same IDs and counts, and `problems`. Preflight errors are `NO_GAME`, `MISSING`, `INVALID_SNAPSHOT`, `TOO_LARGE` and `BACKUP_FAILED`. |

`games` can include an empty `games` array in an error reply. Only `ok: true` supplies shelf and ownership data.
`unavailable` lists the registered game IDs the shelf could not read.
Each public pending record has `storedId`, `name` (up to 120 characters or null), `createdAt`
(finite seconds or null), and `exists`.
The `build` start reply includes `pending.storedId`, `pending.name`, and the registry's `pending.createdAt` before Desktop sends the first message.
`game_build_status` also returns `UNAVAILABLE` if an existing web export's ROM cannot be read.

`captures` reads `<project>/captures/` (the player's screenshots and videos; `backend/library/README.md`, "Captures").
Save states are the engine's: `<project>/save-states/<build digest>/<sha256>.gbstate.json`, written by its web preview
(`engine/modretro-chromatic/dist/web-preview-states.js`), at most 8 kept per build; no RPC reads them
(`backend/library/README.md`, "Save states", has the fields).

`chromatic_present_game` `{ note?, project? }` is the agent's way to show a finished game: it needs a fresh
web export the engine made of the current sources (else `BUILD_FIRST`) and a complete game card (else
`GAME_INFO_INCOMPLETE` with `missing`, `problems` and `nextStep`; before the card, a game folder out of its layout gets
`LAYOUT` with `nextStep`: `layout.check`'s problems, `backend/library/README.md`, "The game folder"), records the presentation and returns `{ ok, studio: { gameId, playerUrl,
title, note, presentedAt, buildConversation } }` (`buildConversation`: the game's own Build conversation presented
it, so the Build page plays it); otherwise the desktop opens the emulator in a tab docked right of the chat. Builds
open nothing. Setting `live_player` ("Keep the playable copy current", default on) makes every successful
`rom_build` refresh that web export, so a presentation finds it fresh.

Every plugin tool's failure is `{ ok: false, error, code, nextStep? }` (`tool_error(message, code, next_step)`):
`nextStep` says what the agent does about it, and `ADAPTER_ERROR` always has one. `chromatic_game_info`,
`chromatic_present_game` and `chromatic_build_report` act on the chat's own game: in a game's Build conversation a
`project` naming another folder is refused with `ONE_GAME_PER_CONVERSATION` (in a New Game conversation, one naming
an existing game with `NEW_GAME_ONLY`), and a game with a Build conversation
keeps it as its `chat` link whatever other chat touches it. An engine tool the broker cannot run answers
`UNAVAILABLE` with a `nextStep`; when another copy of the plugin's broker still runs games, it says whether one is
this chat's own (the plugin folder changed under it) or other chats'.

## The build card (`chromatic_build_report`)

The agent calls `chromatic_build_report` once at the end of every turn that changed or built the game
(after `chromatic_rom_build`, its own playtest and `chromatic_present_game`), never in a subagent
(`PARENT_ONLY`). The Build page draws the call as the turn's build card, so the written reply after it stays
one or two sentences. It stores nothing: the page reads the tool call and its result.

```
args   { title (1–48), summary (1–280), changes?: [{ kind: added|changed|removed, text (1–100), asset? }] (≤8),
         tested?: [1–80] (≤6), untested?: [1–80] (≤6), notes?: [1–160] (≤3), suggestions?: [1–40] (≤4), project? }
result { ok: true, report: { title, summary, changes[], tested[], untested[], notes[], suggestions[] },
         reportedAt /* Unix time in ms, after image capture */, project /* root or null */, message, warnings? }
     | { ok: false, code: "INVALID_REPORT", problems[], error }
```

All or nothing: any invalid field (unknown keys included) refuses the whole report. Strings are trimmed and
their whitespace collapsed. `asset` (absolute, or relative to the project) becomes an absolute path inside
the project; one outside it or missing is left out of that change and listed in `warnings`. Without a
resolvable project the report is still accepted (`project: null`) and no asset is kept (it could be another game's). Each
kept asset's current version is saved like a delivered image, so the card keeps showing it after a rewrite.

## Build history (snapshots)

After each successful `chromatic_rom_build` (Hermes's `post_tool_call`: result without `error`/`isError`
and `structuredContent.success === true`, not a `sourcePath` build) of a game in the library, the plugin
copies the project to `<plugin data>/snapshots/<game id>/<ms>/files/` with `<ms>/snapshot.json`
`{ at, game, root, files, bytes, reason: "build" | "before-restore", from?, backup?, fingerprint, builds: [ms…], buildRefs? }`.
Never copied, compared, deleted or restored: top-level `build/`, `artifacts/`, `.git/`, `node_modules/`,
`captures/`, `save-states/`, temporary files (`*.part`, `*.tmp`, …), every symlink, and every folder below the
project that holds a `.gbsproj` of its own (in any case, a file or a link, as the engine finds a project: another
game's project, which restoring this one never changes, even
when an older snapshot holds files there from before it was a game). A project over 64 MB
or 20 000 files is skipped. When the files are identical to the newest snapshot (path + size + SHA-256 of
each), the existing copy is verified and reused. The newest 30 are kept, with the selected snapshot and
backup protected during a restore.

- The build's tool result carries `buildRef`, which the snapshot hook records in `buildRefs`.
  `builds { game, stored? }` returns
  `{ ok, builds: [{ id, at, builds, buildRefs?, buildCalls?, files, bytes, reason, from?, backup? }] }`, newest first.
  `buildCalls: [{ id, ref, timestamp }]` gives the call ID and exact result timestamp in Unix seconds
  when a stored result in the bound conversation carries the recorded build reference. The page uses
  these two fields together when the gateway omits a result body. Without a confirmed match or a result
  body that establishes the outcome, the build shows as unknown. Historical times in `builds` use milliseconds.
  An unmatched legacy snapshot or before-restore backup is selectable by its saved date and time.
- Under one per-game lock, `build_restore` verifies the supplied `buildRef` or historical `buildAt`
  against the selected snapshot. An explicitly selected saved snapshot supplies its `id`. Either
  selection checks the saved file count, byte total and fingerprint. The restore then
  rejects redirected project paths and verifies the backup's names and contents before publishing it.
  The `before-restore` snapshot's `from` field is the restored ID. When a restore reuses the newest
  identical snapshot for the backup, its `backup: { at, from }` records the latest such restore's time in milliseconds
  and selected ID. The restore removes project files absent from the saved build and writes back
  files that differ using a temporary sibling. Each
  overwrite or deletion scans opened ancestor folders for nested-game markers before comparing the live
  file's identity and bytes against the backup. When restore removes a hard link, it records the change
  to that inode's stamp for verifying remaining links. A final scan verifies the resulting project
  paths and contents against the selected snapshot. An unexpected file is preserved and reported.
  Incomplete restores include the verified backup ID, operation counts and up to 20 file problems.
  A complete restore requests a rebuild.

## The game card (`game.json` + `cover.png`)

Every game has a card at its project root, next to the `.gbsproj`: `game.json` and `cover.png`. A starter
`game.json` (title only) is written when a project is created, and by `chromatic_game_info` or
`chromatic_present_game` when missing. Neither file counts as game source, so writing them never marks a
built game as changed. Unknown keys are kept (later fields need no migration).

```
{ version: 1, title, tagline, description, about, genres: [..], tags: [..], controls: { button: action },
  cover: "cover.png", coverSha256, coverForBuild /* ROM sha when the cover was set */, createdAt, updatedAt,
  id /* the portable game id */, gameVersion /* "0.1.0" until a release */, rom /* "build/game.gbc" */,
  remixOf? /* { id, version } of the game a remix came from */ }
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

One entry of the `games` RPC's `games[]` (`describe` in `backend/library/shelf.py`, then `rpc_games` in
`backend/library/rpcs.py`, which reshapes `chat` and `session` and drops `updatedAt`):

| Field | What it holds |
|---|---|
| id, title, displayTitle | The game's id, its project's title, and the card's title when set (else `title`) |
| projectRoot, kind | The project folder; `gbstudio` (it has a `.gbsproj`) or `gbdk` |
| state, error | `ready`, `changed` (sources newer than the ROM), `unbuilt` or `failed`; `error` only when `failed` |
| rom | `{ path, sha256, size, builtAt }` of the game's ROM (`build/game.gbc` or `build/game.gb`, the newer); for a game last built before it had one, the last recorded build's ROM, else the newest in `build/`, else the web export's; or null |
| webExport, web | Whether a web export exists; its ROM `{ sha256, builtAt }`, or null |
| thumb, cover | A data URL for the shelf (the cover, else the captured title screen, else null); whether it is the cover |
| layout | `layout.check()` (`backend/library/layout.py`): `{ ok, problems, warnings }`, each `{ code, path, message }`; a problem blocks presenting, a warning names what stays local |
| card | `game_card.public()` (`backend/library/game_card.py`), or null without `game.json`: `title`, `tagline`, `description`, `about` (text or null), `genres`, `tags` (lists of text), `controls` (`{ button: what it does }`, `{}` when none), `complete`, `missing` (the fields still needed to present), `hasCover`, `coverForBuild` (the ROM sha the cover was set for, or null) |
| chat | `{ sessionId, title, conversationId, profile, thisProfile }` of the chat working on it (the last to select it), or null |
| session | The Build conversation bound to it: `{ storedId, createdAt, thisProfile, profileName, exists }`, or null |

The Build page's rail gets the same objects (`shell.gameList`, `page/app/studio-page.js`), with `title` replaced by
`displayTitle`, `session` null once the page released it, and `buildSession` (the bound stored session id) added
(`build-page.js`).
