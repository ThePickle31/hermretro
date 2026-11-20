# Prompts

**Shows:** the Reader: the prompt list with search on the left, the chosen prompt as editable text in the
middle, its actions (Start a new chat, Add to current chat, Copy), Hermes art on the right
(`prompts-page.js`). `library.js` is every prompt.

**Tabs:** none.

**Events:** emits none, listens to none.

**Slots:** declares none, contributes none.

**Exposes** (`index.js`): the prompt library (`ALL_PROMPTS`, `promptById`, `NEW_GAME_PROMPT`, `SETUP_PROMPT`,
`DEVICE_CLI_PROMPT`, `FLASH_PROMPT`) for Home, Setup and Games.

**Tests:** `tests/page/page-prompts.test.mjs` (the Prompts page's Reader), `tests/page/registry.test.mjs`.

## Adding a tab here

Make a folder `page/pages/prompts/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/prompts/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Switching tabs remounts the tab's `Page`
(`page-view.js` keys it by `tab.id`), so its own state starts over: state shared between tabs goes in
`shell.ctx.storage` or the shell (`app/studio-page.js`). Full steps:
`docs/dev/STUDIO-PAGES.md`, "Adding to the page".
