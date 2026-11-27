# The emulator, the library RPCs and the frame

## The emulator beside the chat

User request: show **our** emulator (the Emulator page's bar + ModRetro's real player from `backend/player/server.py`,
Hermes Edition Nous Black) beside the chat instead of the engine's page in the in-app browser — and only
when the agent is ready to present the game after making it, never for the whole of development
(user requirement: "it should not be there the entire time"). Builds open nothing.

- **Agent tool `chromatic_present_game`** (plugin-owned, toolset `chromatic`, registered next to
  `chromatic_studio_device_cli`; not an engine tool, not in the pinned manifest). Params
  `{note?: string ≤300, project?: absolute folder}`. The project is `project` when given (in a game's Build
  conversation only that game: else `ONE_GAME_PER_CONVERSATION`; a library game from any chat but its own
  conversation: `GAME_CHAT_ONLY`), else the game whose Build conversation this
  is, else the chat's lane selection (broker `activity` op, memory only, never starts the broker), else the
  library game whose chat link is this conversation (`host._chat_project`). It requires a fresh web export
  (`library.export_freshness`: `build/web` exists, is the engine's own (its `.codex-web-build.json` lists the ROM
  and `index.html` with hashes that still match), plays the game's ROM byte for byte
  (`build/game.gbc` or `.gb`, when that file exists; not in a batteryless project), is not older than the last ROM build — the registry's `lastBuild.t`, else that ROM's file
  time — and its sources are unchanged (`lastWebExport.sources`, a
  content digest; for an older record, no source file newer than the copy), where the
  export's time is the later of its ROM file and `lastWebExport.t`, which the broker records on every successful
  `web_preview` open, because the engine reuses an export whose sources did not change without rewriting its
  files, unless a newer build of those sources made another ROM, which the export then plays (`engine/CHANGES.md`); a failed build after it also counts as stale); otherwise `{ok:false, code:"BUILD_FIRST", error,
  nextStep}`, the next step saying whether to build again or only to remake the copy with `chromatic_web_preview`. On success it records the presentation in the games registry
  (`games[id].chat`, `games[id].presented = {t, note}`, and the bounded `presentations` list) and returns
  `{ok:true, studio:{gameId, playerUrl, title, note, presentedAt}, message:"Shown to the user beside the chat."}`.
  It never calls an engine tool or a device; the approval hook lets it through; a delegated subagent is
  refused (`PARENT_ONLY`).
- **Trigger.** `register()` subscribes with `ctx.onEvent` (fallback `host.onEvent`) to the gateway event
  `tool.complete`, payload `{tool_id, name, args, result, …}` (`result` already JSON-parsed by
  `tui_gateway/tool_progress._on_tool_complete`), envelope `session_id`. Only a successful
  `chromatic_present_game` (`result.ok` and `result.studio.gameId`) opens or fronts
  `host.openWorkspace('hermretro.emulator.<game id>', {dock: {pane: 'workspace', pos: 'right'},
  minWidth: '22rem', title: 'Emulator · <studio.title>'})`. `chromatic_rom_build` / `chromatic_web_preview`
  completions bump a counter so open beside-chat tabs check their game at once.
- **Fallback.** The gateway sends `tool.complete` only while the chat's tool progress is not `off`, so every
  `message.complete` (600 ms later) calls RPC `presentations` with `since` = the backend's `now` from the
  previous answer minus 1 s and presents the newest one per game. The first answer uses the backend's
  clock and elapsed time since plugin startup to keep the same five-second lookback.
  Presentations are de-duplicated by `<gameId>:<presentedAt>`, so one heard through both paths is acted on once.
- **Presenting again** loads the newest build in the open tab directly (the player query and frame key
  change, no banner): it is an explicit "try this now". The note appears as a slim, dismissible line
  (`.cs-side-note`) between the bar and the player; a presentation without a note shows none.
- **Rebuilt without presenting.** An open tab keeps the `Hermes rebuilt <game> · Load the new build`
  banner (no auto-reload). A closed tab is never reopened by builds.
- **User's own button.** The Emulator page's **Open beside the chat** (under the player, hidden on
  desktops without `openWorkspace`) opens or fronts the current game's tab on request. There is no
  auto-open setting any more (the old `sideEmulator` / `sideOpened` storage keys are unused).
- **One live player.** A module atom names the surface that runs the game: `'page'`, `'side:<id>'` or
  none. Opening the Emulator page, a presentation opening a tab, or **Bring it here** takes it; the other
  surface unmounts its frame and shows "Playing beside the chat" / "Playing in hermretro" with
  Bring it here (which starts the game again). A surface that unmounts gives it up; a visible surface
  takes it when nobody has it.
- **Tab content.** Same `EmulatorBar`, `PlayerNotice`, `PlayerStage` and annotate / Ask Hermes code as
  the page, in `.cs-page.cs-side` (stage fills the tab; the player inside scales by height and width).
  Page keys reach the game only after the user last clicked inside the tab, so the chat keeps its keys.
- **Rebuilt check.** Both emulators poll `game_build_status` every 5 s while visible and holding playback.
  The beside-chat tab also checks on taking playback, showing the live tab again, and a build or turn ending
  while it is active. When the RPC returns method not found (`-32601`), the check uses a successful
  shelf response from the same profile. The Studio uses its existing 30 s shelf refresh, and the tab
  reads the shelf on its next check. Other failures keep the last successful game data and hide the rebuild
  action until a check succeeds. An explicit `web: null` leaves the build comparison unavailable.
  The Studio still looks up a remembered pick without playback and clears it only when the per-game check
  confirms it is gone.
- **Agent side.** `rom_build` / `web_preview` results no longer carry any Studio address
  (`studio`/`studioPlayerUrl`/`studioGameId` are gone) and the engine's own preview address is not offered
  after a build. Their `nextStep`, the system prompt section and the skills say: when the game is ready for
  the user to try, call `chromatic_present_game` (do not use `desktop_preview`/`drive_preview` for the
  game); only if the user says they cannot see the emulator, open `studio.playerUrl` from
  `chromatic_present_game` with `desktop_preview`; without desktop tools, give the user that URL.
- No openWorkspace (older desktops): a presentation opens nothing and nothing breaks; the page keeps its
  player.

## RPC (all `plugin.hermretro.<name>`)

### `games` → library
Params: none. Result:
```json
{ "ok": true, "games": [ {
    "id": "<sha1 of projectRoot, 12 hex>",
    "title": "Comet Drift",
    "projectRoot": "/abs/path",
    "kind": "gbstudio" | "gbdk",
    "state": "ready" | "changed" | "failed" | "unbuilt",
    "rom": { "path": "/abs/…gbc", "sha256": "…", "size": 131072, "builtAt": 1731400000 } | null,
    "webExport": true,
    "web": { "sha256": "…", "builtAt": 1731400000 } | null,
    "thumb": "data:image/png;base64,…" | null,
    "cover": false,
    "card": { "title": "…", … } | null,
    "layout": { "ok": true, "problems": [ { "code": "…", "path": "…", "message": "…" } ], "warnings": [ … ] },
    "install": { "source": "https://github.com/…", "url": "…", "ref": "main", "commit": "<40 hex>", "mode": "game" | "game+source", "rom": "build/game.gbc", "installedAt": 1731400000, "edited": false } | null,
    "duplicateId": [ "/home/you/hermretro/games/comet-drift-copy" ] | null,
    "displayTitle": "Comet Drift",
    "chat": { "sessionId": "…", "title": "…", "conversationId": "…", "profile": "…", "thisProfile": true } | null,
    "session": { "storedId": "…", "createdAt": 1731400000, "thisProfile": true, "profileName": null, "exists": true } | null,
    "error": "<last build error, ≤240 chars>" | null
  } ],
  "unavailable": [ "<unreadable registered game id>", … ],
  "pending": [ … ],
  "gamesDir": "/abs/…/games",
  "demo": { "id": "demo", "title": "Hello Color", "kind": "gbdk", "note": "ModRetro example" },
  "device": { "hardwareEnabled": false, "skipped": false }
}
```
`demo` is the built-in demo cartridge. It is never part of `games[]`, so the Games shelf stays the user's library.
The registry is `state_dir/games.json`, updated by the broker whenever a lane selects or builds a project (`Lane.remember` paths for `project_select`/`project_create`/`rom_build`/`web_preview`). `state` = `failed` if the last build failed, `changed` if any file under the project's sources is newer than the ROM, `unbuilt` without a ROM, else `ready`. `webExport` = `<project>/build/web/index.html` and `js/binjgb.wasm` exist. `web` describes the ROM named by the export's `gbstudio.json`, or is null if it is missing or unreadable. The rebuilt banner compares the ROM the web player loads against `web.sha256`. `layout` is `layout.check` (`backend/library/layout.py`): a problem keeps the game from being presented; a warning names something that stays local. `install` says where a game installed from a link came from (`backend/library/installs.py`), null for a game made here; `edited` is whether its files changed since. An installed game plays its ROM in the bundled player (`shell: true`, `backend/library/play.py`): its `webExport`/`web` describe that ROM, never a web export of its own, and its player URL is pinned to that ROM's SHA-256 (`rom-<sha>/index.html`; the server answers 409 once the ROM changed). A game without its source has `state` `romChanged` (Play disabled, no Build) when its checked ROM changed. Its Install on Chromatic prompt (`installPrompt`, `page/pages/games/model.js`) names the ROM, size, SHA-256, repository and commit, and claims only what the library verified for that very ROM (`install.romSha256`, or `install.testBuild` for the same ROM and commit); it goes to the game's own Build conversation (`games.chatPromptRequested`), never a new chat.

On `ok: false` the page shows the read error and retains any cached result. A nonempty `unavailable` list
shows the shelf's read notice alongside the cards that loaded. An empty library requires a successful
answer with no unreadable games.
The Build page keeps the selected ID if it appears in `unavailable`. With an older shelf that omits the field,
Build asks `game_build_status` before clearing a missing selection.

### `game_build_status` → check one game's build
Params `{ "id": "…" }`. Result `{ ok, game: { id, title, projectRoot, rom, webExport, web, shell?, install, chat, session },
device: { hardwareEnabled } }`. The result omits shelf images, card data and source state. Errors include
`NO_GAME` for confirmed removal and `UNAVAILABLE` when the library, project, or an existing export's ROM cannot be read.

### `game_thumb` → store a title screen
Params `{ "id": "…", "png": "data:image/png;base64,…" }` (≤ 64 KB). Saves `state_dir/thumbs/<id>.png`; `games` returns it from then on. Result `{ "ok": true }`.

### `player` → open the real player for a game
Params `{ "id": "…" }`. Result `{ "url": "http://127.0.0.1:<port>/<token>/<id>/index.html", "romSha256": "…", "title": "…", "skins": [{ "id", "name", "swatch" }], "skin": "…" }` (`skins`: bundled and personal skins for the inline player's finish menu; `<hermretro home>/skins/<id>/` takes precedence over the same bundled ID; `skin`: the one a player starts in) or `{ "error": "…" }` (no web export → message telling the user to build it from chat).
`{ "id": "demo" }` or `{}` opens the demo cartridge (`"demo": true` in the result): GB Studio's default browser player bundled in `player/web/` (MIT notices in `player/web/LICENSES/`) with ModRetro's `examples/hello-color/hello-color.gbc` read in place from the engine, served as `rom/hello-color.gbc`. No project is involved; its captures go to `<library dir>/captures/demo` (`captures`/`capture_image` accept `demo` too).

The backend runs one loopback HTTP server (stdlib `ThreadingHTTPServer`, `127.0.0.1`, random port, 32-byte random path token, started lazily in the gateway process, daemon thread). For `/<token>/<id>/…` it serves:
- `index.html` = the game's `build/web/index.html` with, injected:
  - in `<head>`, before anything else: the **frame shim** `player/frame-shim.js`, generated from `page/frame/` by `tools/bundle/bundle.mjs` (never edit it): in-memory `localStorage`/`sessionStorage` because the sandboxed frame has an opaque origin (the finish from `?color=`); the `document.oai.annotation` host the engine's annotation registers with; the inline view (`?view=screen|device` hides the player's own controls); the page's commands (see Page ↔ frame messages); player state, console error and focus/blur posts. `backend/player/frame.py` fills its `__DEFAULT_COLOR__`/`__COLOR_KEY__` placeholders.
  - before `js/script.js`: the engine bootstrap (`Binjgb` wrapper that sets `module.codexRuntimeSha256` and calls `installInputOwner` from `./codex-annotations/input-owner.js`) — copy it from `dist/server.js` `prepareAnnotations`.
  - before `</body>`: `<script type="application/json" id="codex-web-annotations-context">{romSha256, romPath, sourceRevision, runtimeSha256, captures:{generation}}</script>` and `<script type="module" src="./codex-annotations/bridge.js"></script>`.
- the export's own files (`js/*`, `css/*`, `rom/*`, `gbstudio.json`) read-only, path-checked to stay inside `build/web`.
- `codex-annotations/<file>.js` from the prepared engine (`<hermretro home>/.cache/engine-<version>-<manifest digest>/src/web-annotations`, falling back to `engine/src/web-annotations`), with **one text patch in `view.js`**: the plugin's skins (`backend/player/skins.py`, from the bundled and personal skin folders) replace its `DEVICE_COLORS` list, and one rule after the engine's own ordering rules keeps its colour rail in the skins' order. ModRetro's finishes are skin folders too, under their engine ids. If the list is not found, serve unpatched and log it.
- `codex-annotations/chromatic-<id>.(webp|png)` from the selected skin folder’s `skin.webp` or `skin.png`, whatever extension is asked for; nothing else (404).
- `codex-captures` POST (multipart: `kind`, `metadata`, `media`): save to `<projectRoot>/captures/<iso>-<kind>.<png|webm|mp4>` + `.json`; reply exactly `{id, kind, bytes, path, metadataPath, sha256, createdAt, url: "./codex-captures/<id>/media", metadataUrl: "./codex-captures/<id>/metadata"}`; GET those two URLs back.
  The engine's `metadata` (`engine/src/web-annotations/recording.js`): a screenshot's `{schemaVersion, source, status, mimeType, bytes, width, height, captureRequested, encodedAt}`; a video's `{schemaVersion, source, mimeType, status (complete or partial), error, bytes, width, height}` plus timing (`startRequested`, `stopEvent`, `elapsedMs`, `chunks`…) and audio fields; both get `game` (the build identity). A recording the agent started also carries `managed: {recordingId, requestedDurationMs, observedDurationMs, stopReason}` (`recording-controller.js` `metadata()`) and `x-codex-recording-*` headers, which this server ignores; the plugin stores `metadata` as sent.
- `codex-states` GET → `{ "states": [] }` (not wired yet).
- `codex-device` POST → `{generation, devices: [], rom:{sha256}, available:false, blocked:false, detecting:false}`. Installing from inside the player stays off: the Studio's own Install button sends the flash prompt to chat, where Hermes's approval gate applies. Do not proxy flashing here.
- Every response: `Access-Control-Allow-Origin: *` (the frame's origin is `null`), `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, correct MIME (`.wasm` → `application/wasm`, `.js` → `text/javascript`). Default device colour: the shim seeds `localStorage['codex-gb-studio:device-color:v1']` with the first skin unless the page passes a valid `?color=`.

### `presentations` → games the agent presented
Params `{ "since"?: number, "cursorOnly"?: boolean }` (seconds, backend clock). Result `{ "ok": true, "now": <backend time>,
"presentations": [{ "gameId", "title", "t", "note", "sessionId", "conversationId", "profile", "thisProfile" }] }`,
oldest first, at most 20, only those with `t > since`. Written by `chromatic_present_game` (registry key
`presentations`, newest 100 kept). Used by the desktop when `tool.complete` does not arrive.
Build passes `cursorOnly: true` to capture the selection time. This returns an empty list without opening the registry.

### `captures` → list
Params `{ "id": "…" }` → `{ "captures": [{ "path", "kind", "createdAt", "url" }] }` where `url` is the loopback media URL (frame-independent: `http://127.0.0.1:<port>/<token>/<id>/codex-captures/<cid>/media`).

## Page ↔ frame messages
Defined once in `page/shared/player/protocol.js` (page side `shared/player/bridge.js`, frame side `frame/commands.js`); every message is an object whose `cs` names it, and the page accepts only messages from its own frame's window.
- page → frame: `{cs:'cmd', type, …}` with `type` one of `key {key, code, down}`, `snap {id}`, `hold` (pause + suspend audio while the surface is hidden), `release`, `theme {css}`, `view {view}` (`full` | `screen` | `device`), `press {action}` (one of the player's own buttons: play, sound, restart, history, screenshot, record-video, annotate), `finish {id}`, `annotate {on}`, `mark-color {id, index, value}` (value null resets), `mark-remove {id}`, `marks-take {id}`.
- frame → page: `{cs:'focus', value}`, `{cs:'log', level, text}`, `{cs:'snap', id, url}`, `{cs:'state', ready, paused, muted, annotating, recording}`, `{cs:'marks', marks}` (inline annotate, each `{n, id, name, role, metadata, colors, original, image}`), `{cs:'marks-taken', id, image, marks}` (answers `marks-take`, then annotate ends), `{cs:'annotate', target:{name, role, metadata}, note, image}` (the full view's single pick with the in-frame note card).
- Ask HermRetro / annotate / Something's wrong: the page saves the frame through `capture_image` (`{id, png}` → `{path}` under `<project>/captures/`) and attaches it to the game's message box (in the Build page; elsewhere `host.composer.insertText`, falling back to a new chat in the studio profile) with what was marked, its metadata and the note. Nothing is sent automatically.

## Install
Games shelf and Emulator bar **Install** = send the existing "Flash a cartridge" prompt (with the game named) to that game's chat. Hardware gating and the approval prompt stay exactly as today; locked with "Needs your Chromatic" when hardware is not set up.
