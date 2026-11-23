# Emulator

**Shows:** ModRetro's real player. The player itself is the shell's (it stays loaded while other pages are
shown); this page's `Page` (`emulator-page.js`) adds the bar above it with the rebuilt banner and captures
(`emulator-bar.js`) and the notice;
the captures strip there (`Captures` in `emulator-bar.js`, shown while the bar's captures toggle is open, refetched
every 5 s) lists the `captures` RPC (`backend/library/rpcs.py`, which reads `list_captures` in
`backend/player/server.py`: the game's `captures/` folder, newest first by `createdAt`);
the descriptor adds the row under it (`beside-chat/row.js`). `beside-chat/` is the emulator tab beside the chat that opens when
the agent presents a game. The nav segment carries a live dot while a game is loaded elsewhere (`Badge`).
Padding `flush`, no footer.

**Tabs:** none.

**Events:** emits `emulator.presented` `{ gameId, seq, note, t }` each time the agent presents a game
(`beside-chat/present.js`). Listens to `setup.demoRequested` (opens the bundled demo in the tab beside the chat).

**Slots:** declares `emulator.barActions`: buttons in the bar after the keyboard light, for the user's own game
(not the demo), rendered both on the Emulator page and in the emulator tab beside the chat
(`beside-chat/tab.js`). Props `{ ctx, game, hardwareOn }`, plus `go(pageId)` on the Emulator page only (the tab
beside the chat has no shell): a contribution checks `go` before using it. Games fills it with Install.

**Starts with the plugin** (`register`): `watchBuilds(ctx)`, which opens the tab beside the chat on a
presentation and refreshes open tabs after builds. Both players check their own game through `game_build_status`.

**Uses from other pages:** `#pages/build/index.js` (is a session a Build conversation, which game Build shows,
tool results).

**Tests:** `tests/page/page-emulator.test.mjs` (the Emulator page), `tests/page/page-emulator-side.test.mjs` (the tab beside the chat),
`tests/page/slots.test.mjs` (the slot's props: `go` on the Emulator page, not beside the chat),
`tests/page/registry.test.mjs` (slot declarations and contribution wiring).

## When the player stays black

Errors inside the player frame reach the app's developer console as `[Chromatic player] <text>` warnings
(`page/shared/player/bridge.js`, forwarded by `page/frame/sandbox.js`). The stage (`page/app/player/stage.js`)
says what it is waiting for: "Starting the player for <game>…" while the `player` RPC runs, "The player could not
start" with Refresh when that RPC failed, and with Build it in chat when the game has no web export. A frame that
loads but stays black: compare the game's `webExport` and `web.sha256` (the `game_build_status` RPC) with the `player` RPC's
`romSha256`; when they differ the bar offers "Load the new build" (`emulator-bar.js`). More in
`.agents/skills/hermretro-dev-debugging/references/debugging.md`, "Common symptoms".

## Adding a tab here

Make a folder `page/pages/emulator/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/emulator/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`.agents/skills/hermretro-dev-page/references/adding.md`, "Adding to the page".
