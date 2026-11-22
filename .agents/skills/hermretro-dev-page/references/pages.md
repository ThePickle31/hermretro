# The pages

This file is the shared contract between the
page (`page/`, bundled into `desktop/plugin.js`) and the backend (`backend/`). Both halves must match it exactly.

## Pages (one segmented control in the header, always in the same place)

The **HermRetro** entry in the Hermes Desktop sidebar opens `/hermretro`.

`Build · Setup · Games · Emulator` (Chromatic and Guide are not designed yet: do not add them). The page opens on
Build, or on the page the user last chose (a remembered page that no longer exists opens Build).

| Page | Design (details below) |
|---|---|
| Setup | Atelier wizard with the flying Chromatic |
| Games | **Shelf**, layout "A1 · split Play" |
| Emulator | ModRetro's **real player**, always: the game picked on the Games page, else the demo cartridge |

Beside Refresh, the header shows an update chip (`page/app/update/`) only
while Hermes's own daily check says a newer hermretro exists (`plugins.manage list` in the profile named by status
`plugin.installed_in`), while an update runs, or just after one. Its popover runs the update: Hermes's
`plugins.manage update` in that profile (a caution scan or a widened plugin is shown and needs "Install anyway"; a
dangerous verdict is never offered), then the `studio_profile` RPC there, then `plugins.manage toggle` off and on in
the hermretro profile (Hermes reloads only the profile that ran the update), then the app's
`hermesDesktop.reconcileDesktopPlugins` (the call Capabilities > Plugins makes; not in the plugin SDK, used only when
present) so the app copies and reloads the new page. A storage marker (`update`) lets the reloaded page say how it
went. "Later" hides the chip until a newer target. No update while something is being built: while a chat in the
hermretro profile has a turn under way (`session.active_list` there: `working`, `waiting`, `streaming` or `starting`;
checked every 5 s while an update is ready, and again right before anything changes) or the page's toolchain install
runs, Update is disabled with the reason; a turn started while Hermes updates is waited for before the hermretro
profile reloads (only after a successful check: five failed checks in a row stop there); everything that starts
work (Build sends, Continue after a lost turn, New Game, Restore, the toolchain install, removing the tools, setting up
the hermretro profile) checks the update lock in its handler and greys its control out while an update runs
(`app/update/lock.js`); a toolchain install already running is waited for before the reload. A failed profile lookup,
or a hermretro profile the status reports but the app cannot reach, stops the update before anything changes, and a
failed profile-settings step leaves it unfinished. Each yes given to Hermes (caution scan,
widened plugin) is kept for the next try. An update Hermes installed whose later steps failed is remembered
(`updatePending`) and shown as "Finish update", which runs the remaining steps even though Hermes then answers
"unchanged"; it never says "nothing was changed". The Setup page's complete screen has a hermretro row with the
version and, when one is ready, Update.

Each page has a short row here and its full design in its own subsection below, one bullet per area. A new page
adds both: a row naming its design, and a `### <Page>` subsection saying what it shows.

### Setup

- Today's Atelier wizard (step rail + current step, same rules as now) with the **flying Chromatic** on the right on every step: body + one wing drawn twice, wings flap ~0.9 s, whole thing bobs and drifts, tilted (`perspective rotateY(-14deg) rotateX(6deg) rotateZ(16deg) scale(.82)`), soft shadow, still pose under reduced motion.
- Setup tab shows a small dot while incomplete.
- First-run onboarding ends on Build: the last screen's idea goes into New Game's box through the page event
  `setup.firstIdea` (`{ idea, plan }`; Continue in Build, Plan it first, Skip and Set up my Chromatic first all take
  what was typed), with Build it or Plan first chosen and nothing sent; the user sends it from there, through New
  Game's normal start in the hermretro profile. The box is a kept draft (`buildNewGame`), cleared only once a game
  starts. On the hardware screen **Start making games** is the primary choice and **Set up my Chromatic** the
  optional one. While the tools install, **Try the demo while you wait** (only where the app can open a tab beside the
  chat) emits `setup.demoRequested`, and the Emulator page opens the bundled demo there; nothing plays unasked.
- Model access is not assumed: the hermretro profile starts with the sign-ins Hermes can share, and New Game says so
  when Hermes's `model.options` there lists no signed-in provider (no model is called), with Open provider settings.
  The hardware switch opens the hermretro profile's plugin settings (`&profile=hermretro`, Settings' own scope
  hand-off) even while the app is on another profile.

### Games

- **Cartridge grid**: the HermRetro cartridge (`page/shared/art/cart-hermretro.png`, 299×340, dark grey, HERMRETRO on its top plate) with the game's title screen filling the label window (`left 13.38%, top 28.82%, width 73.24%, height 56.76%`, `border-radius 1.5cqw`, no border).
- Under each (layout "A1 · split Play", rows line up across the shelf): title (the card's); one line of tagline (failed: the build error in red; none: "No description yet"; description and genres in its tooltip); a status line (coloured dot + Ready / Changed / Build failed / Not built, then "built … ago"; size in its tooltip); one split control.
- Its main half is the next action: Play (→ Emulator page), Build & play when changed since the last build (build prompt into its chat, not sent), Fix in chat when failed, Build in chat when never built.
- Its arrow opens a menu: Play last build (changed only), Install on Chromatic (`player.md`, "Install"; disabled with the reason), Open its chat, Make cover art / Finish card (incomplete card only), Show in folder.
- A game showing its title screen rather than a cover gets a small "No cover" tag on the label.
- The hardware state is one chip beside New game ("Chromatic tools on", or the button "Emulator only · Set up my Chromatic"); the full strip stays only on the empty library.
- The label shows the game card's cover art when it has one (`.agents/skills/hermretro-dev-architecture/references/contract.md`, "The game card (`game.json` + `cover.png`)"), else the captured title screen.
- A game without a complete card offers **Make cover art** (or Finish card) in its menu, which opens that game on Build with the request in its message box, not sent.
- **New game** (header and faded Blank cartridge, or the action in the empty or unreadable library) opens Build's
  New Game form with **Build it** and **Plan first**. Navigation alone does not start a chat.
- The empty library keeps the Chromatic status strip.

### Emulator

- ModRetro's **real player** in a `SandboxedFrame`, served by the backend (`player.md`, the `player` RPC), always. It plays only the game picked with Play on the Games page (remembered across visits in `ctx.storage` `emulatorGame`, `page/app/studio-page.js`); a game a chat builds or presents never loads here by itself (presentations open in the tab beside the chat). With none picked, or one no longer in the library, it loads the **demo cartridge** (Hello Color; no chip or extra button for it, and no Install). Tests: `tests/page/page-emulator-pick.test.mjs`.
- A failed or missing `player` RPC shows a compact notice with the reason and Refresh above an empty device area (for -32601: reload the plugin, Capabilities › Plugins).
- Above it a thin bar with only the player's controls: keyboard-focus indicator, Install, Ask Hermes, Captures drawer, Full screen (no game tabs: Play on the Games shelf picks the game).
- Below 700 px of page width the bar stops wrapping, and below 560 px its buttons keep only their icons, each with a tooltip; the header likewise stays one row (tighter segments, icon-only Refresh, and below 600 px no wordmark).
- "Hermes rebuilt <game> · Load the new build" banner when the game's web ROM (`web.sha256`) changed after the frame loaded.
- Under the player: a one-line hint ("Hermes shows your game beside the chat when it is ready for you to try.") and the user's own **Open beside the chat** button (`player.md`, "The emulator beside the chat").
- Default device finish: the first skin in `player/skins/` (**Hermes Edition · Midnight**).
