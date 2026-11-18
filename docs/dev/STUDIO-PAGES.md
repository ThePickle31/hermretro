# Studio pages: build contract

The maintainer approved clickable mockups (kept outside this repository; the table names their files) for a multi-page
hermretro and asked to build all of them. This file is the shared contract between the
page (`page/`, bundled into `desktop/plugin.js`) and the backend (`backend/`). Both halves must match it exactly.

## Pages (one segmented control in the header, always in the same place)

`Home · Build · Setup · Prompts · Games · Emulator` (Chromatic and Guide are not designed yet: do not add them).

| Page | Approved design | Mockup file (source template) |
|---|---|---|
| Home | E · Segmented nav, home variant 1 "Hero + band" (hero with the Hermes bust, then three columns Continue / Start something / Studio). While setup is incomplete quick starts are disabled ("after setup") and "Continue setup" leads with a 7-step bar and the next step's name; the hero and the Studio list both count done steps ("n of 7 done", as the Setup rail does). | `src/nav.template.html` (`ui.dir='E'`, `ui.home='1'`) |
| Setup | Today's Atelier wizard (step rail + current step, same rules as now) with the **flying Chromatic** on the right on every step: body + one wing drawn twice, wings flap ~0.9 s, whole thing bobs and drifts, tilted (`perspective rotateY(-14deg) rotateX(6deg) rotateZ(16deg) scale(.82)`), soft shadow, still pose under reduced motion. Setup tab shows a small dot while incomplete. | `src/setup-page.template.html` variant 5 (`.flyer` CSS) |
| Prompts | **Reader**: list with search + ↑/↓ on the left grouped Plan / Create / Play / Polish / On your Chromatic; chosen prompt in the middle as an editable textarea, folder + project-name inputs for prompts with `{folder}`/`{name}`; actions **Start a new chat**, **Add to current chat**, **Copy**, "Reset text"; a "What happens" note; Hermes art on the right. Hardware prompts locked without a Chromatic ("Needs your Chromatic" + Set up my Chromatic). | `src/prompts-page.template.html` variant 2 |
| Games | **Shelf**: grid of the HermRetro cartridge (`page/shared/art/cart-hermretro.png`, 299×340, dark grey, HERMRETRO on its top plate) with the game's title screen filling the label window (`left 13.38%, top 28.82%, width 73.24%, height 56.76%`, `border-radius 1.5cqw`, no border). Under each (layout "A1 · split Play", rows line up across the shelf): title (the card's); one line of tagline (failed: the build error in red; none: "No description yet"; description and genres in its tooltip); a status line (coloured dot + Ready / Changed / Build failed / Not built, then "built … ago"; size in its tooltip); one split control. Its main half is the next action: Play (→ Emulator page), Build & play when changed since the last build (build prompt into its chat, not sent), Fix in chat when failed, Build in chat when never built. Its arrow opens a menu: Play last build (changed only), Install on Chromatic (see below; disabled with the reason), Open its chat, Make cover art / Finish card (incomplete card only), Show in folder. A game showing its title screen rather than a cover gets a small "No cover" tag on the label. The hardware state is one chip beside New game ("Chromatic tools on", or the button "Emulator only · Set up my Chromatic"); the full strip stays only on the empty library. The label shows the game card's cover art when it has one (`docs/dev/CONTRACT.md`, game card), else the captured title screen. A game without a complete card offers **Make cover art** (or Finish card) in its menu, which opens that game on Build with the request in its message box, not sent. A faded "Blank cartridge" slot = New game. Empty library page (with the Chromatic status strip). | `src/games-page.template.html` (`.mcart.real`) |
| Emulator | ModRetro's **real player** in a `SandboxedFrame`, served by the backend (below), always: with nothing playable of the user's it loads the **demo cartridge** (Hello Color; no chip or extra button for it, and no Install). A failed or missing `player` RPC shows a compact notice with the reason and Refresh above an empty device area (for -32601: reload the plugin, Capabilities › Plugins). Above it a thin bar with only the player's controls: keyboard-focus indicator, Install, Ask Hermes, Captures drawer, Full screen (no game tabs: Play on the Games shelf or Home picks the game). Below 700 px of page width the bar stops wrapping, and below 560 px its buttons keep only their icons, each with a tooltip; the header likewise stays one row (tighter segments, icon-only Refresh, and below 600 px no wordmark). "Hermes rebuilt <game> · Load the new build" banner when the game's web ROM (`web.sha256`) changed after the frame loaded. Under the player: a one-line hint ("Hermes shows your game beside the chat when it is ready for you to try.") and the user's own **Open beside the chat** button (see below). Default device finish **Hermes Edition · Midnight**. | `src/emulator-page.template.html` variant 5 + `src/player/*` |

## Build: one game, one conversation

The Build page drives an ordinary Hermes session itself instead of sending prompts to the chat:
this game's conversation, where the game also plays, with the trimmed New Game screen (idea box,
name, "Plan it first"). There is no games rail (user picked mockup B to give the chat room next to
Hermes's own sidebar): the title in the header is the game switcher. Its menu (user picked mockups
A1 + A2 + E) lists New game, Edit a game, then "Editing now": New Game conversations still being set
up and the games that have a conversation (plus the game just picked, until its first message makes
one), each with its screen, status (working, needs your answer, new reply) and Ctrl+1…9 (Hermes binds
no Ctrl+digit). Edit a game swaps the menu for a searchable list of the other library games, with a
footer naming the ones already open; picking one opens it with a blank conversation. Right-click (or
the context-menu key / Shift+F10) on a game being edited offers Open in full chat and Stop editing
(Discard for a New Game still being set up); both are off for a conversation in another profile, and
Stop editing / Discard wait while the agent works. Beside the title, other games show as "N needs you"
(yellow, names in the tooltip), else "N working", else a new-reply dot. Arrow keys move through the
menu, Escape closes the right-click menu, then the library list, then the menu. User decisions:

- **One game = one session.** Game sessions are created `hidden` (not in the Hermes sidebar); the
  Build page's game switcher is the way in, and "Open in full chat" (`host.openSession`) shows the same session.
- **New Game** creates the session first (`session.create {hidden: true, title}`), then sends the
  new-game (or planning) prompt. It is pending in the game switcher until the library shows the game it made.
- **A game with no conversation** opens a blank one; the session is created on the first message.
- **Stop editing** unbinds the game (`build` `unbind`) and un-hides its session (`session.set_hidden
  {hidden: false}`), so the old conversation shows up in the Hermes sidebar instead of being lost. The
  game goes back under Edit a game; editing it again starts a new conversation.
- **Guards (broker, `guard_selection`):** a game's conversation that tries to create a project or
  select a different one is refused (`ONE_GAME_PER_CONVERSATION`, "start a new game from Build").
  Another chat selecting a game that has its own conversation is warned (`GAME_HAS_CONVERSATION`);
  it may continue once the user confirms, by selecting again with `continueInThisChat: true`
  (hermretro's own `project_select` argument, removed before the engine sees it). A New Game
  conversation may create a project or look at an unbound game, never take a bound one. A game's
  conversation whose game folder is gone is told so (`GAME_FOLDER_MISSING`); the warning applies to
  chats in every profile, since the rule is about the game.
  Start fresh is out for now.
- **Auto-select:** the first read, write or runtime call of a game's conversation selects its game
  (`select_bound_game`) and the result's `notice` says so. A failed attempt is not repeated for the
  same worker; a failed status sync after a good select still records the selection.
- **Per-turn context:** a `pre_llm_call` hook tells a game's conversation which game it is, and a New
  Game conversation how to start (name, Plan it first). The page therefore sends the user's own words.

### Binding (`games.json`)

`games[id].session = {storedId, profile, createdAt, aliases}` (aliases: live session ids after
compression rotates them, noted on each tool call) and `pending[storedId] = {storedId, profile, name,
plan, createdAt, aliases}` (New Game conversations whose project does not exist yet, newest 50).
The first project a pending conversation creates is bound to it (`observe` → `claim_pending`);
selecting an existing game does not claim it. Unknown top-level keys in `games.json` are kept, since
every hermretro copy shares the file.
The `games` RPC returns `games[].session = {storedId, createdAt, thisProfile, profileName, exists} |
null` and `pending: [{storedId, name, createdAt, exists}]` for this profile. `exists` is read from
the profile's session database (`null` when unknown).

### `build` RPC

Params name the session `stored`, never `session_id` (the gateway would authorize it as live):
`{action: "start", stored, name?, plan?}` → `{ok, pending}`; `{action: "bind", game, stored,
replace?}` → `{ok, game, session}` (`replace` swaps a conversation that was removed);
`{action: "cancel", stored}` → `{ok, cancelled}`; `{action: "unbind", game, stored}` → `{ok, unbound}`
(only when `stored` is the game's current conversation, so a stale page cannot drop a newer one). Failures are `{ok: false, code, error}` with
`code` one of `INVALID`, `NO_GAME`, `BOUND` (the session belongs to another game),
`HAS_CONVERSATION` (the game has another session and `replace` was not set) and `OTHER_PROFILE`
(`replace` never takes another profile's conversation).

### `asset` RPC

`{path}` (absolute, or `file://`) → `{ok, path, relative, name, kind, width, height, bytes,
modifiedAt, dataUrl, sprite?}` for PNG, GIF, JPEG or WebP up to 6 MB, only inside a library game's
folder or the plugin's saved frames (symlinks are resolved first). `sprite = {name, frameWidth,
frameHeight, animSpeed, canvasWidth, canvasHeight, palette, standing: {tiles, flip}, moving: {frames,
flip}}` from the `.gbsres` sidecar and the project: GB Studio stores sprites in four placeholder
greens with `#65ff00` as transparency, so the page paints every sprite thumbnail with `palette` (the
one its first use in a scene is painted with, else the default sprite palette) and draws the frame
that use stands in. The project lookup is cached per game until a settings, palette, scene, actor or
sprite file changes. Failures: `INVALID`, `NOT_IMAGE`, `OUTSIDE`,
`TOO_LARGE`, `MISSING`. With `at` (a reply's time, ms) it answers the version the file had then; with
`version` (an id from `asset_info`) that kept version. Every answer carries `versionId` and `earlier`.

Versions: the plugin keeps a copy of a game image (up to 40 per file, named by modification time in
ns, identical rewrites skipped, under `<plugin data>/asset-versions/`) when a reply delivers it
(`MEDIA:` line, `post_llm_call`), a step looks at or writes it (`post_tool_call`), or the page shows
it. So a file rewritten later (cover.png made again) still shows each reply what it delivered.

### `asset_info` RPC

`{path}` → `{ok, path, relative, kind, versions}`, `kind` one of `cover` (the game card's cover),
`sprite`, `background`, `ui`, `frame`, `capture`, `image`; `versions = [{id, at, file, current}]`
oldest first, exactly one `current`. A sprite adds `sprite = {name, id, type, flipLeft, states,
canvasWidth, canvasHeight, animSpeed, numTiles, animations: [{slot, name, frames: [[tile]]}]}` (the
first state's animations, named by GB Studio slot: "Walk right"…; a tile is `{x, y, sliceX, sliceY,
flipX, flipY}`, 8×16, `y` up from the canvas bottom) and `palette = {id, name, colors[4]}` (the one
it is painted with in its first scene). Sprites and backgrounds add `usedIn = [{scene, sceneId, as,
count}]` and `scenes` (up to 6): `{id, name, width, height, background, actors: [{name, spriteId,
sprite, x, y, player, canvasWidth, canvasHeight, tiles, flip, palette}]}`, each actor's standing frame
for its facing, the player at the start position of the start scene. Read from the distributed
project files; nothing is compiled.

### `asset_restore` RPC

`{path, version}` → `{ok, path, versions}`: puts a kept version back in place, keeping the one it
replaces first. Not for saved frames.

### `assets` RPC

`{game}` (a library id) or `{root}` (a library game's folder) → `{ok, root, assets, truncated}`, the
pictures the Build page's @ picker lists: the game card's cover first, then every image under
`assets/sprites`, `assets/backgrounds`, `assets/ui` and `assets/fonts` (symlinks leaving the game are
skipped), at most 400. Each is `{path, relative, name, file, kind, modifiedAt, bytes}`; `name` is the
sidecar's (`.gbsres`) name when there is one, `kind` one of `cover`, `sprite`, `background`, `ui`.
No image data: the page loads each through `asset`. Failure: `NO_GAME`.

### Page

Gateway calls go to the `hermretro` profile ONLY (`studioTarget()` in `app/routing.js`: its route, or the app's
own connection when the app is on that profile). When it is missing or not answering, every Build/chat call
throws `STUDIO_PROFILE_MISSING`, the Build page shows `StudioNeeded` (Repair re-runs `studio_profile` from the
profile the plugin was installed into) and "Use in chat" copies the prompt with a notice; nothing ever runs in
another profile. Gateway calls (on that route, `host.retainProfile` held): `session.create
{hidden: true, title}`, `session.resume` (history; `omit_messages` while polling), `prompt.submit`
(with `submission_id`), `session.interrupt`, `clarify.lock` (fallback `request.answer`),
`approval.respond`. The stream is `host.onEvent` filtered by `session_id`, de-duplicated by `seq`
and the delta `offset`. Questions and approvals are server requests the page never receives: while
a tool runs it reads the session's `open_requests` and renders them as cards. A backend without the
`build` RPC (-32601) keeps bindings for the visit only and names the project in the first message.

- **The conversation** (approved design "Build chat final"; user: "this still needs to feel like a
  chat experience"). The user's messages are bubbles on the right; the agent's replies are plain prose
  on the left under a plain "HermRetro" label and time ("working now" while it works). No avatar, no
  coloured bar or tint ("seems like too much", "it doesn't need to be stylized"). Every UI string
  calls the agent HermRetro. Text is `MessageTextContent` (markdown), memoised per block.
- **Worked for…** Each reply folds its steps into one line: "Working for 0:42 · 3 steps" (open, live)
  and "✓ Worked for 1m 12s · drew the art, built it" once done (closed, opens on a click), followed by
  a small stack of what the turn made and an "N assets" link that opens the viewer on its first
  picture (pictures a step only looked at and playtest frames do not count). Open, it has a Simple /
  Technical switch (one setting for every turn). Simple: a turn of 8 or more steps opens to fixed
  groups, always in this order (Planned it · Drew the art · Set up the level · Built it · Play-tested
  it), each folded with its step count; commands and file edits join the group they helped (a command
  or file about art joins Drew the art), and glances (reading a guide, inspecting the project) are left
  out unless they showed a picture. Shorter turns are one plain list. Technical: every step with its
  command or detail, as before.
  Steps read in plain words from `STEP_WORDS` ("Creating the project", "Built the game");
  Hermes's `tool_call` wrapper is unwrapped live and in history (Hermes splits a batch into one
  `tool_call` per call, so the inner call keeps the outer id, and its result row names only the outer
  id); a history result row with `ok: false` or an `error` marks its step failed. Plumbing
  (`tool_describe`, `todo`, `chromatic_build_report`…) is hidden. The words before the first step
  lead the reply, words between steps are notes inside, words after the last step close it. Steps
  keep only small args (`stepArgs`); a report keeps its whole (`normalizeReport`).
- **Build cards** (user-approved "final set": A Quiet thread + D Build cards + E Focus mode). Each
  turn that compiled the game (`rom_build`/`web_build` done or failed) is a numbered build, #1 up, in
  conversation order (`buildHistory`). A finished build turn, or one that called
  `chromatic_build_report`, ends in a card: badge (#n, red when its last compile failed), the report's
  title (else the message that asked), how long it took, and Play on the build that plays (else
  "Earlier build" / "Playable again when HermRetro finishes"); the report's summary; for a picture
  it edited, Before → After (the `asset` RPC at the turn's start and end; nothing when the file is
  new), with Keep / Undo on the newest turn (Undo = `asset_restore` of the earlier version, then
  "Rebuild" asks the agent to build again); what changed (+ added, ~ changed, − removed, with a
  thumbnail when the change names an asset; without a report, the pictures the turn made); the
  player when open; a footer with "✓ N play-tested · ○ N not tested · ⚠ N notes" and Details (the
  lists, and the compiler's words for a failed build, with Ask HermRetro to fix it). With a report
  the reply's words follow the card; without one they come first. The newest reply's suggestions
  are chips under it that put their words in the message box (never sent).
- **Header.** The title (game switcher), one status pill (Working · 0:42 / Build #n · up to date /
  Edited since build #n / Build #n didn't finish / No builds yet) and Builds ▾: every build newest
  first, with Show (scrolls to its card) and Restore (on built ones, except the one already playing
  when nothing changed since). Restore matches the build to a snapshot from the `builds` RPC by time,
  confirms in place, calls `build_restore` (which saves the game as it is first) and sends the agent
  "I restored the game to build #n … Please build it again", so the restored files become the newest
  build. There is no Assets panel and no Full chat button (Open in full chat stays in the switcher's
  right-click menu and the stuck status).
- **@ assets.** Typing `@` (at the start or after a space) in the message box, or its @ Asset button,
  lists the game's pictures from the `assets` RPC; what follows filters by name or file, ↑/↓ and
  Enter/Tab pick, Esc closes. The pick leaves the text and is attached as an `@name` chip (sent as
  "About <path>:" like any attachment); the user's bubble shows it as `@name`.
- **New Game** keeps its two choices and adds starter ideas (chips that fill the box, editable) and a
  dashed hint that pictures show up as HermRetro draws them and `@` points at one.
- **Assets as they land.** Images a step made or looked at (`image_path`, result images,
  `assetPath`/`outputPath`, `vision_analyze`'s `image_url`; project-relative paths joined to the
  game's root) show as thumbnails under the step and as a "Latest" card while it works. Sprite sheets
  show one frame (a one-row sheet plays in the Latest card, CSS steps only). An image line in a reply
  (`MEDIA:<image>`) is drawn by the page too, at the version the reply delivered. Images come from the
  `asset` RPC, cached per path and version, four at a time.
- **The viewer** (approved mockups A + C + E + F, "remove the suggested prompts"). A click on any
  picture opens one window, picture first: Fit (the biggest whole zoom) / 1–8×, wheel zoom, drag to
  pan, an 8×8 tile grid (8×16 for sprites). The kind picks the views: a cover Image · In game (its
  Games page card and a Chromatic), a sprite Animation (states as chips, the game's speed from
  `animSpeed`, frames, onion skin, painted with its in-game palette) · Sheet · In game, a background
  Image · In game (the scene as it starts, the sprite's actors outlined). The side panel has Details
  (who made it and the message that asked, an older version's Restore, palette, colours to copy,
  hardware checks from the pixels, Used in / Shown on) and Change: a request box, a dragged area
  ("Only change the area from (x, y) to …"), "Build and show the game after" for sprites and
  backgrounds; it is sent into the conversation naming the image, the viewer stays open with the
  turn's steps, and when the turn ends the new version is fetched and shown. Every kept version sits
  in a strip along the bottom (the one in the game marked). ←/→ other pictures of the turn, Esc
  closes, Show in folder (`ctx.os.revealPath`, else the path is copied), Copy image.
- **The game, in the conversation** (user: "for now it should only ever show up when the agent has
  finished and the user can play test the game"). The turn that last built the game ends with its
  build card; Play there opens the real player inside that card (no third column; a game built
  outside the conversation still gets a plain play card). It opens by itself when the
  agent presented the game that turn (`chromatic_present_game` from a Build conversation opens no tab
  beside the chat; its note shows on the player). While the agent works the player rests as a card,
  "Playable again when HermRetro finishes", and comes back when it is done. Older build cards say
  "Earlier build". It takes the live player from the Emulator page (a tab beside the chat keeps it
  and offers "Bring it here"); keys reach the game only after a click in it. The player
  (`page/pages/build/player/`, user-approved mockup `chromatic-studio-mockups/inline-player/inline-player-final.html`):
  - **One bar**: Fit/2×/3×/4× (always a whole multiple of 160×144; Fit is the largest that fits, a size
    that does not fit is disabled), Chromatic (the handheld around the screen; its finish in the menu),
    Play-test (the panel), Annotate, sound, pause, screenshot, More (restart, record), full screen, close.
    ModRetro's own controls are hidden in the frame (`view=screen|device`); the bar presses them.
  - **Play-test panel** beside the game (under it as tabs below 760 px; folded to a tab with a count):
    the agent's note, "Try this" checks from the build report (`untested` first, then `tested`,
    deduplicated), ticked by hand only and kept per game and build (last 12 builds), controls, Ask
    HermRetro. Ticking the last check folds the panel. A check's "Something's wrong" attaches the frame
    and starts a sentence in the message box; on later builds that check comes back as "Fixed in #N"
    until ticked.
  - **Annotate**: the engine's own annotation (frozen frame, `hitTest` snapping to sprites, sprite groups
    and tiles, names and hardware metadata, live palette preview through its controls) with our UI:
    numbered boxes in the frame, the panel lists each mark with a close-up, its colours (recolour preview)
    and a note; Add to message attaches the frame and one chip per mark (close-up and hardware details
    for the agent), not sent. Esc or Cancel leaves it.
  - Ask HermRetro attaches the current frame to the message box, not sent.
- **Honest status** above the message box while a turn runs: "HermRetro is <step>" (or thinking,
  writing, tidying up the conversation) with "last update Ns ago"; after 45 s of quiet it says
  nothing new has come in (normal for builds); after 3 min (10 for builds and installs) "has been
  quiet for N minutes, may be stuck" with Open full chat and Stop; "waiting for your answer" with
  Jump to the question; "Reconnecting…" after three failed polls. The game switcher shows a spinner, "Needs
  your answer" or a new-reply dot per game.
- **Questions** are one card outside the steps: numbered choices (number keys pick), "(Recommended)"
  shown as a Suggested tag, an own-answer field, Send answer once every question has one. Answered,
  they become a step with the answers as chips. Approvals are a card with their choices.
- **Sending while it works** follows Hermes's `display.busy_input_mode`: a redirected message joins
  the turn; a `queued` one waits under the conversation ("Queued · HermRetro reads this when it
  finishes") until its `message.start`. Only a message sent behind a running (or lost) turn moves
  there: the gateway also answers `queued` for a first message that starts at once. Messages Hermes
  still holds when a conversation opens (`pending` rows with status `queued`) show the same way.
  Stop interrupts; a stopped reply says so and offers Carry on.
  A failed build offers "Ask HermRetro to fix it"; a failed send offers Try again.
- **A lost turn** (the gateway restarted mid-turn; `pending` row with status `unknown`, from
  `session.resume` or a `session.info` event) pauses the conversation: Hermes runs nothing after it.
  The page drops the working state and shows "HermRetro stopped partway through" with Continue, which
  calls `prompt.resolve_unknown {session_id, admission_id}` per lost turn (the app's client adds the
  generation it learned from the snapshot; the lost turn is not re-run). Waiting messages then run;
  with none, Continue sends "Continue where you left off" (shown as "Continue"). A message sent while
  paused waits ("Waiting · sent when you continue").
- **Model and effort** (user picked mockup C, "one button, one panel"): one button under the message
  box, "<mark> Claude Opus 5.5 · High". It opens connected providers (left; `model.options`, only
  `authenticated` ones with models), that provider's models (right; search covers every provider and
  names each match's provider; ids shown as names: `claude-opus-5-5[1m]` → "Claude Opus 5.5" + 1M tag,
  "fast mode" from `capabilities`), and an Effort row (Off only when the model can disable reasoning;
  Minimal, Low, Medium, High, X-high, Max). Changes are per conversation, never the profile default:
  `config.set {session_id, key: 'model', value: '<model> --provider <slug> --session'}` and
  `{key: 'reasoning', value}`; the app's client turns both into `session.mutate` on the canonical
  gateway (a raw `config.set` model is refused there with `use_session_mutation_model`). The current
  values come from `info` of `session.create`/`session.resume` and `session.info` events. A pick made
  while HermRetro works is held ("next message") and applied when the turn ends. A model that asks
  first (`confirm_required`) shows its message in the panel with Use it (`confirm_expensive_model`).
  A provider that is no longer connected shows on the button. New Game and a game with no conversation
  use a draft pick (stored as `buildModel`), passed to `session.create {model, provider,
  reasoning_effort}`. A reply names its model when it differs from the message before.
- **Smoothness:** text events are applied once per frame; turns are memoised (only the live one
  re-renders); 40 turns at a time with "Show earlier messages" keeping the reading position; the view
  follows the end unless the user scrolled up (then a "Latest" button). Measured with a 200-turn
  conversation: streaming holds 60 fps with no long tasks. `prefers-reduced-motion` stops every
  animation.
- Events carry `replay_epoch`: a new epoch (gateway restart) resets the `seq` watermark. A
  `session.replay_gap`, or a submit that finds no session, re-attaches and reloads the transcript.
- `open_requests` is polled for the whole turn (a plugin approval gate asks before `tool.start`) and
  stops when the snapshot says `running: false`. Cards are keyed by request id, so the event and the
  poll make one card; `*.settled` marks it answered. An `error` frame ends the turn.
- A conversation is "removed" only on a definite not-found (4007) or `exists: false`; other open
  failures offer Try again. A game whose conversation is in another profile says so and is not
  replaced from here. A New Game that never made a project can be discarded (`cancel`); a failed
  start cancels itself. A remembered selection that no longer exists falls back to New game.

## The emulator beside the chat

User request: show **our** emulator (the Emulator page's bar + ModRetro's real player from `backend/player/server.py`,
Hermes Edition Midnight) beside the chat instead of the engine's page in the in-app browser — and only
when the agent is ready to present the game after making it, never for the whole of development
(user requirement: "it should not be there the entire time"). Builds open nothing.

- **Agent tool `chromatic_present_game`** (plugin-owned, toolset `chromatic`, registered next to
  `chromatic_studio_device_cli`; not an engine tool, not in the pinned manifest). Params
  `{note?: string ≤300, project?: absolute folder}`. The project is `project` when given, else the chat's
  lane selection (broker `activity` op, memory only, never starts the broker), else the library game whose
  chat link is this conversation. It requires a fresh web export (`library.export_freshness`: `build/web`
  exists and is not older than the last ROM build — the registry's `lastBuild.t`, else the newest native
  ROM under `build/` — where the export's time is the later of its ROM file and `lastWebExport.t`, which the
  broker records on every successful `web_preview` open, because the engine reuses an export whose sources
  did not change without rewriting its files; a failed build after it also counts as stale); otherwise `{ok:false, code:"BUILD_FIRST", error, guidance}` telling the
  agent to run `chromatic_rom_build`. On success it records the presentation in the games registry
  (`games[id].chat`, `games[id].presented = {t, note}`, and the bounded `presentations` list) and returns
  `{ok:true, studio:{gameId, playerUrl, title, note, presentedAt}, message:"Shown to the user beside the chat."}`.
  It never calls an engine tool or a device; the approval hook lets it through; a delegated subagent is
  refused (`PARENT_ONLY`).
- **Trigger.** `register()` subscribes with `ctx.onEvent` (fallback `host.onEvent`) to the gateway event
  `tool.complete`, payload `{tool_id, name, args, result, …}` (`result` already JSON-parsed by
  `tui_gateway/tool_progress._on_tool_complete`), envelope `session_id`. Only a successful
  `chromatic_present_game` (`result.ok` and `result.studio.gameId`) opens or fronts
  `host.openWorkspace('hermretro.emulator.<game id>', {dock: {pane: 'workspace', pos: 'right'},
  minWidth: '22rem', title: 'Emulator · <studio.title>'})`. `chromatic_rom_build` / `chromatic_web_preview`
  completions only bump a counter so open players re-read `games` at once.
- **Fallback.** The gateway sends `tool.complete` only while the chat's tool progress is not `off`, so every
  `message.complete` (600 ms later) calls RPC `presentations` with `since` = the backend's `now` from the
  previous answer minus 1 s (first call: plugin start minus 5 s) and presents the newest one per game.
  Presentations are de-duplicated by `<gameId>:<presentedAt>`, so one heard through both paths is acted on once.
- **Presenting again** loads the newest build in the open tab directly (the player query and frame key
  change, no banner): it is an explicit "try this now". The note appears as a slim, dismissible line
  (`.cs-side-note`) between the bar and the player; a presentation without a note shows none.
- **Rebuilt without presenting.** An open tab keeps the `Hermes rebuilt <game> · Load the new build`
  banner (no auto-reload). A closed tab is never reopened by builds.
- **User's own button.** The Emulator page's **Open beside the chat** (under the player, hidden on
  desktops without `openWorkspace`) opens or fronts the current game's tab on request. There is no
  auto-open setting any more (the old `sideEmulator` / `sideOpened` storage keys are unused).
- **One live player.** A module atom names the surface that runs the game: `'page'`, `'side:<id>'` or
  none. Opening the Emulator page, a presentation opening a tab, or **Bring it here** takes it; the other
  surface unmounts its frame and shows "Playing beside the chat" / "Playing in hermretro" with
  Bring it here (which starts the game again). A surface that unmounts gives it up; a visible surface
  takes it when nobody has it.
- **Tab content.** Same `EmulatorBar`, `PlayerNotice`, `PlayerStage` and annotate / Ask Hermes code as
  the page, in `.cs-page.cs-side` (stage fills the tab; the player inside scales by height and width).
  Page keys reach the game only after the user last clicked inside the tab, so the chat keeps its keys.
- **Rebuilt check.** Both surfaces compare the player's `romSha256` with `game.web.sha256` (the web
  export's own ROM; the native build's bytes differ), falling back to `rom.sha256` on older backends.
- **Agent side.** `rom_build` / `web_preview` results no longer carry any Studio address
  (`studio`/`studioPlayerUrl`/`studioGameId` are gone) and the engine's own preview address is not offered
  after a build. Their `nextStep`, the system prompt section and the skills say: when the game is ready for
  the user to try, call `chromatic_present_game` (do not use `desktop_preview`/`drive_preview` for the
  game); only if the user says they cannot see the emulator, open `studio.playerUrl` from
  `chromatic_present_game` with `desktop_preview`; without desktop tools, give the user that URL.
- No openWorkspace (older desktops): a presentation opens nothing and nothing breaks; the page keeps its
  player.

## RPC (all `plugin.hermretro.<name>`)

### `games` → library
Params: none. Result:
```json
{ "games": [ {
    "id": "<sha1 of projectRoot, 12 hex>",
    "title": "Comet Drift",
    "projectRoot": "/abs/path",
    "kind": "gbstudio" | "gbdk",
    "state": "ready" | "changed" | "failed" | "unbuilt",
    "rom": { "path": "/abs/…gbc", "sha256": "…", "size": 131072, "builtAt": 1731400000 } | null,
    "webExport": true,
    "web": { "sha256": "…", "builtAt": 1731400000 } | null,
    "thumb": "data:image/png;base64,…" | null,
    "chat": { "sessionId": "…", "title": "…" } | null,
    "error": "<last build error, ≤240 chars>" | null
  } ],
  "demo": { "id": "demo", "title": "Hello Color", "kind": "gbdk", "note": "ModRetro example" },
  "device": { "hardwareEnabled": false, "skipped": false }
}
```
`demo` is the built-in demo cartridge. It is never part of `games[]`, so the Games shelf stays the user's library.
The registry is `state_dir/games.json`, updated by the broker whenever a lane selects or builds a project (`Lane.remember` paths for `project_select`/`project_create`/`rom_build`/`web_preview`). `state` = `failed` if the last build failed, `changed` if any file under the project's sources is newer than the ROM, `unbuilt` without a ROM, else `ready`. `webExport` = `<project>/build/web/index.html` and `js/binjgb.wasm` exist. `web` describes the ROM inside that export (named by its `gbstudio.json`): the player loads that file, which is its own compilation and not byte-identical to `rom`, so the rebuilt banner compares against `web.sha256`.

### `game_thumb` → store a title screen
Params `{ "id": "…", "png": "data:image/png;base64,…" }` (≤ 64 KB). Saves `state_dir/thumbs/<id>.png`; `games` returns it from then on. Result `{ "ok": true }`.

### `player` → open the real player for a game
Params `{ "id": "…" }`. Result `{ "url": "http://127.0.0.1:<port>/<token>/<id>/index.html", "romSha256": "…", "title": "…" }` or `{ "error": "…" }` (no web export → message telling the user to build it from chat).
`{ "id": "demo" }` or `{}` opens the demo cartridge (`"demo": true` in the result): GB Studio's default browser player bundled in `player/web/` (MIT notices in `player/web/LICENSES/`) with ModRetro's `examples/hello-color/hello-color.gbc` read in place from the engine, served as `rom/hello-color.gbc`. No project is involved; its captures go to `<library dir>/captures/demo` (`captures`/`capture_image` accept `demo` too).

The backend runs one loopback HTTP server (stdlib `ThreadingHTTPServer`, `127.0.0.1`, random port, 32-byte random path token, started lazily in the gateway process, daemon thread). For `/<token>/<id>/…` it serves:
- `index.html` = the game's `build/web/index.html` with, injected:
  - in `<head>`, before anything else: the **frame shim** `player/frame-shim.js`, generated from `page/frame/` by `tools/bundle/bundle.mjs` (never edit it): in-memory `localStorage`/`sessionStorage` because the sandboxed frame has an opaque origin (the finish from `?color=`); the `document.oai.annotation` host the engine's annotation registers with; the inline view (`?view=screen|device` hides the player's own controls); the page's commands (see Page ↔ frame messages); player state, console error and focus/blur posts. `backend/player/server.py` fills its `__DEFAULT_COLOR__`/`__COLOR_KEY__` placeholders.
  - before `js/script.js`: the engine bootstrap (`Binjgb` wrapper that sets `module.codexRuntimeSha256` and calls `installInputOwner` from `./codex-annotations/input-owner.js`) — copy it from `dist/server.js` `prepareAnnotations`.
  - before `</body>`: `<script type="application/json" id="codex-web-annotations-context">{romSha256, romPath, sourceRevision, runtimeSha256, captures:{generation}}</script>` and `<script type="module" src="./codex-annotations/bridge.js"></script>`.
- the export's own files (`js/*`, `css/*`, `rom/*`, `gbstudio.json`) read-only, path-checked to stay inside `build/web`.
- `codex-annotations/<file>.js` from the prepared engine (`<hermretro home>/.cache/engine-<version>/dist/web-annotations`, falling back to `engine/modretro-chromatic/dist/web-annotations`), with **one text patch in `view.js`**: prepend the four Hermes Edition entries to `DEVICE_COLORS` (`hermes-midnight` "Hermes Edition · Midnight" `#15171c`/`#e6edf3`, `hermes-blue` "Hermes Edition · Nous Blue" `#0053fd`/`#ffffff`, `hermes-white` "Hermes Edition · White" `#f2f5fc`/`#1f2328`, `hermes-clear` "Hermes Edition · Clear Blue" `#cfdcff`/`#1f2328`). If the anchor text is missing, serve unpatched and log it.
- `codex-annotations/chromatic-<color>.(webp|png)` from the prepared engine's `assets/devices/`, and `chromatic-hermes-*.webp` from the plugin's `player/devices/`.
- `codex-captures` POST (multipart: `kind`, `metadata`, `media`): save to `<projectRoot>/captures/<iso>-<kind>.<png|webm|mp4>` + `.json`; reply exactly `{id, kind, bytes, path, metadataPath, sha256, createdAt, url: "./codex-captures/<id>/media", metadataUrl: "./codex-captures/<id>/metadata"}`; GET those two URLs back.
- `codex-states` GET → `{ "states": [] }` (not wired yet).
- `codex-device` POST → `{generation, devices: [], rom:{sha256}, available:false, blocked:false, detecting:false}`. Installing from inside the player stays off: the Studio's own Install button sends the flash prompt to chat, where Hermes's approval gate applies. Do not proxy flashing here.
- Every response: `Access-Control-Allow-Origin: *` (the frame's origin is `null`), `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, correct MIME (`.wasm` → `application/wasm`, `.js` → `text/javascript`). Default device colour: the shim seeds `localStorage['codex-gb-studio:device-color:v1'] = 'hermes-midnight'` unless the page passes a valid `?color=`.

### `presentations` → games the agent presented
Params `{ "since"?: number }` (seconds, backend clock). Result `{ "ok": true, "now": <backend time>,
"presentations": [{ "gameId", "title", "t", "note", "sessionId", "conversationId", "profile", "thisProfile" }] }`,
oldest first, at most 20, only those with `t > since`. Written by `chromatic_present_game` (registry key
`presentations`, newest 100 kept). Used by the desktop when `tool.complete` does not arrive.

### `captures` → list
Params `{ "id": "…" }` → `{ "captures": [{ "path", "kind", "createdAt", "url" }] }` where `url` is the loopback media URL (frame-independent: `http://127.0.0.1:<port>/<token>/<id>/codex-captures/<cid>/media`).

## Page ↔ frame messages
Defined once in `page/shared/player/protocol.js` (page side `shared/player/bridge.js`, frame side `frame/commands.js`); every message is an object whose `cs` names it, and the page accepts only messages from its own frame's window.
- page → frame: `{cs:'cmd', type, …}` with `type` one of `key {key, code, down}`, `snap {id}`, `hold` (pause + suspend audio while the surface is hidden), `release`, `theme {css}`, `view {view}` (`full` | `screen` | `device`), `press {action}` (one of the player's own buttons: play, sound, restart, history, screenshot, record-video, annotate), `finish {id}`, `annotate {on}`, `mark-color {id, index, value}` (value null resets), `mark-remove {id}`, `marks-take {id}`.
- frame → page: `{cs:'focus', value}`, `{cs:'log', level, text}`, `{cs:'snap', id, url}`, `{cs:'state', ready, paused, muted, annotating, recording}`, `{cs:'marks', marks}` (inline annotate, each `{n, id, name, role, metadata, colors, original, image}`), `{cs:'marks-taken', id, image, marks}` (answers `marks-take`, then annotate ends), `{cs:'annotate', target:{name, role, metadata}, note, image}` (the full view's single pick with the in-frame note card).
- Ask HermRetro / annotate / Something's wrong: the page saves the frame through `capture_image` (`{id, png}` → `{path}` under `<project>/captures/`) and attaches it to the game's message box (in the Build page; elsewhere `host.composer.insertText`, falling back to a new chat in the studio profile) with what was marked, its metadata and the note. Nothing is sent automatically.

## Install
Games shelf and Emulator bar **Install** = send the existing "Flash a cartridge" prompt (with the game named) to that game's chat. Hardware gating and the approval prompt stay exactly as today; locked with "Needs your Chromatic" when hardware is not set up.

## Constraints that apply to both halves
- The page's source is `page/`; `desktop/plugin.js` and `player/frame-shim.js` are generated from it by `tools/bundle/bundle.mjs` and committed. Never edit a generated file: change the sources, rebuild, commit them together. The bundle stays plain readable ESM (`jsx`/`jsxs`, not minified), imports only `@hermes/plugin-sdk`, `react`, `react/jsx-runtime`, scoped CSS under `.cs-page`, every colour a `var(--ui-*)`. Size: Hermes Desktop reads a plugin file up to 16 MiB through `readPluginSource`; an older shell without it stops at 512 KiB and says to update, and the bundle (about 635 KB) needs the newer one. Hermes's install scanner notes a file over 1024 KB; the bundler refuses a bundle over 1,000,000 bytes. `desktop/` holds only `plugin.js`: the app copies and lints that whole folder. Small art is a PNG in `page/shared/art/` plus an import in `shared/art/index.js` (the bundler embeds it as a data URL); device skins are served by the backend only.
- Never edit `engine/`. Never touch hardware. No wording that trips the install scanner (see the trigger list in tools/skills_guard.py; never quote the triggers in our own files).
- Verify: `node tools/bundle/bundle.mjs --check`, `python -m unittest discover -s tests -t .`, `node --check desktop/plugin.js`, `node --test 'tests/page/**/*test*.mjs'` (it includes the page scenario files `page-*.test.mjs`), the preview build, and `python tests/acceptance/broker_acceptance.py` after backend changes. Before a release: `node tools/bundle/bundle.mjs --check --same-esbuild`.

## The page's source (`page/`)

- `index.js` is the entry: the default export and the one `register()`, which calls `startPages(ctx)` (every page's own start-up work and event listeners). `sdk.js` is the only module that imports packages.
- `app/`: the shell and what every page uses. The shell: `studio-page.js` (the page shown, the data every page shares as `shell`), `nav.js`, `page-view.js` (a page's body or its tabs), `not-running.js`, `shell.css.js`, `registry.js` (checks the pages and wires them), `player/` (the one player, kept across pages). Hubs pages use: `events.js`, `slots.js`, `style.js`. Plumbing: routing, ids, RPC names, backend queries, the chat composer insert and prompt buttons, formatting, paths, the prompts several pages send, agent tool names.
- `pages/index.js` is the registry: one import line per page, in nav order. `pages/<page>/`: one folder per page: `home/`, `build/`, `setup/` (with `onboarding/` and `install/`), `prompts/`, `games/`, `emulator/` (with `beside-chat/`, the tab beside the chat). Each has an `index.js`, its front door: the descriptor (`HOME_PAGE`…) and what other pages may use from it, and a `README.md` (what it shows, tabs, events, slots, tests). A page's tabs and areas are subfolders of it: Build has `chat/` (conversation state, gateway events, actions), `transcript/`, `composer/`, `assets/`, `viewer/` and `player/` (the game inside the conversation).
- `shared/`: the bottom layer every page and the shell use: `ui/` (components), `styles/`, `art/` (the PNGs), `player/` (the frame layer every player surface uses). It never imports `#app/` or `#pages/`.
- `frame/`: the code that runs inside the player frame; built separately into `player/frame-shim.js`; imports only `frame/` and `#shared/`.
- Boundaries (ESLint, `tools/bundle/lint-rules.mjs`, run by `python tools/check.py lint`): a page imports another page only as `#pages/<page>/index.js`; pages never import the shell modules of `app/` or the registry; `app/` reaches pages only through `#pages/index.js`; `shared/` imports neither `app/` nor pages; the entry never imports pages. Every message says why the rule exists and the fix; `node tools/bundle/lint-page.mjs --fix` rewrites an import through a front door that already exports the names. A deliberate exception goes on its line with a reason: `// retrodev: allow hermretro/boundaries — <reason>`; the report lists every one. `eslint-disable` comments are ignored.
- One main component per file, named after it in kebab-case (`BuildCard` in `build-card.js`), with its private helpers. Pure logic lives in noun-named files without components (`turns.js`, `reducer.js`). Named exports only, each name unique across the tree (a front door's `export { x } from './y.js'` passes a name on and does not count).
- Imports: `./file.js` for the module's own folder, `./sub/file.js` for a folder inside it, and an alias for anything else: `#sdk` (`page/sdk.js`), `#app/`, `#pages/`, `#shared/`, `#frame/` (the folders of the same name; `ALIASES` in `tools/bundle/bundle.mjs`, used by esbuild, the lint and `tests/page/aliases.mjs`). No path climbs a folder (Hermes's install scanner notes relative paths that climb two). No import cycles (the build fails on one).
- Module state (atoms, maps, caches, listener sets) is declared once, in the module that owns it, and changed only by that module's functions; a feature with more than a little keeps it in `store.js`/`state.js`/`cache.js`. Another page learns of a change through a page event, never by reading the state. Gateway listeners start from a page's `register(ctx)`; features export `watchX(ctx)`.
- Styles: `<area>.css.js` beside the code, listed in its page's `css` (that order, then the page order, is the cascade; `app/style.js`). Classes keep their area prefix (`cs-b-*` Build, `cs-v-*` viewer, `cs-rp-*` real player, `cs-ip-*` inline player, `cs-onb-*` onboarding).
- RPC names only in `app/rpc.js` (which re-exports `app/rpc-names.js`, generated from the backend's `@rpc` declarations by `tools/bundle/rpc_names.py` when `node tools/bundle/bundle.mjs` runs; never edit it), agent tool names only in `app/tools.js`, in step with `docs/dev/CONTRACT.md`.
- Size: aim for 300 lines a file. The build fails above 400, except for the files listed in `tools/bundle/lint.mjs` (each one large component today); that list only shrinks.

## Adding to the page

Each of these touches one folder plus at most one registry line. `tests/page/registry.test.mjs` checks the
registry, and every descriptor is checked when the bundle loads (`app/registry.js`): a mistake fails the page
tests with the exact problem.

**A page.** Make `page/pages/<page>/` with `index.js` exporting `export const <PAGE>_PAGE = { id: '<page>',
label: '<Label>', Page }`, where `Page({ shell })` renders it from `shell` (the data and actions every page
shares, built in `app/studio-page.js`: `ctx`, `go(id)`, `status`, `steps`, `games`, `play(id)`, `player`…).
Add one line to `page/pages/index.js` (import it, and put it in `PAGES` where its nav segment goes), and a
`README.md` (copy `page/pages/games/README.md`'s sections; `tests/repo/test_readmes.py` fails without one).
Optional fields: `Badge({ nav })`, `pad`, `BelowPlayer`, `css`, `register(ctx)`, `events`, `listens`, `slots`,
`contributes` (all listed at the top of `app/registry.js`). Nothing in `app/` changes. Or:
`python tools/retrodev new page <page> [--label ...]` writes the folder, the registry line and the registry test's
nav list (it goes last; move it in both).

**A tab.** Make `page/pages/<page>/<tab>/index.js` exporting `{ id, label, Page }` (and, like a page,
`css`, `events`, `listens`, `slots`, `contributes`), and add it to `tabs: [...]` in `page/pages/<page>/index.js`.
`app/page-view.js` draws the tab bar and remembers the choice per page. With tabs, the page's own `Page` is not
the page's body any more: if the descriptor keeps one it renders only as a strip between the tab bar and the
chosen tab (given `{ shell, tab }`), so move its content into a tab, or drop `Page` when the tabs are the whole
page. Mention the tab in the page's `README.md`. Or:
`python tools/retrodev new tab <page> <tab>` (the folder, the `tabs` entry and the README line).

**An event.** The page it happens in owns it: add `events: { '<page>.<name>': 'what happened; the payload' }`
to `page/pages/<page>/index.js`, and call `emit('<page>.<name>', payload)` from `#app/events.js` where it
happens. To react to it in another page: from a component, `on(name, fn)` in an effect (it returns the
unsubscribe); for the plugin's whole life (even while the page is not shown), `listens: { '<page>.<name>':
(payload, ctx) => ... }` in that page's `index.js`. A listener that throws is logged and never breaks the
emitter. An undeclared name throws. List it in both READMEs.

**A slot.** The host page declares it: `slots: { '<page>.<name>': 'where it is; the props it passes' }` in
`page/pages/<page>/index.js`, and renders `jsx(Slot, { name: '<page>.<name>', props: { ... } })` (from
`#app/slots.js`) where the contributions go. Empty, it renders nothing, so declaring one changes nothing on
screen. Or: `python tools/retrodev new slot <page> <name> --doc '...'` declares it (and lists it in the registry
test); rendering the `Slot` stays yours.

**A contribution to a slot.** In the contributing page's `index.js`: `contributes: { '<page>.<name>':
[Component] }`. It lives in the contributing page's folder. `Component` gets the host's props: read the slot's
doc string in the host page's `index.js` (`slots: { ... }`) for what they are and what to return. For example
`games.cardMenu` passes `{ ctx, game, hardwareOn, item }`, where `item(icon, label, run, { disabled, why })` makes a
menu button, so a contribution returns `item(...)` (or `null` for no button); `emulator.barActions` passes
`{ ctx, game, hardwareOn }` and its contribution renders a button.

Events today: `games.coverRequested` (Games → Build), `emulator.presented` (Emulator → Build). Slots today:
`games.cardMenu` (empty), `emulator.barActions` (Games' Install button).
