# app: the shell and page-wide plumbing

**Shows:** the frame around every page: the header with one segmented control (`nav.js`), the body of the
page shown (`page-view.js`, with a tab bar for a page that has tabs), the shared player that stays loaded
across pages (`player/`), the not-running and repair notices, the footer (`studio-page.js`). The shell builds
the nav, the routing (the remembered page) and the stylesheet from the registry: `page/pages/index.js` lists
the pages, `registry.js` checks each page's descriptor, declares their events and slots and starts them.

**Hubs other pages use:** `events.js` (`on`, `emit`), `slots.js` (`Slot`), `style.js` (`PageStyle`).
**Plumbing:** `backend.js` (RPC queries), `rpc.js` (RPC names, re-exported from the generated `rpc-names.js`; never edit that one), `routing.js`
(the hermretro profile), `chat-insert.js` and `prompt-button.js` / `prompt-block.js` (prompts into chats),
`ids.js`, `tools.js` (agent tool names), `game-prompts.js`, `format.js`, `paths.js`. `update/`: updating hermretro
from the page (the header chip and popover, the update steps, the state pages read as `shell.pluginUpdate`).

**Tabs:** none of its own; `page-view.js` draws any page's tabs.

**Events:** declares none (pages own events); `registry.js` wires every page's `listens` in `startPages(ctx)`.

**Slots:** declares none; `Slot` renders any page's slot.

**Boundaries** (`tools/bundle/lint-rules.mjs`): app/ imports `#sdk`, `#shared/`, its own files and, of the
pages, only `#pages/index.js`. Pages may use the plumbing and hubs, never the shell modules (`studio-page.js`,
`nav.js`, `not-running.js`, `registry.js`, `page-view.js`, `shell.css.js`).

**Tests:** `tests/page/registry.test.mjs` (registry, events, slots, tabs, stylesheet order); `tests/page/page-update.test.mjs`
(the update chip and its steps), `tests/page/page-update-busy.test.mjs` (no update while a game is being built); every
`tests/page/page-*.test.mjs` drives the shell through the built bundle.

## Adding a tab

Tabs belong to a page, not to the shell: see "Adding a tab here" in that page's README.md, and
`docs/dev/STUDIO-PAGES.md`, "Adding to the page".
