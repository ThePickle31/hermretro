# Home

**Shows:** the hero with the Hermes bust, then three columns: Continue (the last game, or the next setup step
while setup is unfinished), Start something (quick starts, off until setup is done) and Studio (rows of `dl.cs-stat`: Setup, steps
verified done of those counted, from the setup steps; Profile, the `status` RPC's `profile`; Toolchain, the
setup toolchain state from `status` and `doctor`; Chromatic, `status`'s `hardware_enabled` and the stored
"emulator only" choice; Games, the number the `games` RPC lists; then links to Setup and Games). Main component: `home-page.js`; descriptor: `index.js`.

**Tabs:** none.

**Events:** emits none, listens to none.

**Slots:** declares none, contributes none.

**Uses from other pages** (their front doors): `#pages/games/index.js` (game meta, latest game, state tag),
`#pages/prompts/index.js` (the prompt library), `#pages/setup/index.js` (step names, toolchain state).

**Tests:** `tests/page/page-games.test.mjs` (Home fed by the games RPC), `tests/page/page-setup.test.mjs` (Home
during setup), `tests/page/registry.test.mjs` (its descriptor).

## Adding a tab here

Make a folder `page/pages/home/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/home/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`docs/dev/STUDIO-PAGES.md`, "Adding to the page".
