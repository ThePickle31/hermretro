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
  or missing SOUL. The compaction cap `compression.threshold_tokens` (Hermes compacts at the lower of it and its
  ratio) is set to 300,000 (`COMPACT_AT_TOKENS`) where the profile's raw config has no such key or a value an earlier
  release set (`OLDER_COMPACT_AT`): by creation and repair, and by registering in the `hermretro` profile
  (`studio_profile.refresh_compaction_cap`), so a Studio-only or `hermes plugins update` gets it too. Any other value
  is the user's and is kept, an explicit `null` (the ratio alone decides) included. `agent.disabled_toolsets` is
  `DISABLED_TOOLSETS` (`code_execution` among them: one-shot chats refuse `execute_code` and the `chromatic_*` tools
  refuse calls from inside it), set by creation and repair, which record it in the profile's marker
  (`studio-profile.json`, `disabled_toolsets`), and once by registering where the profile still has exactly the list
  the marker records (`OLDER_DISABLED_TOOLSETS` for a marker without one; `studio_profile.refresh_disabled_toolsets`
  records the new one); any other list, or none, is the user's. Both registration updates change one key
  (`studio_profile._update_config`, through `api.write_profile_config_key`), never through a `config.yaml` link (it
  would write the linked profile's) and never over a change made meanwhile (read again just before the write; a
  changed config waits for the next registration). Checked by
  `tests/backend/setup/test_studio_profile.py`, `test_disabled_toolsets.py` and
  `tests/backend/hermes/test_registration.py`.
- After a context compaction (any kind but `prune_tool_results`), the chat's next engine tool result that reached the
  engine leads with `hermretroContext`, images or not: the project, the last build and its SHA-256, the live
  emulator session's ROM and frame, its recording (path, session id, branch, status) and the skill pages loaded with
  `skill_view`, after that result is taken in (`backend/hermes/chat_state.py`, per process; the engine tool handler
  adds it, `results.encode`). Emulator state follows the tool and action: `emulator_run`, `emulator_status` and a
  checkpoint restore describe the whole session (no recording in them clears it), `emulator_replay` the ROM it was
  given, `emulator_recording` only `stop` or the live attempt, and `emulator_close` ends the session and leaves its
  recording stopped. A delegated subagent has a state of its own (`subagent_start`). Checked by
  `tests/backend/hermes/test_chat_state.py`.
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
| `library.game_moved` | `old`, `new` (library ids, str), `old_root`, `new_root` (folders, str) | an installed game's update kept the user's edited copy as a game of its own in a new folder (`keep_both`) | history (moves the game's snapshots), assets (moves its images' kept versions) |
| `setup.tools_removed` | `root` (the emptied download folder, str) | `remove_tools`, or the factory reset's `reset` (`toolchain`), emptied the download folder | — |
| `setup.studio_profile_ready` | `profile` (profile name, str) | `studio_profile` finished the profile | — |
| `assets.image_restored` | `path` (the image's absolute path, str) | `asset_restore` put a kept version back | — |
| `history.build_kept` | `game` (library id, str), `root` (the real project folder, `pathlib.Path`) | a successful build was kept as a snapshot | — |
- Tool names: every original engine tool `X` is exposed as `chromatic_X`
  (`project_select` → `chromatic_project_select`, `flash` → `chromatic_flash`). Besides them, the
  plugin-owned tools that are not engine tools (not in the pinned manifest): `chromatic_studio_device_cli`,
  `chromatic_present_game` (shows the built game in the Studio emulator beside the chat; see
  `.agents/skills/hermretro-dev-page/references/player.md`), `chromatic_game_info` (the game card, below), `chromatic_playtest`
  (the test plan's bound checks replayed, below) and `chromatic_build_report` (the Build page's build card, below).
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

### `status` — params `{ chat?: string, sync?: boolean }`

```json
{
  "ok": true,
  "plugin": { "id": "hermretro", "version": "<plugin.yaml version>",
              "installed_in": { "profile": "default", "linked": false }, "root": "/abs/path" },
  "platform": { "system": "linux | darwin", "machine": "x64 | arm64", "rosetta": false, "supported": true,
                "qualified": true },
  "node": { "found": true, "version": "26.13.0", "required": "22" },
  "engine": { "present": true, "version": "1.0.34", "verified": true, "detail": "" },
  "hardware_enabled": false,
  "flags": [],
  "broker": { "running": true },
  "project": null
}
```

`flags` names the feature flags that are on, sorted (`backend/system/flags.py`; `page/app/flags.js` lists them).
`project` is `null` or `{ "root": "/abs/path", "name": "folder", "emulator_active": false, "writer": true }`
for the conversation named by `chat` (the focused chat's id). When the handshake cannot be confirmed,
`broker.running` is `null`. `plugin.installed_in` names the profile Hermes installed
this copy into (the studio profile only links it), where the page runs Hermes's `plugins.manage update`; it is
`{ "profile": null, "linked": true }` for a checkout linked in from elsewhere, which Hermes does not update.
`plugin.root` is the folder the running code was loaded from and `restart_needed` says its files changed since:
together, whether the gateway runs what a profile loads now (`python tools/dev bench run` checks both).
Each call also brings the studio profile's providers up to date in the background; `sync: false` skips that, so
the call only reads. `chat` is not called `session_id` on purpose: the gateway authorizes that name as a live session and rejects the call (`not_found`) for a draft chat. It never starts a worker.

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
Control ops `hold_game` / `release_game` `{root}` (`backend/broker/holds.py`, client `game_hold` in the broker's front door) hold a game while an installed game's update replaces its files: `GAME_BUSY` while a conversation's worker has it selected (or as its workspace) and alive, then every call that would reach it is refused with `GAME_BUSY` until the release (at most 600 s), which closes a worker that opened it meanwhile.
Control op `test_build {root}` (`backend/broker/installed.py`, client `test_build`; the library's `BrokerWorkers.test_build`, which `installs.install`/`update` call after an install the user allowed to build) builds a game installed with its source once, in a worker of its own, under an exclusive hold that outlasts the build and the game's folder lock, and records it there: `install.json`'s `testBuild: {sha256, commit, matches, t}` (`matches`: the ROM it was installed with) and an ordinary `lastBuild`; `{ ok, built, sha256, matches, commit, t, error }`, `BUILD_NOT_ALLOWED` without the user's consent for the commit installed (`buildConsent`), `GAME_BUSY` while anything else holds or has the game. It is work: a retiring broker waits for it. Holds are exclusive (a second `hold_game` is `GAME_BUSY`). A game without its source (installed so, or the edited copy an update kept, `kept-rom.json`) is worked on in its own conversation only, whose worker has its folder as its workspace (`GB_STUDIO_WORKSPACE_ROOT`), rechecked on every call (delegated ones too): only read-only tools, `emulator_run`, `emulator_step`, `emulator_replay`, `emulator_checkpoint`, `emulator_close`, `web_preview_close` and the hardware tools run there (anything else, a new tool included, is `INSTALLED_WITHOUT_SOURCE`); a `romPath` must be its checked ROM (`ROM_OUTSIDE_GAME`), still those bytes, and `flash`'s `expectedSha256` its SHA-256 (`ROM_CHANGED`). No installed game gets `web_build` or `web_preview` (`INSTALLED_PLAYS_ROM`, checked again once its game is selected), and an installed game with its source gets `rom_build` only with consent (`BUILD_NOT_ALLOWED`). A worker of a chat that no longer owns such a game is closed before a hold, so Stop editing does not keep it busy.
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

### `reset_plan` — no params

What the factory reset (Settings → Plugins → hermretro) would delete, part by part, for its choices:

```
{ ok: true, parts: {
    games: { bytes, count },        // what deleting the games removes; count: the library's games
    history: { bytes },             // kept versions: build snapshots and image versions (this profile's)
    chats: { count },               // the studio profile's chats; null when they cannot be read
    profile: { ours, holds },       // ours: the hermretro profile is the one hermretro made; holds: hermretro's
                                    // own folders, its toolchain or a library game are inside it
    settings: {},                   // hermretro's settings in Hermes
    toolchain: { bytes, custom },   // <hermretro home>/.cache; custom: a folder the user configured (left alone)
    logs: { bytes } } }             // the broker's logs, saved frames, the captures of the games in the games folder
{ ok: false, error }
```

The studio profile is Hermes's own: the page deletes it through Hermes (`host.deleteProfile`), which takes its chats,
build history and its copy of the plugin settings with it. Every call of the reset, `status` first, goes through an explicit profile
route on the Hermes connection the app is on as the dialog opens, so switching the app's connection or profile does
not move it. A profile named hermretro that hermretro did not make and set up is never asked.

### `reset` — params `{ part }`

One step of the factory reset; the page calls it once per part it deletes, in this order: `stop`, `history`, `logs`,
`games`, `chats`, `settings`, `toolchain`; before each one it checks that no studio chat is building. Every part but `settings` first asks the broker to stop with its idle workers
(`{"op": "shutdown", "replace": true}`) and holds its election lock while it deletes (`backend/setup/broker_stop.py`);
`stop` does only that. While a part is deleted, the player saves no capture (`player.captures_paused`). `games` empties the games folder (only the library's games in it when `HERMRETRO_GAMES_DIR`
is set), deletes the library's own files (`games.json`, its lock, `thumbs/`); a
game in a folder of the user's own leaves the library but stays on disk with its captures, and a game folder a link
now stands in for is never followed, nor is a games or library folder (or `games.json`) that is a link. The library
goes only once every game folder is gone, so a retry still finds what is left (`LIBRARY_UNREADABLE` when a games
folder the user configured has no readable library to say which games are hermretro's). `logs` deletes the broker's
logs, saved frames, the demo cartridge's captures (`<library>/captures/demo`) and the captures of the games in the
games folder. A capture asked for while a part is deleted (counted from when its upload began) is refused, not written
afterwards. `chats` deletes each studio chat with Hermes's `hermes sessions delete` (its ids read-only from the
studio profile's `state.db`, never one that is a link, in rounds, since a deleted chat's forks become chats of their own), only in the profile
hermretro made (`NOT_OURS` otherwise), `CHATS_LEFT` when some remain, `CHATS_UNREADABLE` when its database cannot be read. `settings` clears `plugins.entries.hermretro.settings` (and the older `config`, which Hermes still
reads) in this profile and the one hermretro was installed into, never through a `config.yaml` that is a link
(`CONFIG_LINKED` says which profile's were left), so each setting reads its default. `toolchain` is `remove_tools`. Returns `{ ok: true, removed_bytes }`
(the toolchain answers as `remove_tools` does) or `{ ok: false, code, error }` with `code` `UNKNOWN_PART`, `PARTLY_REMOVED` (something could not be deleted; `removed_bytes` says what was), `CHATS_LEFT`
(`partly` with either, and with `toolchain`'s `PARTLY_REMOVED`: some of the part did go), `LIBRARY_UNREADABLE`,
`CHATS_UNREADABLE`, `NOT_OURS`, `CONFIG_LINKED`, `BUSY`
(a call is running or the broker did not stop within 15 s), `WORKER_STILL_RUNNING`, `UNAVAILABLE`, or one of
`remove_tools`'s.

### `releases` — no params

hermretro's published releases, for the page's update card and dialog: GitHub's releases of the repository, stable and
published ones only (no drafts, no `-rc` tags), newest first. Each one's `notes` come from its generated notes (the
squash-merged pull request titles): `feat` lines are `new`, `fix` lines `fixed`, without the `type(scope): ` prefix
and the author; other types and the `dev`, `ci`, `test`, `tests`, `docs` and `release` scopes are left out. An answer
is kept for 10 minutes; a failure is not kept. Never raises.

```
{ ok: true, releases: [{ version: "0.0.13", date: "2026-11-24T04:00:00Z", url, notes: [{ kind: "new" | "fixed", text }] }] }
{ ok: false, error }
```

### `activity` — params `{ chat?: string, stored?: string, limit?: number }`

Was for the panes beside the chat, which are gone (the Build page shows the agent's work); kept for older
desktop halves and for the broker's own use. `chat` and `stored` are the focused chat's runtime and durable ids; either may
match. Served from the broker's memory: no engine call, never starts the broker or a worker.

```
{ ok, running, matched: "chat" | null,
  lane: { project_root, project_name, alive, busy, current_tool, preview_url } | null,
  frame: { t, tool, frame, src /* data URL, or null when that image was too large to keep */ } | null,
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
| `games` | none | `{ ok, games[], unavailable[], pending[], demo, device, gamesDir }`: the library (`<hermretro home>/library/games.json`, see `backend/system/paths.py`). Each game (`describe` in `backend/library/shelf.py`): `id, title, projectRoot, kind, state, rom: { path, sha256, size, builtAt } \| null, webExport, web: { sha256, builtAt } \| null, thumb, cover` (whether `thumb` is the cover art), `card` (below, or null), `layout: { ok, problems[], warnings[] }` (the game folder's layout, `backend/library/layout.py`), `install: { source, url, ref, commit, mode, rom, romSha256, installedAt, edited, testBuild, buildAllowed } \| null` (where a game installed from a link came from, `backend/library/installs.py`; `romSha256` the ROM its install checked; `testBuild: { sha256, commit, matches, t } \| null`, the one build here of the commit installed of a game with its source; `buildAllowed`, the user's consent to build it; null for a game made here), `duplicateId` (the other library folders holding a game with this one's id, a folder copied by hand; null when none), `shell` (true for a game the bundled player plays, `backend/library/play.py`: an installed game, or the edited copy kept of one; `rom`, `webExport` and `web` describe the ROM it plays, and a game without its source has only its checked ROM: `state` `romChanged` and no `rom` when that ROM changed), `displayTitle, chat, session, error`; what each means: `.agents/skills/hermretro-dev-page/references/player.md`, "`games` → library". |
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

`chromatic_present_game` `{ note?, unfinished?, project? }` is the agent's way to show a finished game: it needs a
fresh web export the engine made of the current sources (else `BUILD_FIRST`; with `unfinished`, an export the engine
made and nothing changed since, `freshness.intact_export`, of whichever build), the pipeline gate's go (below, "The
pipeline gate"; `unfinished` passes it) and a complete game card (else
`GAME_INFO_INCOMPLETE` with `missing`, `problems` and `nextStep`; before the card, a game folder out of its layout gets
`LAYOUT` with `nextStep`: `layout.check`'s problems, `backend/library/README.md`, "The game folder"), records the presentation and returns `{ ok, studio: { gameId, playerUrl,
title, note, presentedAt, buildConversation }, unfinished?: { request, notVerified[], notCurrent? } }`
(`buildConversation`: the game's own Build conversation presented it, so the Build page plays it; `unfinished` when the
call gave it and the gate held or the export was not fresh: `notVerified` the gate's `reasons`, `notCurrent` why the
export is not the current sources). The library keeps `unfinished` with the presentation (`presented`,
`presentations`), and the Build page marks the build Unfinished; otherwise the desktop opens the emulator in a tab docked right of the chat. Builds
open nothing. Setting `live_player` ("Keep the playable copy current", default on) makes every successful
`rom_build` refresh that web export, so a presentation finds it fresh.

Every plugin tool's failure is `{ ok: false, error, code, nextStep? }` (`tool_error(message, code, next_step)`):
`nextStep` says what the agent does about it, and `ADAPTER_ERROR` always has one. `chromatic_game_info`,
`chromatic_present_game` and `chromatic_build_report` act on the chat's own game: a library game is acted on only
from its own Build conversation. In a game's Build conversation a `project` naming another folder is refused with
`ONE_GAME_PER_CONVERSATION`; in a New Game conversation, one naming an existing game with `NEW_GAME_ONLY`; from any
other chat, a library game (named, or found through a chat link left after Stop editing) with `GAME_CHAT_ONLY`. A game
with a Build conversation keeps it as its `chat` link whatever other chat touches it. An engine tool the broker cannot run answers
`UNAVAILABLE` with a `nextStep`; when another copy of the plugin's broker still runs games, it says whether one is
this chat's own (the plugin folder changed under it) or other chats'.

## The build card (`chromatic_build_report`)

The agent calls `chromatic_build_report` once at the end of every turn that changed or built the game
(after `chromatic_rom_build`, its own playtest and `chromatic_present_game`), never in a subagent
(`PARENT_ONLY`). The Build page draws the call as the turn's build card, so the written reply after it stays
one or two sentences. The page reads the tool call and its result; the report stores only the checks it took on their
own evidence (`playtest.verify`, below, "The pipeline gate").

```
args   { title (1–48), summary (1–280), changes?: [{ kind: added|changed|removed, text (1–100), asset? }] (≤8),
         tested?: [1–80] (≤6), untested?: [1–80] (≤6),
         checks?: [{ id (1–9), text (1–80), result: passed|failed|not run|blocked|needs review,
                     evidence? (1–4096) }] (≤100),
         difficulty? (1–200), finishRun? (1–4096), unfinished? (1–160), notes?: [1–160] (≤3),
         suggestions?: [1–40] (≤4), project? }
result { ok: true, report: { title, summary, changes[], tested[], untested[], checks[], difficulty /* or null */,
                             finishRun: { recordingPath, sessionId, status, frames, outcome? } /* or null */,
                             unfinished?, notVerified?: [] /* when the gate held */, notes[], suggestions[] },
         reportedAt /* Unix time in ms, after image capture */, project /* root or null */, message, warnings? }
     | { ok: false, code: "INVALID_REPORT", problems[], error }
     | GATE /* the pipeline gate's refusal, when it is the only problem */
```

All or nothing: any invalid field (unknown keys included) refuses the whole report. Strings are trimmed and
their whitespace collapsed. `asset` (absolute, or relative to the project) becomes an absolute path inside
the project; one outside it or missing is left out of that change and listed in `warnings`. Without a
resolvable project the report is still accepted (`project: null`) and no asset is kept (it could be another game's). Each
kept asset's current version is saved like a delivered image, so the card keeps showing it after a rewrite.

A game with a test plan (`docs/game/TEST-PLAN.md`, `backend/library/plan_checks.py`) holds every report to it:
`difficulty` is required, and `checks` names each open check exactly once and nothing else. A check is a row of a
table whose first header cell is `ID`, superseded when its `Status` (or `Result`) cell says so, or a line `T1: ...`
outside the sections whose heading names results, superseded when it starts with or gives `Status: superseded`.
IDs are 1–4 letters, an optional hyphen, 1–3 digits and an optional letter (backticks and bold around them are
ignored) and compare without case, in the plan and in the report. A check-table row with any other ID adds a
warning naming it; a plan with no checks asks only for `difficulty` and adds a warning; one with more than 100 open
checks refuses every report with a problem asking to combine related checks through an approved decision. Without
a plan both are optional. The page keeps `checks` as `{ id, text, result }`: the card lists a passed check as
play-tested, a failed one as failed and any other as not tested (`page/pages/build/chat/report.js`), and the
play-test checklist keys a check by its ID without case, so its result on a later build replaces it.

`finishRun` names the recording of the one run from power-on to the ending (`backend/library/finish_run.py`): a
recording folder's path (absolute or relative to the project; the folder or its `recording.json`) or its 32-hex
session id, looked up in the project's `artifacts/playtests/`. It is refused unless it is a recording inside the
project (`recording.json` of kind `gb-studio-playtest`, written by the engine's emulator worker), of the game's ROM
as it is now (its `rom.sha256` against `build/game.gbc` or `build/game.gb`), already ended (not `status:
"recording"`, since the engine writes branches only when an attempt ends) and with no branch restored from a
checkpoint. In a game with a test plan, a report giving `F1` (`plan_checks.FINISH_CHECK`, the template's finishable
check) `passed` or `failed` needs `finishRun`, and a `passed` one needs a recording that ended `stopped` (not
`failed` or `cancelled`); a report without `finishRun` otherwise adds a warning saying it shows no recorded run.

`chromatic_build_report` also holds `checks` to `chromatic_playtest`'s last run on the game's ROM as it is now (below;
`report_plan.playtest_problems`): a check that run gave `failed` or `error` cannot be reported `passed`, and one it
gave `passed` or `failed` cannot be reported `not run`; each reported check it ran gains `playtest: { result, ranAt }`
in the answer's `report.checks` (the page keeps only `{ id, text, result }`). A bound check reported `passed` with no
run on this ROM adds a warning.

## The pipeline gate

`chromatic_present_game` and `chromatic_build_report` wait until the game's ROM is the last build of its sources as
they stand and its test plan's bound checks and F1 passed on that ROM (`backend/library/pipeline.py`). It reads the
library's `lastBuild` and the game's playtest state. Only digests pass a ROM, never file times: no `lastBuild`, a
failed one, another ROM than its `sha256`, one without `sha256` or `sources`, or sources whose
`freshness.source_digest` is no longer its `sources` hold it. The broker takes `sources` before the build starts and
the library keeps it only when the digest is the same when it ends (a file saved while it compiled leaves none).
`freshness.source_files` defines the sources, bounded at 20000 files while listing: a GB Studio project's `.gbsproj`
and every file under `project/`, `assets/` and `plugins/`; any other folder (a C game) every file but the
`project.NOT_SOURCE` folders (in any spelling on a volume that ignores case, `backend/system/host.py`
`ignores_case`), the game files at the top and `*.md` notes; hidden files never count. A game without a test plan
needs only the current ROM; the report holds a library game with no ROM too (a turn that built nothing gives
`unfinished`), and nothing for a folder the library does not know with no ROM.

```
GATE { ok: false, code: "BUILD_FIRST" | "PLAYTEST_FIRST", error, reasons[] /* what is not verified */, nextStep,
       pipeline: { rom: { path, sha256, problem /* or null */ },
                   checks: { passed[], sampled[], verified[], failed[], error[], notRun[], unbound[], stale[],
                             finish /* F1's id or null */, finishUnbound } /* or null without a plan */,
                   ready } }
```

`BUILD_FIRST` comes first, while the ROM is not current (results on it would be of another game). `PLAYTEST_FIRST`
holds while a bound check has no result on this ROM (`notRun`), `failed` or `error`, or F1 is open but not bound for
its words (`finishUnbound`); `sampled` counts as passed, and an unbound check other than F1 holds nothing. A report's
own evidence of this ROM counts as `verified`: an `error` check with `evidence` (its `playtest.verifiedBy`), and F1
reported `passed` with a `finishRun` that ended `passed`. An accepted report keeps them (`playtest.verify`: the game's
`.hermretro/playtest.json` `verified`, by check, with the ROM's hash and the check's words), and the gate counts them
for both tools while the ROM and the words stay (`playtest.verified`), so a check no replay can judge is shown by a
report and then presented. `nextStep` names what to do (no `chromatic_playtest` step for a game without a plan) and
ends with the override: `unfinished` (1–160 characters), given only when the user asked for the game as it is (or, in
a report, a failure the turn could not fix or a turn that built nothing), passes the gate; the game is shown with
`unfinished` (above), the report with `report.unfinished`, `report.notVerified` (the gate's `reasons`) and a warning,
and the Build card shows both. In a report with other problems the gate's error and next step are one more problem
(`INVALID_REPORT`).

After a successful `chromatic_rom_build`, its result carries `testPlan: { staleResults[], notRun[], nextStep }`
(`library.after_build`, added by the engine tool handler after `buildRef`) when bound checks have no result on the
new ROM: those whose last result was on an earlier ROM, and those never replayed. Only a build of the game
(`project.game_build`: not a C `sourcePath` inside a GB Studio project) whose ROM (`rom.sha256`) is the game's ROM now
says so. A rebuild to the same bytes, or a game without a plan or bindings, has none.

## The test plan, replayed (`chromatic_playtest`)

A check of `docs/game/TEST-PLAN.md` can be bound to a recorded attempt; `chromatic_playtest` replays every bound check
on the game's ROM as it is now (`backend/library/playtest.py`, `playtest_run.py`, `playtest_tools.py`). It calls the
engine as the chat (`host.engine_call`, so the chat's state follows the replays), never touches a device, and is the
main conversation's: a subagent's call is refused (`PARENT_ONLY`) before anything is read from the engine or written.
Every answer, a refusal included, keeps the note after a compaction first as `hermretroContext` and the broker's
notices (joined) as `notice`.

```
bind   args   { action: "bind", check (1–9), recording (1–4096: a recordingPath or 32-hex session id),
                branchId? ("branch-NNNN"), toActionIndex? (≥ 0), expect?: { frames?: match|ignore, scene? (1–256),
                variables?: { name: integer -32768–65535 } (1–8) }, project? }
       result { ok: true, binding: BINDING /* recording absolute */, bound[], stale[], unbound[], retired[], nextStep }
            | { ok: false, code: "INVALID_BINDING", problems[], error, nextStep }
unbind args   { action: "unbind", check, project? }
       result { ok: true, removed /* bool */, bound[], stale[], unbound[], retired[],
                cleared?: { check, result: failed|error } /* the result on this ROM it took away */, nextStep? }
run    args   { action?: "run", checks?: [id] (≤100), project? }
       result { ok: true, project, rom: { path, sha256 }, ranAt /* ms */,
                counts: { passed, sampled, failed, error, stale, unbound }, checks: [CHECK], stale[], unbound[],
                retired[], finishRun /* F1's recorded replay when it passed or failed, else null */,
                endedSession?: { romSha256, frame, recording?: { recordingPath, sessionId, branchId, status } },
                nextStep }
            | { ok: false, code: "NOT_RUN", error, nextStep }
CHECK  { id, result: passed|sampled|failed|error, recordingPath /* the bound recording */, sessionId, branchId,
         toActionIndex, expect, revision /* the binding's */,
         replay: { status: matched|diverged, replayedActions, toActionIndex, actionCount, comparedFrames,
                   coverage, deterministic, frame } /* or null when the replay was refused */,
         divergence: { frame, actionIndex, lastMatchedFrame, differingFrames? } /* or null */,
         observed: { scene?, variables? } /* or null */, problems[], notes[],
         evidence: { expected?, actual?, end? /* saved image paths */, recordingPath? /* F1's recorded replay */ } }
BINDING { id, check /* digest of the check's words */, recording, sessionId, branchId, toActionIndex /* or null */,
          expect: { frames, scene?, variables? }, romSha256 /* the ROM the recording played */, boundAt /* ms */,
          revision /* digest of the fields above but romSha256 */ }
```

`bound`, `stale`, `unbound` and `retired` are check IDs: open checks with a binding, with one made before the check's
words changed (bind it again; a run skips it, and `checks` naming it is `NOT_RUN`), and with none, and bindings of
checks no longer open (superseded or removed), which a run skips. A check's words are its row's cells but the
Status/Result cell, or its line's text before any `Status:` (`plan_checks.Plan.definitions`), spaces collapsed; a
retired ID used again for other words is stale. A binding needs a plan that lists the check open, a recording inside
the project (`finish_run.find_recording`: its manifest and journal agree), the branch among the recording's, and
`toActionIndex` while the recording still has `status: "recording"`; such a recording's branches and session come from
the engine (`emulator_recording {action: "status"}`), since its `recording.json` lists only the branches it started
with. F1 (`plan_checks.FINISH_CHECK`) binds only a whole run (no `toActionIndex`) that ended, restored no checkpoint
and was stopped with outcome `passed`. `expect.frames` defaults to `match` without `scene` or `variables`, else
`ignore`; `ignore` alone is refused. Binding again or unbinding drops the check's result; an unbind that drops a
`failed` or `error` result on the current ROM names it (`cleared`) with a `nextStep` to report its true result.

A run replays the bound open checks in plan order, F1 last, each with one `emulator_replay` `{ romPath, recordingPath,
sessionId, branchId, toActionIndex?, onDivergence, expect, recording: false }` (`onDivergence: "stop"` for frames
alone, `continue` when a scene or variables decide). The engine refuses a replay whose folder holds another attempt
than `sessionId` (an older build's recording of that attempt is fine), and judges `expect` in the same queued emulator
operation (`verdict { outcome: passed|failed|needs-review, problems[], observed?, unreadable? }`: failed when `frames:
match` and a frame differs, fewer actions than asked were played, or the scene, by name or symbol, or a variable,
signed or unsigned, is another; needs-review when they could not be read, as in ROM debug mode). A check is `passed`,
or `sampled` when `frames: match` and the replay's `coverage` is not `every-frame` (only the frames the recording kept
were compared); `failed`; or `error` for needs-review, a replay the engine refused, or the engine replaying another
session. F1's replay is recorded in `artifacts/playtest-runs/<id>-<time>/` with `maxBytes` twice what its source used
(16 to 512 MiB) and `finishRecording: true`, so the same operation stops it with the verdict as its outcome. It is
F1's evidence (and the run's `finishRun`) only when `finish_run.read_run` takes it (this ROM, ended, no restore,
journal agrees) with outcome `passed` (all of the run's actions replayed) or `failed`; else F1 is `error`. Before it,
the oldest finished recordings this module named there (`RUN_NAME`) are removed until one more fits by count
(`KEEP_RUNS`, 4) and by reserved bytes (1 GiB, the engine's bound per folder); never one a binding or a kept result
names. `endedSession` is the session the run's first replay ended; a recording with `status: "recording"` there was
an attempt still being made, which the replay stopped (and kept).

Nothing is kept when the broker refused a call before it ran (`denied`, or not dispatched): the run answers `NOT_RUN`
and earlier results stay. Nothing is kept either when a replay's `romSha256` is not the ROM the run hashed, or the ROM
changed by the end of the run. Otherwise each result is kept only when its check's binding still has the revision it
ran for (a check bound again or unbound meanwhile gets the note "Not kept").

State (`.hermretro/playtest.json`, under the game folder's lock, read once per call as `playtest.read`):

```
{ version: 1, bindings: { <CHECK KEY>: BINDING /* recording relative to the project */ },
  results: { <CHECK KEY>: { id, result, ranAt, romSha256, revision, check, problems[] (≤4), notes[] (≤4),
                            coverage?, recordingPath? /* F1's recorded replay */ } } }
```

Check keys are `plan_checks.check_key` (upper case). A result stands (`playtest.current(plan, state, rom)`) only while
its `romSha256` is the game's ROM, its `revision` its check's binding's and its `check` the binding's and the plan's
digest of the check's words. A run of some checks leaves the others' results. `chromatic_build_report` holds each
reported check to the result that stands: `passed` is refused for `failed`, and for `error` unless the check gives
`evidence` (a recording in the project of this ROM, a path or session id; the check's `playtest` then has
`verifiedBy`); `not run` is refused for `passed`, `sampled` or `failed`; `passed` for `sampled` adds a warning, as
does `passed` for a bound check with no result on this ROM. Each reported check with a result gets
`playtest: { result, ranAt, verifiedBy? }`.

## Build history (snapshots)

After each successful `chromatic_rom_build` (Hermes's `post_tool_call`: result without `error`/`isError`
and `structuredContent.success === true`, not a `sourcePath` build) of a game in the library, the plugin
copies the project to `<plugin data>/snapshots/<game id>/<ms>/files/` with `<ms>/snapshot.json`
`{ at, game, root, files, bytes, reason: "build" | "before-restore", from?, backup?, fingerprint, builds: [ms…], buildRefs? }`.
Never copied, compared, deleted or restored: top-level `build/`, `artifacts/`, `.git/`, `node_modules/`,
`captures/`, `save-states/`, `scratch/` (the agent's helper scripts and working files; on a volume that ignores case,
each of these top-level folders in any spelling, `backend/system/host.py` `ignores_case`), temporary files (`*.part`, `*.tmp`, …), every symlink, and every folder below the
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
  remixOf? /* { id, version } of the game a remix came from */,
  format /* the folder's format, layout.FORMAT_VERSION; an install refuses a newer one */,
  license? /* MIT, CC-BY-4.0, CC-BY-SA-4.0, CC-BY-NC-4.0, CC0-1.0 or All-Rights-Reserved (licence.py) */,
  author? /* the licence's copyright holder, else "the authors of <title>" */,
  romSha256? /* the last successful build's ROM, what an install checks; absent until a build */,
  builtWith? /* { engine, verified, gbStudio?, gbStudioCommit?, repeatable? }: what built it; absent until a build.
                The GB Studio parts only when verified: the CLI the build ran is the one the toolchain's setup installed */ }
```

- **Written by hermretro** (`layout.ensure` and, after each successful build of the game's ROM, `build_record.record_build`
  with the build's own `outputPath` and ROM SHA-256): `id`, `gameVersion`, `rom`, `format`, `romSha256`, `builtWith`,
  and `LICENSE` from `license` (when missing, or one it wrote: their digests are `.hermretro/licence.json`, so one a
  history restore brings back is still its own, and in a game made here the engine template's, GB Studio's own, is
  replaced; an installed game's `LICENSE` is its author's and a `LICENSE` of the user's own is kept, and an update never carries the
  record). `format`, `romSha256`, `builtWith` and that `LICENSE` never count as an edit of an installed game.
- **Publishing** (`publish_ready.readiness(root, source=, last_build=)` → `{ ok, problems, warnings }`, `last_build`
  the library's `lastBuild`): the layout's problems (incl. `FORMAT_NEWER`), `CARD`, `NO_LICENSE`, `NO_LICENSE_TEXT`,
  `LICENSE_STALE` (the `LICENSE` hermretro wrote, or a made-here game's template one, is another licence), `NO_ROM`, `ROM_OLD` (`pipeline.rom_state`: not
  the last build of the sources by their digest), `ROM_UNFIT` (not a ROM a Chromatic cartridge holds, `cartridge.py`),
  `ROM_SHA_STALE` (`romSha256` is not this ROM: build again), `NO_SOURCE`, the scan's blocking findings, and
  `INSTALL_<code>`: what an install of exactly the published files would refuse (`install_git.tree_problems`,
  `install_check.take_payload` and `check`). `publish_ready.scan(root, source=)` (`publish_scan.py`) → `{ blocking,
  warnings }` over exactly `release.files` (no GB Studio `.bak`/`.new` leftovers), each read without following links:
  `SECRET` and `HOME_PATH` (with `line`; a ROM's printable strings too), `UNREADABLE`, `FILE_TOO_LARGE` (over 20 MB),
  `TOO_LARGE` (over 50 MB in all), `TOO_MANY` (over 5000 files); the warnings `NOT_TEXT` (a file it could not read as
  text) and `PLUGIN_CODE` (the code under `plugins/`, `files`).

- **Required to present:** title (1–60), tagline (8–90), description (40–400), 1–3 genres from `Action,
  Adventure, Arcade, Exploration, Platformer, Puzzle, Racing, Role-playing, Rhythm, Shooter, Simulation,
  Sports, Strategy, Story, Other`, and a cover. Placeholder words (TODO, TBD, lorem ipsum, …) do not count.
  Optional: about (≤4000), tags (≤12, ≤24 chars), controls (≤12, button ≤20 chars, action ≤60 chars).
  `game.json` is at most 64 KB.
- **Cover:** a PNG of at most 512 KB, exactly 160×144, every pixel opaque, 3–32 colours (pixel art, drawn natively, never
  Image Generation), not a byte-identical copy of a PNG under `assets/` (any case of `.png`). Read by `backend/library/game_cover.py`
  with the standard library (8-bit and palette PNGs, not interlaced).
- `chromatic_game_info` `{ title?, tagline?, description?, about?, genres?, tags?, controls?, license?, cover?,
  project? }` (`license` only as the user chose it): with no fields it reports the card; otherwise it checks every field and stores all or
  nothing (`INVALID_GAME_INFO` with `problems`), copying `cover` into the project. Answers `{ ok, card,
  file, complete, missing, problems, nextStep }`.
- `games[].card` = `{ title, tagline, description, about, genres, tags, controls, license, complete, missing,
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
| duplicateId | `shelf.mark_duplicates()`: an array of the absolute paths of the other library folders whose game has this one's id (`.hermretro/identity.json`; one folder reached two ways counts once), or null; the card shows a Same id tag naming them |
| install | `shelf.installed_from()`: for a game installed from a link, `source` (its canonical repository and folder), `url`, `ref` (its branch), `commit` (installed), `mode` (`game` or `game+source`), `rom` (the ROM the install checked, relative; a game alone's `rom` above is that file), `installedAt` (seconds) and `edited` (its files changed since); null for a game made here. On disk, `.hermretro/install.json`: `backend/library/README.md`, "Installing a game from a link" |
| card | `game_card.public()` (`backend/library/game_card.py`), or null without `game.json`: `title`, `tagline`, `description`, `about` (text or null), `genres`, `tags` (lists of text), `controls` (`{ button: what it does }`, `{}` when none), `license` (one of `licence.LICENSES`, or null when the card names none or not one of those), `complete`, `missing` (the fields still needed to present), `hasCover`, `coverForBuild` (the ROM sha the cover was set for, or null) |
| chat | `{ sessionId, title, conversationId, profile, thisProfile }` of the chat working on it (the last to select it), or null |
| session | The Build conversation bound to it: `{ storedId, createdAt, thisProfile, profileName, exists }`, or null |

The Build page's rail gets the same objects (`shell.gameList`, `page/app/studio-page.js`), with `title` replaced by
`displayTitle`, `session` null once the page released it, and `buildSession` (the bound stored session id) added
(`build-page.js`).
