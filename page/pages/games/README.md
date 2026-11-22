# Games

**Shows:** the shelf of cartridges from the `games` RPC (`games-page.js`), one card each with its split
action and menu (`game-card.js`; the cartridge itself is `cartridge.js`, exported for Build's New Game shelf), the games folder, and the hardware chip. `model.js` is the library model.
The cards read these fields of each game as the `games` RPC returns it (every field: [.agents/skills/hermretro-dev-architecture/references/contract.md, "The game object"](../../../.agents/skills/hermretro-dev-architecture/references/contract.md#the-game-object)):
`id`, `title`, `displayTitle`, `state` (the status and the split action), `error`, `thumb` (the label art),
`cover` (whether `thumb` is the cover art), `card` (`tagline`, `description`, `genres`, `complete`), `rom`,
`webExport`, `chat` and `projectRoot`. A game whose `thumb` is the title screen (`cover` false) gets the
"No cover" tag (`.nocover`, in `cartridge.js`, styled in `games.css.js`); the same `Cartridge` draws Build's New
Game shelf, so a change to it shows on both pages.

**Tabs:** none.

**Events:** emits `games.coverRequested` `{ game, prompt }` when Make cover art (or Finish card) is picked, so
Build can draft the message. The Games page navigates to the selected game or to the New Game form. Listens to none.

**Slots:** declares `games.cardMenu`: extra items at the end of a game's arrow menu, props
`{ ctx, game, hardwareOn, item(icon, label, run, { disabled, why }) }` (return `item(...)`; starts empty).
Contributes `InstallButton` to `emulator.barActions` (Install on Chromatic in the Emulator page's bar).

**Exposes** (`index.js`): `GAME_STATES`, `gameMeta`, `latestGame`, `StateTag`.

**Uses from other pages:** none.

**Tests:** the Games card is covered in two files: `tests/page/page-games.test.mjs` (the cards' states, the split
Play/Fix button, the arrow menu with its contributed items, and New Game navigation) and `tests/page/page-build-turns.test.mjs` (the card's
cover art, display title, tagline and genres, and Make cover art for a game without a card);
`tests/page/registry.test.mjs` (its events and slots).

## Adding a tab here

Make a folder `page/pages/games/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/games/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`.agents/skills/hermretro-dev-page/references/adding.md`, "Adding to the page".
