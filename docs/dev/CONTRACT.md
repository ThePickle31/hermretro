# Internal contract: names shared by backend, desktop page and skills

## Identity

- Plugin id: `hermretro`. Display name: `hermretro`.
- Toolset: `chromatic`.
- Tool names: every original engine tool `X` is exposed as `chromatic_X`
  (`project_select` → `chromatic_project_select`, `flash` → `chromatic_flash`). 81 tools, plus two
  plugin-owned tools that are not engine tools (not in the pinned manifest): `chromatic_studio_device_cli`
  and `chromatic_present_game` (shows the built game in the Studio emulator beside the chat; see
  `docs/dev/STUDIO-PAGES.md`). 83 in total.
- Skills are loaded as `skill_view("hermretro:<skill>")`:
  `setup`, `game-planning`, `authoring`, `pixel-art`, `rom-debugging`, `deployment`.

## Backend RPC (desktop → Python)

Called with `host.request('plugin.hermretro.<name>', params)`.
A disabled or missing backend answers JSON-RPC error `-32601`.

### `status` — params `{ chat?: string }`

```json
{
  "ok": true,
  "plugin": { "id": "hermretro", "version": "0.0.4" },
  "platform": { "system": "linux", "machine": "x86_64", "qualified": true },
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
  "root": "/abs/plugin/deps/toolchain",
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

For the panes beside the chat. `chat` and `stored` are the focused chat's runtime and durable ids; either may
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
| `games` | none | `{ ok, games[], demo, device }`: the library (`~/.local/state/chromatic-studio/games.json`) |
| `game_thumb` | `{ id, png }` | `{ ok }`: stores a title screen for the shelf |
| `player` | `{ id? }` (none or `demo`: the demo cartridge) | `{ ok, url, romSha256, title, demo? }` on the loopback player server |
| `presentations` | `{ since? }` | `{ ok, now, presentations[] }`: what `chromatic_present_game` showed, for a desktop that missed `tool.complete` |
| `captures` | `{ id }` | `{ ok, captures[] }`: screenshots and videos saved from the player |
| `capture_image` | `{ id, png }` | `{ ok, path }`: saves a frame for Ask Hermes / annotate |

`chromatic_present_game` `{ note?, project? }` is the agent's way to show a finished game: it needs a fresh
web export (else `BUILD_FIRST`), records the presentation and returns `{ ok, studio: { gameId, playerUrl,
title, note, presentedAt } }`; the desktop then opens the emulator in a tab docked right of the chat. Builds
open nothing. Setting `live_player` ("Keep the playable copy current", default on) makes every successful
`rom_build` refresh that web export, so a presentation finds it fresh.

