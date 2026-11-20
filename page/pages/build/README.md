# Build

**Shows:** one game, one conversation with the agent (`build-page.js`): the game switcher in the header, the
transcript (`transcript/`), the message box (`composer/`), the game playing inside the reply (`player/`), the
picture viewer (`viewer/`), the image cache (`assets/`) and the game drawn behind New Game (`attract/`). `chat/` holds the conversations, the gateway events
and the actions. While the hermretro profile is missing it shows `studio-needed.js` instead (the choice is the page's
`Page`, `build-entry.js`). Descriptor: `index.js` (padding `build`, no footer, its stylesheet last).

**Tabs:** none (its areas are subfolders, not tabs).

**Events:** emits none. Listens to `games.coverRequested` (opens that game with the cover prompt in its
message box, not sent) and `emulator.presented` (plays the presented game in its conversation).

**Slots:** declares none, contributes none.

**Exposes** (`index.js`): `isBuildSession(runtimeId)`, `buildShowing()` and the tool-result helpers
`toolResultObject`, `unwrapCalls`, for the Emulator page's tab beside the chat.

**Starts with the plugin** (`register`): `watchBuildChats(ctx)`, the gateway listeners that keep a conversation
streaming while the page is closed.

**Uses from other pages:** `#pages/games/index.js` (game states), `#pages/setup/index.js` (creating the studio
profile).

**Tests:** `tests/page/page-build.test.mjs`, `tests/page/page-build-turns.test.mjs`,
`tests/page/build-player.test.mjs`, `tests/page/registry.test.mjs` (its listeners), `tests/page/attract.test.mjs`
(the New Game level, run headless), `tests/page/attract-run.test.mjs` (running it in the page).

## The New Game level (`attract/`)

Behind the New Game form the page draws a Game Boy Color style platformer where the Nous Girl plays one fixed level
by herself (no ROM: a canvas at native pixels, scaled x2 with pixelated scaling, dimmed to half strength with a pool
of the page colour behind the composer). The elements marked `data-plat` in `new-game.js` (title, composer, the two
choices) are platforms in it; the level is rebuilt around them when the area or one of them changes size, and its
sky follows the theme (day on a light page, night on a dark one). It ignores clicks and keys, is hidden from screen
readers, stops drawing while the window is hidden, and shows one still frame under reduced motion.

| File | What it is |
|---|---|
| `index.js` | `AttractLevel`: the canvas and its overlay, started with the browser's functions |
| `run.js` | Running it: measuring the platforms, the 60 Hz loop, theme, rebuilding on resize and on the form's scroll |
| `world.js` | `World`: the game without drawing (build, step); pilot, actors and drawing are mixed in |
| `physics.js` | Units (24-px tiles), her box and jump, the collider grid, one physics step, the seeded random |
| `level.js` | The level builder: ground, pits and movers, pipes, stairs, the lattice of rows, cannons, flag |
| `paths.js` | Surfaces, every simulated jump between them, repairs, shortest paths |
| `coins.js` | Coin groups and jump arcs, spread apart, only where she can reach |
| `pilot.js` | How she plays: goals, safe jumps, stomps, re-planning, the watchdog |
| `actors.js` | Enemies, bats, cannon shots, blocks, power-ups, particles |
| `draw.js`, `hud.js`, `sprites.js` | Drawing: prerendered tiles, sprites, the HUD and its pixel font |
| `girl.js`, `art.js`, `art-enemies.js`, `palettes.js` | The pixel art (one character per pixel) and the day and night palettes |
| `attract.css.js` | The layer, the dimming and the spotlight |

## Adding a tab here

Make a folder `page/pages/build/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/build/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`docs/dev/STUDIO-PAGES.md`, "Adding to the page".
