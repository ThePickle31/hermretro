# Build

**Shows:** one game, one conversation with the agent (`build-page.js`): the game switcher in the header, the
transcript (`transcript/`), the message box (`composer/`), the game playing inside the reply (`player/`), the
picture viewer (`viewer/`) and the image cache (`assets/`). `chat/` holds the conversations, the gateway events
and the actions. While the hermretro profile is missing it shows `studio-needed.js` instead. Descriptor:
`index.js` (padding `build`, no footer, its stylesheet last).

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
`tests/page/build-player.test.mjs`, `tests/page/registry.test.mjs` (its listeners).

## Adding a tab here

Make a folder `page/pages/build/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/build/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`docs/dev/STUDIO-PAGES.md`, "Adding to the page".
