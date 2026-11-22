# backgrounds

**Shows:** what pages draw behind them. Each background is one folder here with an `index.js` exporting its
descriptor `{ id, css, start }`; `index.js` lists them, one line each. A page shows one by rendering
`jsx(Background, { id })` (`#app/background.js`); the shell's layer (`app/background-layer.js`) draws it behind the
page area, keeps it running when the next page asks for the same one, and keeps it paused while no page does.
How to make one: `.agents/skills/hermretro-dev-backgrounds/SKILL.md`.

**Boundaries:** a background imports only its own folder and `#shared/`; only `app/` imports this registry, and
pages choose a background by its id (`tools/bundle/lint-rules.mjs`).

**Tests:** `tests/page/background-layer.test.mjs` (the registry and the layer), `tests/page/platformer.test.mjs`
(the platformer run headless), `tests/page/platformer-run.test.mjs` (running it in the page area),
`tests/page/cart-shelf.test.mjs` (the flat ground under the Build page's shelf).

## The platformer (`platformer/`)

A Game Boy Color style platformer where the Nous Girl plays one level by herself (no ROM: a canvas at native pixels,
scaled x2 with pixelated scaling, dimmed). It is built for the page area's size and rebuilt only when that size, or
the flat ground the page asks for (`data-at-flat`), changes; its sky follows the theme (day on a light page, night on
a dark one). It tells the page where its ground is (`--cs-at-ground`) and the page colour (`--cs-at-bg`), stops
drawing while the window or its layer is hidden, and shows one still frame under reduced motion. The Build page
shows it behind New Game.

| File | What it is |
|---|---|
| `index.js` | `PLATFORMER`: the descriptor; `start` puts its canvas in the layer and runs it |
| `run.js` | Running it: the 60 Hz loop, theme, rebuilding when the area's size changes |
| `world.js` | `World`: the game without drawing (build, step); pilot, actors and drawing are mixed in |
| `physics.js` | Units (24-px tiles), her box and jump, the collider grid, one physics step, the seeded random |
| `level.js` | The level builder: ground, pits and movers, pipes, stairs, the lattice of rows, cannons, flag |
| `paths.js` | Surfaces, every simulated jump between them, repairs, shortest paths |
| `coins.js` | Coin groups and jump arcs, spread apart, only where she can reach |
| `pilot.js` | How she plays: goals, safe jumps, stomps, re-planning, the watchdog |
| `actors.js` | Enemies, bats, cannon shots, blocks, power-ups, particles |
| `draw.js`, `hud.js`, `sprites.js` | Drawing: prerendered tiles, sprites, the HUD and its pixel font |
| `girl.js`, `art.js`, `art-enemies.js`, `palettes.js` | The pixel art (one character per pixel) and the day and night palettes |
| `platformer.css.js` | The canvas: pixel-sharp, dimmed |
