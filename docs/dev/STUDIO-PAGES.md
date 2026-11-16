# Studio pages: build contract

The user approved clickable mockups (`~/projects/chromatic-studio-mockups/`) for a multi-page
hermretro and asked to build all of them. This file is the shared contract between the
page (`desktop/plugin.js`) and the backend (`adapter/`). Both halves must match it exactly.

## Pages (one segmented control in the header, always in the same place)

`Home · Setup · Prompts · Games · Emulator` (Chromatic and Guide are not designed yet: do not add them).

| Page | Approved design | Mockup file (source template) |
|---|---|---|
| Home | E · Segmented nav, home variant 1 "Hero + band" (hero with the Hermes bust, then three columns Continue / Start something / Studio). While setup is incomplete quick starts are disabled ("after setup") and "Continue setup" leads with a 7-step bar and the next step's name; the hero and the Studio list both count done steps ("n of 7 done", as the Setup rail does). | `src/nav.template.html` (`ui.dir='E'`, `ui.home='1'`) |
| Setup | Today's Atelier wizard (step rail + current step, same rules as now) with the **flying Chromatic** on the right on every step: body + one wing drawn twice, wings flap ~0.9 s, whole thing bobs and drifts, tilted (`perspective rotateY(-14deg) rotateX(6deg) rotateZ(16deg) scale(.82)`), soft shadow, still pose under reduced motion. Setup tab shows a small dot while incomplete. | `src/setup-page.template.html` variant 5 (`.flyer` CSS) |
| Prompts | **Reader**: list with search + ↑/↓ on the left grouped Plan / Create / Play / Polish / On your Chromatic; chosen prompt in the middle as an editable textarea, folder + project-name inputs for prompts with `{folder}`/`{name}`; actions **Start a new chat**, **Add to current chat**, **Copy**, "Reset text"; a "What happens" note; Hermes art on the right. Hardware prompts locked without a Chromatic ("Needs your Chromatic" + Set up my Chromatic). | `src/prompts-page.template.html` variant 2 |
| Games | **Shelf**: grid of the HermRetro cartridge (`desktop/art/cart-hermretro.png`, 299×340, dark grey, HERMRETRO on its top plate) with the game's title screen filling the label window (`left 13.38%, top 28.82%, width 73.24%, height 56.76%`, `border-radius 1.5cqw`, no border). Under each: title, state tag, meta (kind · size · built), actions Play (→ Emulator page), Install (see below), open its chat. A faded "Blank cartridge" slot = New game. Chromatic status strip at the top. Empty library page. | `src/games-page.template.html` (`.mcart.real`) |
| Emulator | ModRetro's **real player** in a `SandboxedFrame`, served by the backend (below), always: with nothing playable of the user's it loads the **demo cartridge** (Hello Color; no chip or extra button for it, and no Install). A failed or missing `player` RPC shows a compact notice with the reason and Refresh above an empty device area (for -32601: reload the plugin, Capabilities › Plugins). Above it a thin bar with only the player's controls: keyboard-focus indicator, Install, Ask Hermes, Captures drawer, Full screen (no game tabs: Play on the Games shelf or Home picks the game). Below 700 px of page width the bar stops wrapping, and below 560 px its buttons keep only their icons, each with a tooltip; the header likewise stays one row (tighter segments, icon-only Refresh, and below 600 px no wordmark). "Hermes rebuilt <game> · Load the new build" banner when the game's web ROM (`web.sha256`) changed after the frame loaded. Under the player: a one-line hint ("Hermes shows your game beside the chat when it is ready for you to try.") and the user's own **Open beside the chat** button (see below). Default device finish **Hermes Edition · Midnight**. | `src/emulator-page.template.html` variant 5 + `src/player/*` |

## The emulator beside the chat

User request: show **our** emulator (the Emulator page's bar + ModRetro's real player from `player_server`,
Hermes Edition Midnight) beside the chat instead of the engine's page in the in-app browser — and only
when the agent is ready to present the game after making it, never for the whole of development
(user requirement: "it should not be there the entire time"). Builds open nothing.

- **Agent tool `chromatic_present_game`** (plugin-owned, toolset `chromatic`, registered next to
  `chromatic_studio_device_cli`; not an engine tool, not in the pinned manifest). Params
  `{note?: string ≤300, project?: absolute folder}`. The project is `project` when given, else the chat's
  lane selection (broker `activity` op, memory only, never starts the broker), else the library game whose
  chat link is this conversation. It requires a fresh web export (`library.export_freshness`: `build/web`
  exists and is not older than the last ROM build — the registry's `lastBuild.t`, else the newest native
  ROM under `build/` — where the export's time is the later of its ROM file and `lastWebExport.t`, which the
  broker records on every successful `web_preview` open, because the engine reuses an export whose sources
  did not change without rewriting its files; a failed build after it also counts as stale); otherwise `{ok:false, code:"BUILD_FIRST", error, guidance}` telling the
  agent to run `chromatic_rom_build`. On success it records the presentation in the games registry
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
  completions only bump a counter so open players re-read `games` at once.
- **Fallback.** The gateway sends `tool.complete` only while the chat's tool progress is not `off`, so every
  `message.complete` (600 ms later) calls RPC `presentations` with `since` = the backend's `now` from the
  previous answer minus 1 s (first call: plugin start minus 5 s) and presents the newest one per game.
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
- **Rebuilt check.** Both surfaces compare the player's `romSha256` with `game.web.sha256` (the web
  export's own ROM; the native build's bytes differ), falling back to `rom.sha256` on older backends.
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
{ "games": [ {
    "id": "<sha1 of projectRoot, 12 hex>",
    "title": "Comet Drift",
    "projectRoot": "/abs/path",
    "kind": "gbstudio" | "gbdk",
    "state": "ready" | "changed" | "failed" | "unbuilt",
    "rom": { "path": "/abs/…gbc", "sha256": "…", "size": 131072, "builtAt": 1731400000 } | null,
    "webExport": true,
    "web": { "sha256": "…", "builtAt": 1731400000 } | null,
    "thumb": "data:image/png;base64,…" | null,
    "chat": { "sessionId": "…", "title": "…" } | null,
    "error": "<last build error, ≤240 chars>" | null
  } ],
  "demo": { "id": "demo", "title": "Hello Color", "kind": "gbdk", "note": "ModRetro example" },
  "device": { "hardwareEnabled": false, "skipped": false }
}
```
`demo` is the built-in demo cartridge. It is never part of `games[]`, so the Games shelf stays the user's library.
The registry is `state_dir/games.json`, updated by the broker whenever a lane selects or builds a project (`Lane.remember` paths for `project_select`/`project_create`/`rom_build`/`web_preview`). `state` = `failed` if the last build failed, `changed` if any file under the project's sources is newer than the ROM, `unbuilt` without a ROM, else `ready`. `webExport` = `<project>/build/web/index.html` and `js/binjgb.wasm` exist. `web` describes the ROM inside that export (named by its `gbstudio.json`): the player loads that file, which is its own compilation and not byte-identical to `rom`, so the rebuilt banner compares against `web.sha256`.

### `game_thumb` → store a title screen
Params `{ "id": "…", "png": "data:image/png;base64,…" }` (≤ 64 KB). Saves `state_dir/thumbs/<id>.png`; `games` returns it from then on. Result `{ "ok": true }`.

### `player` → open the real player for a game
Params `{ "id": "…" }`. Result `{ "url": "http://127.0.0.1:<port>/<token>/<id>/index.html", "romSha256": "…", "title": "…" }` or `{ "error": "…" }` (no web export → message telling the user to build it from chat).
`{ "id": "demo" }` or `{}` opens the demo cartridge (`"demo": true` in the result): GB Studio's default browser player bundled in `player/web/` (MIT notices in `player/web/LICENSES/`) with ModRetro's `examples/hello-color/hello-color.gbc` read in place from the engine, served as `rom/hello-color.gbc`. No project is involved; its captures go to `<library dir>/captures/demo` (`captures`/`capture_image` accept `demo` too).

The backend runs one loopback HTTP server (stdlib `ThreadingHTTPServer`, `127.0.0.1`, random port, 32-byte random path token, started lazily in the gateway process, daemon thread). For `/<token>/<id>/…` it serves:
- `index.html` = the game's `build/web/index.html` with, injected:
  - in `<head>`, before anything else: the **frame shim** (in-memory `localStorage`/`sessionStorage` because the sandboxed frame has an opaque origin; `document.oai.annotation` host API that posts annotate results to the parent; a `message` listener for `{cs:'cmd', type:'key'|'snap'|'hold'|'release'|'theme'}`; console error forwarding; focus/blur posts). Port it from the mockup `src/player/build_player_frame.mjs` (shim + annotation blocks) — not the fetch interception, which is unnecessary over real http.
  - before `js/script.js`: the engine bootstrap (`Binjgb` wrapper that sets `module.codexRuntimeSha256` and calls `installInputOwner` from `./codex-annotations/input-owner.js`) — copy it from `dist/server.js` `prepareAnnotations`.
  - before `</body>`: `<script type="application/json" id="codex-web-annotations-context">{romSha256, romPath, sourceRevision, runtimeSha256, captures:{generation}}</script>` and `<script type="module" src="./codex-annotations/bridge.js"></script>`.
- the export's own files (`js/*`, `css/*`, `rom/*`, `gbstudio.json`) read-only, path-checked to stay inside `build/web`.
- `codex-annotations/<file>.js` from the prepared engine (`deps/engine/dist/web-annotations`, falling back to `engine/modretro-chromatic/dist/web-annotations`), with **one text patch in `view.js`**: prepend the four Hermes Edition entries to `DEVICE_COLORS` (`hermes-midnight` "Hermes Edition · Midnight" `#15171c`/`#e6edf3`, `hermes-blue` "Hermes Edition · Nous Blue" `#0053fd`/`#ffffff`, `hermes-white` "Hermes Edition · White" `#f2f5fc`/`#1f2328`, `hermes-clear` "Hermes Edition · Clear Blue" `#cfdcff`/`#1f2328`). If the anchor text is missing, serve unpatched and log it.
- `codex-annotations/chromatic-<color>.(webp|png)` from `deps/engine/assets/devices/`, and `chromatic-hermes-*.webp` from the plugin's `player/devices/`.
- `codex-captures` POST (multipart: `kind`, `metadata`, `media`): save to `<projectRoot>/captures/<iso>-<kind>.<png|webm|mp4>` + `.json`; reply exactly `{id, kind, bytes, path, metadataPath, sha256, createdAt, url: "./codex-captures/<id>/media", metadataUrl: "./codex-captures/<id>/metadata"}`; GET those two URLs back.
- `codex-states` GET → `{ "states": [] }` (not wired yet).
- `codex-device` POST → `{generation, devices: [], rom:{sha256}, available:false, blocked:false, detecting:false}`. Installing from inside the player stays off: the Studio's own Install button sends the flash prompt to chat, where Hermes's approval gate applies. Do not proxy flashing here.
- Every response: `Access-Control-Allow-Origin: *` (the frame's origin is `null`), `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, correct MIME (`.wasm` → `application/wasm`, `.js` → `text/javascript`). Default device colour: the shim seeds `localStorage['codex-gb-studio:device-color:v1'] = 'hermes-midnight'` unless the page passes `?color=`.

### `presentations` → games the agent presented
Params `{ "since"?: number }` (seconds, backend clock). Result `{ "ok": true, "now": <backend time>,
"presentations": [{ "gameId", "title", "t", "note", "sessionId", "conversationId", "profile", "thisProfile" }] }`,
oldest first, at most 20, only those with `t > since`. Written by `chromatic_present_game` (registry key
`presentations`, newest 100 kept). Used by the desktop when `tool.complete` does not arrive.

### `captures` → list
Params `{ "id": "…" }` → `{ "captures": [{ "path", "kind", "createdAt", "url" }] }` where `url` is the loopback media URL (frame-independent: `http://127.0.0.1:<port>/<token>/<id>/codex-captures/<cid>/media`).

## Page ↔ frame messages
- frame → page: `{cs:'focus', value}`, `{cs:'log', level, text}`, `{cs:'annotate', target:{name, role, metadata}, note, image:'data:image/png…'}`, `{cs:'snap', id, url}`.
- page → frame: `{cs:'cmd', type:'key', key, code, down}`, `{type:'snap', id}`, `{type:'hold'}` (pause + suspend audio when the Emulator page is hidden), `{type:'release'}`, `{type:'theme', css}`.
- Ask Hermes / annotate: the page saves the image through `game_thumb`-like RPC `capture_image` (params `{id, png}` → `{path}` under `<project>/captures/`), then puts text into the game's chat composer (`host.composer.insertText`, falling back to a new chat in the studio profile): what was selected, its metadata, the note, and `Screenshot: <path>` so the agent can open it. Nothing is sent automatically.

## Install
Games shelf and Emulator bar **Install** = send the existing "Flash a cartridge" prompt (with the game named) to that game's chat. Hardware gating and the approval prompt stay exactly as today; locked with "Needs your Chromatic" when hardware is not set up.

## Constraints that apply to both halves
- `desktop/plugin.js` stays plain ESM (`jsx`/`jsxs`), imports only `@hermes/plugin-sdk`, `react`, `react/jsx-runtime`, scoped CSS under `.cs-page`, every colour a `var(--ui-*)`, and the file stays under 512 KiB. Small art goes through `tools/embed_art.py`; device skins are served by the backend only.
- Never edit `engine/`. Never touch hardware. No wording that trips the install scanner (see the trigger list in tools/skills_guard.py; never quote the triggers in our own files).
- Verify: `python -m unittest discover -s tests`, `node --check desktop/plugin.js`, `node tests/desktop/wizard_test.mjs`, the preview build, and `python tests/acceptance/broker_acceptance.py` after adapter changes.
