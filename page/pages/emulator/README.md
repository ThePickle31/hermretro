# Emulator

**Shows:** ModRetro's real player. The player itself is the shell's (it stays loaded while other pages are
shown); this page's `Page` (`emulator-page.js`) adds the bar above it with the rebuilt banner and captures
(`emulator-bar.js`) and the notice;
the descriptor adds the row under it (`beside-chat/row.js`). `beside-chat/` is the emulator tab beside the chat that opens when
the agent presents a game. The nav segment carries a live dot while a game is loaded elsewhere (`Badge`).
Padding `flush`, no footer.

**Tabs:** none.

**Events:** emits `emulator.presented` `{ gameId, seq, note, t }` each time the agent presents a game
(`beside-chat/present.js`). Listens to none.

**Slots:** declares `emulator.barActions`: buttons in the bar after the keyboard light, for the user's own game
(not the demo), rendered both on the Emulator page and in the emulator tab beside the chat
(`beside-chat/tab.js`). Props `{ ctx, game, hardwareOn }`, plus `go(pageId)` on the Emulator page only (the tab
beside the chat has no shell): a contribution checks `go` before using it. Games fills it with Install.

**Starts with the plugin** (`register`): `watchBuilds(ctx)`, which opens the tab beside the chat on a
presentation and refreshes open players after builds.

**Uses from other pages:** `#pages/build/index.js` (is a session a Build conversation, which game Build shows,
tool results).

**Tests:** `tests/page/page-emulator.test.mjs` (the Emulator page), `tests/page/page-emulator-side.test.mjs` (the tab beside the chat),
`tests/page/registry.test.mjs` (also: an `emulator.barActions` contribution gets `go` on the page, not beside the
chat).

## Adding a tab here

Make a folder `page/pages/emulator/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/emulator/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`docs/dev/STUDIO-PAGES.md`, "Adding to the page".
