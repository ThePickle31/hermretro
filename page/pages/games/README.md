# Games

**Shows:** the shelf of cartridges from the `games` RPC (`games-page.js`), one card each with its split
action and menu (`game-card.js`; the cartridge itself is `cartridge.js`, exported for Build's New Game shelf), the games folder, and the hardware chip. `model.js` is the library model.

**Tabs:** none.

**Events:** emits `games.coverRequested` `{ game, prompt }` when Make cover art (or Finish card) is picked; the
page then goes to Build, which listens. Listens to none.

**Slots:** declares `games.cardMenu`: extra items at the end of a game's arrow menu, props
`{ ctx, game, hardwareOn, item(icon, label, run, { disabled, why }) }` (return `item(...)`; starts empty).
Contributes `InstallButton` to `emulator.barActions` (Install on Chromatic in the Emulator page's bar).

**Exposes** (`index.js`): `GAME_STATES`, `gameMeta`, `latestGame`, `StateTag`.

**Uses from other pages:** `#pages/prompts/index.js` (the flash prompt).

**Tests:** `tests/page/page-games.test.mjs`, `tests/page/page-build-turns.test.mjs` (the game card),
`tests/page/registry.test.mjs` (its event and slots).

## Adding a tab here

Make a folder `page/pages/games/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/games/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`docs/dev/STUDIO-PAGES.md`, "Adding to the page".
