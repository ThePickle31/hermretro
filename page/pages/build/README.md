# Build

**Shows:** one game, one conversation with the agent (`build-page.js`): the game switcher in the header, the
transcript (`transcript/`), the message box (`composer/`), the game playing inside the reply (`player/`), the
picture viewer (`viewer/`), the image cache (`assets/`) and the game drawn behind New Game (`attract/`) with the shelf of games being worked on standing on its floor (`cart-shelf.js`). `chat/` holds the conversations, the gateway events
and the actions. While the hermretro profile is missing it shows `studio-needed.js` instead (the choice is the page's
`Page`, `build-entry.js`). Descriptor: `index.js` (padding `build`, no footer, its stylesheet last). Its games are the `games` RPC's game
objects ([CONTRACT.md, "The game object"](../../../docs/dev/CONTRACT.md#the-game-object)). A game's conversation is
`BUILD_CHATS.get()[game.session.storedId]` (`chat/store.js`, inside this page); its `busy` is true while a turn runs.

**Tabs:** none (its areas are subfolders, not tabs).

**Events:** emits none. Listens to `games.coverRequested` (opens that game with the cover prompt in its
message box, not sent) and `emulator.presented` (plays the presented game in its conversation).

**Slots:** declares none, contributes none.

**Exposes** (`index.js`): `isBuildSession(runtimeId)`, `buildShowing()` and the tool-result helpers
`toolResultObject`, `unwrapCalls`, for the Emulator page's tab beside the chat.

**Starts with the plugin** (`register`): `watchBuildChats(ctx)`, the gateway listeners that keep a conversation
streaming while the page is closed.

**Uses from other pages:** `#pages/games/index.js` (game states, and the `Cartridge` of the New Game shelf), `#pages/setup/index.js` (creating the studio
profile).

**Page state** (`shell.ctx.storage`, [STUDIO-PAGES.md, "Adding to the page"](../../../docs/dev/STUDIO-PAGES.md#adding-to-the-page)): `buildSelected`, `buildModel`, `inlinePlayer` and `playtest`.

**Tests:** `tests/page/page-build.test.mjs`, `tests/page/page-build-turns.test.mjs`, `tests/page/page-build-builds.test.mjs` (the Builds menu),
`tests/page/page-build-speed.test.mjs` (the model picker's Speed), `tests/page/build-player.test.mjs`, `tests/page/registry.test.mjs` (its listeners), `tests/page/attract.test.mjs`
(the New Game level, run headless), `tests/page/attract-run.test.mjs` (running it in the page),
`tests/page/page-build-shelf.test.mjs` and `tests/page/cart-shelf.test.mjs` (the New Game shelf).

## The header

`build-page.js` builds the header (`header.cs-b-head`) from these parts (and a Discard button for a game not made yet):

| Part | File | Classes |
|---|---|---|
| The game's title and the game switcher (its menu of games, the library view, the right-click menu, and the "N needs you" / "N working" / new-reply marks for other games) | `switcher.js` `BuildSwitcher` (`switcherEntries` gives its rows) | `.cs-b-sw*`, `.cs-b-ctx`, `.cs-b-needs`, `.cs-b-others`, `.cs-b-otherdot` |
| The status pill (working, up to date, edited since a build, failed, no builds yet) | `builds-menu.js` `BuildPill` | `.cs-b-pill*` |
| The Builds menu (the conversation's builds, Show and Restore) | `builds-menu.js` `BuildsMenu` | `.cs-b-brow*`, `.cs-b-sw-pop.cs-b-builds` |

Their styles are in `header.css.js` (`HEADER_CSS`; narrow-window and reduced-motion changes in
`build-responsive.css.js`); the header row itself, `.cs-b-head`, is in `transcript/transcript.css.js`.
`build-page.js` is near the size limit (`tests/repo/test_layout.py`: a warning above 400 lines, a failure above 600),
so a new header part goes in its own file in `page/pages/build/`, with a row in the table above.

A build's `startAt`/`endAt` (`buildHistory`, `transcript/turns.js`) are milliseconds: a message's `timestamp` (Unix
seconds) × 1000 (`chat/history.js`), or `Date.now()` for a live turn. The `builds` RPC's snapshot `at` and `builds` times
are milliseconds too, and `snapshotFor` (`builds-menu.js`) gives a build the latest one from 2 s before its turn started
(an hour before its end when the start is unknown) to 5 s after it ended; without one, Restore stays disabled.

## The New Game level (`attract/`)

Behind the New Game form the page draws a Game Boy Color style platformer where the Nous Girl plays one fixed level
by herself (no ROM: a canvas at native pixels, scaled x2 with pixelated scaling, dimmed). The form takes no part in
it: the composer and the two choices are frosted glass over the level, and she plays behind them. The level is
rebuilt when the area changes size, and its sky follows the theme (day on a light page, night on a dark one). It ignores clicks and keys, is hidden from screen
readers, stops drawing while the window is hidden, and shows one still frame under reduced motion.

| File | What it is |
|---|---|
| `index.js` | `AttractLevel`: the canvas, started with the browser's functions |
| `run.js` | Running it: the 60 Hz loop, theme, rebuilding on resize |
| `world.js` | `World`: the game without drawing (build, step); pilot, actors and drawing are mixed in |
| `physics.js` | Units (24-px tiles), her box and jump, the collider grid, one physics step, the seeded random |
| `level.js` | The level builder: ground, pits and movers, pipes, stairs, the lattice of rows, cannons, flag |
| `paths.js` | Surfaces, every simulated jump between them, repairs, shortest paths |
| `coins.js` | Coin groups and jump arcs, spread apart, only where she can reach |
| `pilot.js` | How she plays: goals, safe jumps, stomps, re-planning, the watchdog |
| `actors.js` | Enemies, bats, cannon shots, blocks, power-ups, particles |
| `draw.js`, `hud.js`, `sprites.js` | Drawing: prerendered tiles, sprites, the HUD and its pixel font |
| `girl.js`, `art.js`, `art-enemies.js`, `palettes.js` | The pixel art (one character per pixel) and the day and night palettes |
| `attract.css.js` | The layer, the dimming and the frosted glass of the form in front |

## Adding a tab here

The page has no tabs yet, so the first is `python tools/retrodev new tab build main --from-page --label Chat` (its
current content becomes that tab; the id `chat` is taken by the conversations folder `chat/`). After that, make a folder `page/pages/build/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/build/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`docs/dev/STUDIO-PAGES.md`, "Adding to the page".
