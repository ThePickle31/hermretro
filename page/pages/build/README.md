# Build

**Shows:** one game, one conversation with the agent (`build-page.js`): the game switcher in the header, the
transcript (`transcript/`), the message box (`composer/`), the game playing inside the reply (`player/`), the
picture viewer (`viewer/`), the image cache (`assets/`) and the `platformer` background behind New Game (`page/backgrounds/platformer/`, shown with `jsx(Background, { id: 'platformer' })`) with the shelf of games being worked on standing on its floor (`cart-shelf.js`) and the form as frosted glass over it (`new-game-glass.css.js`). `chat/` holds the conversations, the gateway events
and the actions. While the hermretro profile is missing it shows `studio-needed.js` instead (the choice is the page's
`Page`, `build-entry.js`). Descriptor: `index.js` (padding `build`, no footer, its stylesheet last). Its games are the `games` RPC's game
objects ([.agents/skills/hermretro-dev-architecture/references/contract.md, "The game object"](../../../.agents/skills/hermretro-dev-architecture/references/contract.md#the-game-object)). A game's conversation is
`BUILD_CHATS.get()[game.session.storedId]` (`chat/store.js`, inside this page); its `busy` is true while a turn runs.
If the library read fails, the page shows the error and keeps the current selection (`selection.js`) and any cached
games or conversations. The page also keeps a selected game listed as unavailable by the shelf. A successful
read confirming removal returns the page to New Game.

**Tabs:** none (its areas are subfolders, not tabs).

**Events:** emits none. Listens to `games.coverRequested` (queues the cover draft in the game's message box,
not sent), `emulator.presented` (plays the presented game in its conversation) and `setup.firstIdea` (opens New Game
with onboarding's idea and mode, unsent; `new-game-draft.js`). The Games cover action separately opens the game
with `shell.go('build', game.id)`.

**Slots:** declares none, contributes none.

**Exposes** (`index.js`): `isBuildSession(runtimeId)`, `buildShowing()` and the tool-result helpers
`toolResultObject`, `unwrapCalls`, for the Emulator page's tab beside the chat.

**Starts with the plugin** (`register`): `watchBuildChats(ctx)`, the gateway listeners that keep a conversation
streaming while the page is closed, and `restoreNewGameDraft(ctx)`, the New Game box's kept draft.

**Uses from other pages:** `#pages/games/index.js` (game states, and the `Cartridge` of the New Game shelf), `#pages/setup/index.js` (creating the studio
profile).

**Page state** (`shell.ctx.storage`, [.agents/skills/hermretro-dev-page/references/adding.md, "Adding to the page"](../../../.agents/skills/hermretro-dev-page/references/adding.md#adding-to-the-page)): `buildSelected`, `buildModel`, `buildModelStars`, `buildNewGame` (the New Game draft), `inlinePlayer` and `playtest`.

**Tests:** `tests/page/page-build.test.mjs` (New Game and the streamed conversation),
`tests/page/page-build-transcript-media.test.mjs` (steps, build results, pictures, suggestions and mentions),
`tests/page/page-build-inline-player.test.mjs` (playing builds, the play-test checklist and keyboard focus),
`tests/page/page-build-interrupted-conversations.test.mjs` (removed conversations and lost turns),
`tests/page/page-build-model-picker.test.mjs` (model and effort picks, plus questions in other games),
`tests/page/page-build-builds.test.mjs` (the Builds menu),
`tests/page/page-build-history-restore.test.mjs` (exact and dated restores), `tests/page/page-build-saved-snapshot.test.mjs` (legacy snapshots for an unbound game),
`tests/page/page-build-restore.test.mjs` (the viewer's Restore redraws the file's pictures),
`tests/page/page-build-viewer.test.mjs` (focus while a sprite animates and scene image loading),
`tests/page/page-build-speed.test.mjs` (the model panel's rail, stars and Standard / Fast),
`tests/page/page-build-model-routing.test.mjs` (fresh sessions and the picked route),
`tests/page/build-player.test.mjs`, `tests/page/registry.test.mjs` (its listeners), `tests/page/platformer-run.test.mjs`
(the New Game form over the platformer),
`tests/page/page-build-shelf.test.mjs` and `tests/page/cart-shelf.test.mjs` (the New Game shelf),
`tests/page/page-setup-handoff.test.mjs` and `tests/page/new-game-draft.test.mjs` (onboarding's idea, the kept draft and
the provider notice).

## The image viewer

`viewer/asset-viewer.js` coordinates the dialog, the stage and the selected view. It focuses the dialog on open
and returns focus to the opening button on close when the button is still present. `viewer/asset-details.js` shows
Details and `viewer/change-form.js` owns the draft and focuses the text area when it opens.
`viewer/version-history.js` handles selecting, showing and restoring kept versions.
`viewer/stage-viewport.js` draws the stage controls. `viewer/in-game.js` requests the
background and actor images for the selected scene when its canvas is shown.

## The header

`build-page.js` builds the header (`header.cs-b-head`) from these parts (and a Discard button for a game not made yet):

| Part | File | Classes |
|---|---|---|
| The game's title and the game switcher (its menu of games, the library view, the right-click menu, and the "N needs you" / "N working" / new-reply marks for other games) | `switcher.js` `BuildSwitcher` (`switcherEntries` gives its rows) | `.cs-b-sw*`, `.cs-b-ctx`, `.cs-b-needs`, `.cs-b-others`, `.cs-b-otherdot` |
| The status pill (working, up to date, edited since a build, failed, outcome unknown, no builds yet) | `builds-menu.js` `BuildPill` | `.cs-b-pill*` |
| The Builds menu (the conversation's builds, Show and Restore) | `builds-menu.js` `BuildsMenu` | `.cs-b-brow*`, `.cs-b-sw-pop.cs-b-builds` |

Their styles are in `header.css.js` (`HEADER_CSS`; narrow-window and reduced-motion changes in
`build-responsive.css.js`); the header row itself, `.cs-b-head`, is in `transcript/transcript.css.js`.
`build-page.js` is near the size limit (`tests/repo/test_layout.py`: a warning above 400 lines, a failure above 600),
so a new header part goes in its own file in `page/pages/build/`, with a row in the table above.

`snapshotFor` (`build-snapshots.js`) matches ROM builds using the result's `buildRef`. When the compact
transcript omits the result body, it requires the call ID and exact tool-result timestamp confirmed
by the `builds` RPC for the bound conversation. Compact ROM results without that evidence show an
unknown outcome. A raw validation error from a single wrapped tool call is paired with that step by
its outer call ID. Optimistic follow-ups in a running turn share the original request's work and build.
Legacy snapshots that have no exact match and before-restore backups get their own dated Restore rows.
The confirmation restores the chosen snapshot by ID.
`build-restore.js` submits a rebuild after a complete restore. It reports an incomplete restore with
the backup ID and reports a failed rebuild submission separately.

## Adding a tab here

The page has no tabs yet, so its current content becomes the first: a tab `main` labelled Chat whose `Page` is the
page's own (`build-entry.js`; the id `chat` is taken by the conversations folder `chat/`). After that, make a folder `page/pages/build/<tab>/` with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/build/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`.agents/skills/hermretro-dev-page/references/adding.md`, "Adding to the page".
