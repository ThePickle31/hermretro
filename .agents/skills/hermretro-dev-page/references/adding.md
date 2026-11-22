# Adding to the page

Each of these touches one folder plus at most one registry line. `tests/page/registry.test.mjs` checks the
registry, and every descriptor is checked when the bundle loads (`app/registry.js`): a mistake fails the page
tests with the exact problem.

**Page state.** A setting a page keeps across visits (a choice, the last folder) goes in
`shell.ctx.storage.get(key, fallback)` / `shell.ctx.storage.set(key, value)`; every page shares one set of keys, so
pick one no other page uses (`buildSelected`, `buildModel`). Page tests seed and read them as `scenario.storage`
(`tests/page/harness.mjs`). To navigate from Games without depending on a storage write, `shell.go('build', selection)`
passes the requested game ID (or `'new'`). `shell.buildSelection` survives a backend disconnect within the same Build
visit; Build updates it through `shell.selectBuild` and saves the selection if possible. The visit also keeps records of
locally started New Game conversations (`shell.buildPending`) so a cached library response cannot drop the active chat.

## A page

Make `page/pages/<page>/` with `index.js` exporting `export const <PAGE>_PAGE = { id: '<page>',
label: '<Label>', Page }`, where `Page({ shell })` renders it from `shell` (the data and actions every page
shares, built in `app/studio-page.js`: `ctx`, `go(id)`, `status`, `viaProfile`, `steps`, `games`, `play(id)`,
`player`…; `viaProfile` is the profile the shell's own queries go to when it is not the app's, else `null`: key
a page's own queries on it, as the shell does).
Add one line to `page/pages/index.js` (import it, and put it in `PAGES` where its nav segment goes), and a
`README.md` (copy `page/pages/games/README.md`'s sections).
Optional fields: `Badge({ nav })`, `pad`, `BelowPlayer`, `css`, `register(ctx)`, `events`, `listens`, `slots`,
`contributes` (all listed at the top of `app/registry.js`). Nothing in `app/` changes. The shell draws its one
player (`PlayerStage` in `app/studio-page.js`, shown on the Emulator page) full width in the page's column, after
`Page` and before `BelowPlayer`: a page puts its content above the player (`Page`) or below it (`BelowPlayer`,
which needs `pad`); content beside the player needs a change to that shell. Add the page to the registry (`page/pages/index.js`) and to
the registry test's nav list (`tests/page/registry.test.mjs`) in the same place.

## Reference content

Reference content (how something works, rather than something to do) goes on the page it is about, not on a
page of its own: the player's controls and keys belong to the Emulator page (a tab there, or under the player);
setup explanations and setup chat actions belong to Setup. The keys a game answers to are the `customControls` of its web
export's `gbstudio.json` (read by `player/web/js/script.js` inside the frame; `player/web/gbstudio.json` is the demo
cartridge's); `GAME_KEYS` in `page/shared/player/bridge.js` are the keys forwarded to the frame while focus is on
the page outside it (arrows, Z, X, Enter, Shift, P: not all of the default map, and P is not in it).

## A tab

On a page without tabs, first make a tab whose `Page` is the page's old `Page` component (the page then looks the
same, with a tab bar of one).
Then add yours: make `page/pages/<page>/<tab>/index.js` exporting `{ id, label, Page }` (and, like a page,
`css`, `events`, `listens`, `slots`, `contributes`), and add it to `tabs: [...]` in `page/pages/<page>/index.js`.
`app/page-view.js` draws the tab bar and remembers the choice per page; a page with a single tab still shows a
tab bar (of one). Switching tabs remounts the chosen tab's `Page` (`page-view.js` keys it by `tab.id`), so its
`useState` starts over each time: state shared between tabs, or kept across a switch, goes in `shell.ctx.storage`
(`get(key, fallback)` / `set(key, value)`, saved) or in the shell (`app/studio-page.js`). With tabs, the page's own `Page` is not the page's body any more: if the descriptor keeps
one it renders only as a strip between the tab bar and the chosen tab (given `{ shell, tab }`), so move its
content into a tab, or drop `Page` when the tabs are the whole page. On a page with `pad` (Emulator), the shell's player and the page's `BelowPlayer` are
drawn by `app/studio-page.js` after the page view, so they stay under every tab (the player shows on the Emulator
page only). There is no per-tab switch to hide them: the player is shown whenever the page is Emulator
(`onEmulator`) and `BelowPlayer` whenever the page has `pad`, whichever tab is chosen (`page-view.js` draws only
the tab bar and the tab's body, and the shell does not know the chosen tab, which `page-view.js` keeps in
`ctx.storage` as `tab:<page>`). A tab that must hide the player needs a shell change in `app/studio-page.js`. Tests that render a page's own `Page` directly (`tests/page/slots.test.mjs` `HOSTS`, any helper like it) must render the first tab's `Page` once the page has tabs: draw `page.Page ?? page.tabs[0].Page` (`ownPage` in `tests/page/shells.mjs`). That needs the page's `Page` in its own file, imported by name in `index.js` (a tab importing `index.js` would be a cycle; `tests/page/registry.test.mjs` checks every page keeps it in its own file). Mention the tab in the page's `README.md`. A tab imports
its page's own files as `#pages/<page>/<file>.js` (a path with `../` is refused: no import climbs a folder).

Testing a tab: a scenario file `tests/page/page-<page>-<tab>.test.mjs` on the real harness (`tests/page/harness.mjs`),
run alone with `node tests/page/page-<page>-<tab>.test.mjs` after `node tools/bundle/bundle.mjs` (`python tools/check.py
page` runs it with every other `tests/page/**/*test*.mjs`). `tab('<Page>')` clicks the studio nav, `pageTab('<Label>')` the page's own tab bar.
`currentTab()` names the studio nav's open page and `currentPageTab()` the selected tab of the mounted page's own
tab bar (null for a page without tabs). As written it opens Setup (which has no tabs yet), so it runs unchanged;
for your tab, open its page, uncomment the `pageTab` line and expect your tab's label from `currentPageTab()`:

```js
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ scenario, render, tab, pageTab, currentTab, currentPageTab, heading, shows, check, answered, doctor, complete }) => {
  // A finished setup in emulator mode (the harness's buildScenario starts the same way), on Build.
  scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'build' }
  scenario.status = answered({ ...complete, hardware_enabled: false }); scenario.doctor = answered(doctor([]))
  scenario.ambient = complete
  await render()
  await tab('Setup')            // the studio nav: the page that has your tab
  // await pageTab('<Label>')   // then your tab, in the page's own tab bar (.cs-tabs)
  check('Setup opens on its finished summary', () => {
    assert.equal(currentTab(), 'Setup')
    assert.equal(currentPageTab(), null)  // '<Label>' once pageTab opened your tab
    assert.equal(heading(), 'Setup is complete')
    shows(/emulator only/)
  })
})
```

## An event

The page it happens in owns it: add `events: { '<page>.<name>': 'what happened; the payload' }`
to `page/pages/<page>/index.js`, and call `emit('<page>.<name>', payload)` from `#app/events.js` where it
happens. To react to it in another page: from a component, `on(name, fn)` in an effect (it returns the
unsubscribe); for the plugin's whole life (even while the page is not shown), `listens: { '<page>.<name>':
(payload, ctx) => ... }` in that page's `index.js`. A listener that throws is logged and never breaks the
emitter. An undeclared name throws. List it in both READMEs.

## A slot

The host page declares it: `slots: { '<page>.<name>': 'where it is; the props it passes' }` in
`page/pages/<page>/index.js`, and renders `jsx(Slot, { name: '<page>.<name>', props: { ... } })` (from
`#app/slots.js`) where the contributions go. Empty, it renders nothing, so declaring one changes nothing on
screen. List it in the registry test too. Write the props in the doc string as `Props: { a, b, ... }` (a prop
passed only in one place: `plus x(...) on the <where> only`): `tests/page/slots.test.mjs` renders each host with a
probe contribution and fails when the props passed differ from those, so give its `HOSTS` the new slot's host.

## A contribution to a slot

In the contributing page's `index.js`: `contributes: { '<page>.<name>':
[Component] }`. It lives in the contributing page's folder. `Component` gets the host's props: read the slot's
doc string in the host page's `index.js` (`slots: { ... }`) for what they are and what to return. For example
`games.cardMenu` passes `{ ctx, game, hardwareOn, item }`, where `item(icon, label, run, { disabled, why })` makes a
menu button (`icon` is a Codicon name, e.g. `folder-opened`, `copy`), so a contribution returns `item(...)` (or `null`
for no button); `emulator.barActions` passes
`{ ctx, game, hardwareOn }` (plus `go` on the Emulator page only: the slot is also drawn in the emulator tab beside
the chat, which has no shell) and its contribution renders a button. A contribution cannot reach the host's
`shell`: when it needs `go(id)` or another shell action, the host adds it to the slot's props and says so in the
slot's doc string (and the host's README Slots line).

Every place to edit for a new contribution: `contributes` in the contributing page's `index.js`; that page's README
**Slots** line ("Contributes `X` to `<page>.<name>`"); the host page's README **Slots** line (who fills it: "Games
fills it with Install"); the "Events and slots today" line below; the `filled`
assertion in `tests/page/registry.test.mjs` (its `expected`); and, when the host renders the slot in a new place,
its recipe in `HOSTS` in `tests/page/slots.test.mjs`.

Test what the item does in the host page's scenario test, where the slot is drawn with the real page around it: for
`games.cardMenu`, `tests/page/page-games.test.mjs` (`openGameMenu(card)` opens a card's arrow menu, then
`click('<label>', menu)`). The harness records what the page does: `scenario.clipboard` the text given to
`ctx.os.writeClipboard`, `scenario.notices` each `host.notify({ kind, message })`, `scenario.revealed` the last
`ctx.os.revealPath`, `scenario.inserted` what went into a chat's composer (`tests/page/sdk-stub.mjs`,
`tests/page/harness.mjs`; "Show in folder on a remote Hermes" in `page-games.test.mjs` is one). For
`emulator.barActions`, `tests/page/page-emulator.test.mjs`.

## Calling the backend from a page

`page/app/backend.js`: `callStudio(method, params)` (and `callStudioOnly`, the
hermretro profile only) resolves to the RPC's answer itself. Pick `callStudioOnly` by what the RPC's handler reads,
not by its feature or page: an answer that depends on the Build conversations or the plugin data folder
(`host._data_dir()`, one per profile: history snapshots, asset versions) needs the hermretro profile; one that is the
same from any profile with the plugin (`games`, `player`, `captures`: the shared hermretro home) uses `callStudio`.
`callBackend(method, params)` resolves to
`{ data, profile }`, so read `(await callBackend(...)).data`. The method names are the generated `RPC_*` constants
in `page/app/rpc.js`.

## Events and slots today

Events today: `games.coverRequested` (Games → Build), `emulator.presented` (Emulator → Build), `setup.firstIdea`
(Setup → Build), `setup.demoRequested` (Setup → Emulator). Slots today:
`games.cardMenu` (empty), `emulator.barActions` (Games' Install button).
