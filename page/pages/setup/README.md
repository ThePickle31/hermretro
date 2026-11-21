# Setup

**Shows:** the wizard: the step rail, the step shown (or the Chromatic choice, or setup complete) and the flying
Chromatic (`setup-page.js`, `wizard.js`, one file per step body). Also first-run onboarding (`onboarding/`,
shown by the shell instead of any page until the game tools are in) and the toolchain install (`install/`: the list and log in `install/install-panel.js`, progress,
errors and buttons in `install/install-actions.js`, state in `install/installer.js`).
The nav segment carries a dot while setup is unfinished (`Badge` in `index.js`).

**Tabs:** none.

**Events:** emits none, listens to none.

**Slots:** declares none, contributes none.

**Exposes** (`index.js`): the steps (`computeSteps`, `STEP_SHORT`, `toolchainState`, `toolchainStateKnown`,
`useSetupMemory`), onboarding (`Onboarding`, `OnboardHeader`, `ONBOARD_STAGES`), the install (`useInstall`) and
`createStudioProfileOnce`. The shell reads the steps and onboarding through `page/pages/index.js`.

**Uses from other pages:** `#pages/prompts/index.js` (setup and device prompts).

**Page state** (`shell.ctx.storage`, [STUDIO-PAGES.md, "Adding to the page"](../../../docs/dev/STUDIO-PAGES.md#adding-to-the-page)): `setup`.

**Tests:** `tests/page/page-setup.test.mjs`, `tests/page/page-setup-recovery.test.mjs` (the install's failure,
cancel and recovery states), `tests/page/page-studio.test.mjs`.

## Adding a tab here

Setup has no tabs yet: first make the wizard it shows today (`SetupPage`, `setup-page.js`) its first tab with
`python tools/retrodev new tab setup wizard --label Setup --from-page`, then add yours with
`python tools/retrodev new tab setup <id> --label <Label>`. By hand: make a folder `page/pages/setup/<tab>/` (`install` and `onboarding` are taken: pick another id) with an `index.js` exporting `{ id, label, Page }` (plus `events`,
`listens`, `slots`, `contributes`, `css` as a page has), then list it in `tabs: [...]` of
`page/pages/setup/index.js`. The shell draws the tab bar and remembers the chosen tab
(`app/page-view.js`); `Page({ shell })` gets the same `shell` as the page. Full steps:
`docs/dev/STUDIO-PAGES.md`, "Adding to the page".
