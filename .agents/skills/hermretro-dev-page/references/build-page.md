# The Build page

## Build: one game, one conversation

The Build page drives an ordinary Hermes session itself instead of sending prompts to the chat:
this game's conversation, where the game also plays, with the trimmed New Game screen (idea box and the
**Build it** and **Plan first** choices). There is no games rail (user picked mockup B to give the chat room beside
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
- **New Game** creates a fresh hidden session (without a title; see [gateway calls under Page](#page)), then sends
  the new-game (or planning) prompt. It is pending in the game switcher until the library shows the game it made.
- **A game with no conversation** opens a blank one; the session is created on the first message. The composer waits
  for one creation and binding at a time and keeps the message and attachments if either is refused.
- **Stop editing** unbinds the game (`build` `unbind`) and un-hides its session (`session.set_hidden
  {hidden: false}`), so the old conversation shows up in the Hermes sidebar instead of being lost. The
  game goes back under Edit a game; editing it again starts a new conversation.
- **Guards (broker, `guard_selection`):** a library game is opened and edited only from its own conversation. A
  game's conversation that tries to create a project or select a different one is refused
  (`ONE_GAME_PER_CONVERSATION`, "start a new game from Build"). Any other chat selecting a library game, or a project
  inside a game's folder, is refused (`GAME_CHAT_ONLY`), whether or not the game has a conversation yet: the user
  opens it on the Build page, which gives it one. Such a chat may still make a new project or open one the library
  does not have, and becomes that game's conversation (`Registry.claim_new`, from the broker's `observe`). A New Game
  conversation creates its project and opens no project (`NEW_GAME_ONLY`): what it opened would stay selected after
  its new project claims it; nor does it name one in the card, present or report tools. Hermes's file tools follow
  the same rule (the library's `pre_tool_call`). No chat creates a project inside another game's folder, a library game's or any folder
  holding a `.gbsproj` (`INSIDE_ANOTHER_GAME`; the same folder is the engine's `PROJECT_ALREADY_EXISTS`, so a
  default name still moves to the next number). Selector paths are read as the engine reads them (trimmed; relative
  only against an open project). A game's conversation that has another project open is moved back to its game, and
  runs nothing while its worker cannot switch (`select_bound_game`). A game's
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
plan, createdAt, aliases}` (New Game conversations whose project does not exist yet; the newest `games.MAX_PENDING` are kept).
The first project a pending conversation creates is bound to it (`observe` → `claim_pending`);
selecting an existing game does not claim it. Unknown top-level keys in `games.json` are kept, since
every hermretro copy shares the file.
The `games` RPC returns `games[].session = {storedId, createdAt, thisProfile, profileName, exists} |
null` and `pending: [{storedId, name, createdAt, exists}]` for this profile. `exists` is read from
the profile's session database (`null` when unknown).

### `build` RPC

Params name the session `stored`, never `session_id` (the gateway would authorize it as live):
`{action: "start", stored, name?, plan?}` → `{ok, pending}`; `{action: "bind", game, stored,
replace?}` → `{ok, game, session}` (`replace` is the stored id of the conversation the page saw was
removed, and the swap happens only while the game is still bound to exactly that one; omit it otherwise);
`{action: "cancel", stored}` → `{ok, cancelled}`; `{action: "unbind", game, stored}` → `{ok, unbound}`
(only when `stored` is the game's current conversation, so a stale page cannot drop a newer one). Failures are `{ok: false, code, error}` with
`code` one of `INVALID` (also for a `replace` that is not a nonempty string, such as `true`), `NO_GAME`,
`BOUND` (the session belongs to another game), `HAS_CONVERSATION` (the game has another session and
`replace` was not set), `STALE` (the game is no longer bound to the conversation `replace` names: another
page replaced or freed it first) and `OTHER_PROFILE` (`replace` never takes another profile's conversation).

### `asset` RPC

`{path, root}` (`path` absolute, or `file://`; `root` the project folder of the game the Build page shows) →
`{ok, path, relative, name, kind, width, height, bytes, modifiedAt, dataUrl, sprite?}` for PNG, GIF, JPEG or WebP up
to `versions.ASSET_MAX_BYTES`, only from that library game's own folder or the plugin's saved frames (symlinks are
resolved first; folders are matched by identity, not spelling). An image of another game, including a game inside
this one's folder (the deepest library folder holding a file owns it, read from the registry's entries), is
`OTHER_GAME`, and so is every game image when `root` is missing or not a library game; the reply then shows the
`MEDIA:` line as inert text (`MessageTextContent` with `media: false, previewOnly: true`), so a reply in one game's
chat never shows another game's files. `sprite = {name, frameWidth,
frameHeight, animSpeed, canvasWidth, canvasHeight, palette, standing: {tiles, flip}, moving: {frames,
flip}}` from the `.gbsres` sidecar and the project: GB Studio stores sprites in four placeholder
greens with `#65ff00` as transparency, so the page paints every sprite thumbnail with `palette` (the
one its first use in a scene is painted with, else the default sprite palette) and draws the frame
that use stands in. The project lookup is cached per game until a settings, palette, scene, actor or
sprite file changes. Failures: `INVALID`, `NOT_IMAGE`, `OUTSIDE` (in no game), `OTHER_GAME`,
`TOO_LARGE`, `MISSING`. With `at` (a reply or report's time, ms) it answers the version the file had then; with
`version` (an id from `asset_info`) that kept version. Every answer carries `versionId` and `earlier`.
When history is unavailable, a readable live file can still be previewed. Requests for a specific kept
version require access to that version.

Versions: the plugin keeps a copy of a game image (up to 40 per file, named by modification time in
ns, identical rewrites skipped, under `<plugin data>/asset-versions/`, filed under the game that owns the
image: a folder that later becomes a game of its own starts with none) when a reply delivers it
(`MEDIA:` line, `post_llm_call`), a step looks at or writes it (`post_tool_call`), a build report names it,
or the page shows it. Replies and reports can still show their images after a later rewrite.

### `asset_info` RPC

`{path, root}` (as for `asset`) → `{ok, path, relative, kind, versions}`, `kind` one of `cover` (the game card's cover),
`sprite`, `background`, `ui`, `frame`, `capture`, `image`; `versions = [{id, at, file, current}]`
oldest first, exactly one `current` when history is available, otherwise empty. A sprite adds
`sprite = {name, id, type, flipLeft, states, canvasWidth, canvasHeight, animSpeed, numTiles, animations: [{slot, name, frames: [[tile]]}]}` (the
first state's animations, named by GB Studio slot: "Walk right"…; a tile is `{x, y, sliceX, sliceY,
flipX, flipY}`, 8×16, `y` up from the canvas bottom) and `palette = {id, name, colors[4]}` (the one
it is painted with in its first scene). Sprites and backgrounds add `usedIn = [{scene, sceneId, as,
count}]` and `scenes` (up to 6): `{id, name, width, height, background, actors: [{name, spriteId,
sprite, x, y, player, canvasWidth, canvasHeight, tiles, flip, palette}]}`, each actor's standing frame
for its facing, the player at the start position of the start scene. Read from the distributed
project files; nothing is compiled.

### `asset_restore` RPC

`{path, root, version}` (`path` and `root` as for `asset`) → `{ok, path, versions}`: puts a kept version back in
place, keeping the one it replaces first. Not for saved frames.
The current file stays in place if the backup or restore record fails to save. The record tells the
next history reader which two versions to keep when an interrupted restore still needs pruning.
The viewer disables Restore while its Build conversation is active. Restore answers `CONFLICT` if the engine
writer lock is held or the image changes after backup.
When the replacement succeeds but its history cannot be listed, the result is successful
with an empty `versions` list.

### `assets` RPC

`{game}` (a library id) or `{root}` (a library game's folder) → `{ok, root, assets, truncated}`, the
pictures the Build page's @ picker lists: the game card's cover first, then every image under
`assets/sprites`, `assets/backgrounds`, `assets/ui` and `assets/fonts` (symlinks leaving the game are
skipped, and so are a nested game's pictures), at most 400. Each is `{path, relative, name, file, kind, modifiedAt, bytes}`; `name` is the
sidecar's (`.gbsres`) name when there is one, `kind` one of `cover`, `sprite`, `background`, `ui`.
Within each asset folder, paths are sorted by component. `truncated` is true only when an eligible image
was left out. The page loads image data through `asset`. Failure: `NO_GAME`.

### Page

Gateway calls go to the `hermretro` profile ONLY (`studioTarget()` in `app/routing.js`: its route, or the app's
own connection when the app is on that profile). When it is missing or not answering, every Build/chat call
throws `STUDIO_PROFILE_MISSING`, the Build page shows `StudioNeeded` (Repair re-runs `studio_profile` from the
profile the plugin was installed into) and "Use in chat" copies the prompt with a notice; nothing ever runs in
another profile. Gateway calls (on that route, `host.retainProfile` held): `session.create
{hidden: true}` (no title: the canonical gateway treats it as a lookup for an existing session),
`session.resume` (history; `omit_messages` while polling), `prompt.submit`
(with `submission_id`), `session.interrupt`, `clarify.lock` (fallback `request.answer`),
`approval.respond`. The stream is `host.onEvent` filtered by `session_id`, de-duplicated by `seq`
and the delta `offset`. Questions and approvals are server requests the page never receives: while
a tool runs it reads the session's `open_requests` and renders them as cards. A backend without the
`build` RPC (-32601) keeps bindings for the visit only and names the project in the first message.

- **Studio Conversation** keeps a 46-rem message column aligned with the composer. The current request is a
  right-aligned bubble, followed by the agent's words, its work disclosure and the game result. Earlier numbered
  builds fold into rows with their number, title and any failure or unknown outcome. Opening one mounts its
  messages and media. A live correction stays in the request's turn, including work that started before it.
  Other conversation turns remain in place. A folded playable build offers Play while the game is idle.
- **Agent steps** start folded while working and after completion. The row names the running tool and the step
  count. Opening it shows live updates and keeps it open when the turn finishes. A small asset stack opens its first
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
  id, or no tool at all as the gateway resumes it); a result with `ok: false`, `isError`, an `error`, or the engine's `structuredContent.success: false` (a build that ran and stopped; its first error diagnostic is the reason) marks its step failed, live and in history. Plumbing
  (`tool_describe`, `todo`, `chromatic_build_report`…) is hidden. The words before the first step
  lead the reply, words between steps are notes inside, words after the last step close it. Steps
  keep only small args (`stepArgs`). A report keeps its whole (`normalizeReport`).
  A compact ROM result without an outcome starts as unknown. It is shown as built only if a saved snapshot
  confirms the exact stored result occurrence.
- **Build results.** Each turn that finishes a ROM or web compile gets a build number in conversation order.
  Its result shows the report title and summary, test counts, and a diagnostic and retry action for failure.
  A result can feature a sprite or background with Before and After at the turn's start and end. When an
  earlier version is available, the latest turn offers Keep and Undo. Undo restores the earlier version
  and offers to rebuild. Details opens the change list, additional image comparisons, checks and notes.
  The change thumbnails open the original images at the report capture time from its tool result, or the
  recorded tool time for older reports. Turns without reports list the pictures they made. Recorded playtest
  frames can be opened individually or scrubbed and replayed in capture order. Reply media uses the Hermes
  renderer for sound and video. Play opens the real player beneath the reply. Suggestions fill the message box.
- **Header.** The title (game switcher), one status pill (Working · 0:42 / Build #n · up to date /
  Edited since build #n / Build #n didn't finish / No builds yet) and Builds ▾: every build newest
  first, with Show to expand the build and scroll to it. Restore matches a completed build to its
  saved snapshot by reference. Compact result rows use the call ID and exact result timestamp
  confirmed for that reference. The current build offers Restore after the project changes.
  Legacy snapshots without an exact match and before-restore backups appear by date and time,
  including for games without a conversation. Backup rows also show the ID. Confirming a selection
  calls `build_restore` to save the current project and put the earlier files back. A complete restore
  submits a rebuild and opens a conversation when needed. An incomplete restore shows the file
  problem and the ID of the backup users can select in Builds. A failed rebuild submission reports
  that the files were restored. Open in full chat stays in the switcher's right-click menu and the
  stuck status.
- **@ assets.** Typing `@` (at the start or after a space) in the message box, or its @ Asset button,
  lists the game's pictures from the `assets` RPC; what follows filters by name or file, ↑/↓ and
  Enter/Tab pick, Esc closes. The pick leaves the text and is attached as an `@name` chip (sent as
  "About <path>:" like any attachment); the user's bubble shows it as `@name`.
- **New Game** keeps its two choices over a game the page draws behind them: the Nous Girl plays a
  Game Boy Color style level by herself, behind the frosted message box and choices, which take no
  part in it (the `platformer` background, `page/backgrounds/`, described in its README).
  Under the form, the games being worked on (those with a Build conversation, and New Game chats
  still being set up) stand as cartridges on the level's floor: waiting for an answer first, then the
  newest; each opens its chat, and a last "+N · All games" tile opens the games menu
  (`page/pages/build/cart-shelf.js`). The shelf hides in a short window; the level only keeps the
  ground under it flat.
- **Assets as they land.** Images a step made or looked at (`image_path`, result images,
  `assetPath`/`outputPath`, each `imported` asset of a several-asset `asset_import`, `vision_analyze`'s
  `image_url`; project-relative paths joined to the
  game's root) show as thumbnails under the step and as a "Latest" card while it works. Sprite sheets
  show one frame (a one-row sheet plays in the Latest card, CSS steps only). An image line in a reply
  (`MEDIA:<image>`) is drawn by the page too, at the version the reply delivered. Images come from the
  `asset` RPC, cached per game, path and version, four at a time. The Build page provides its game's project folder
  (`AssetGame` in `page/pages/build/assets/cache.js`: the game's, else the one the conversation's first step made),
  and every `asset`, `asset_info` and `asset_restore` call sends it as `root`. A file put back (the viewer's Restore,
  a build card's Undo) goes through `forgetAsset(path, answer.path)`: every picture of that file on screen loads it
  again, whichever spelling of its path it asked for.
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
  finished and the user can play test the game"). Under the newest build's line the game rests in a
  dark frame, its screen at twice its size with "Play build #n" at the corner (`player/play-card.js`;
  "The playable copy is not ready yet" when it is not); Play opens the real player in its place (no
  third column; a game built outside the conversation gets the same frame). It opens by itself when
  the agent presented the game that turn (`chromatic_present_game` from a Build conversation opens no
  tab beside the chat; its note shows on the player). While the agent works there is no frame, the
  build's line says "Playable again when HermRetro finishes", and the game comes back when it is done.
  Older builds say "Earlier build". It takes the live player from the Emulator page (a tab beside the chat keeps it
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
  quiet for N minutes, may be stuck" with Open full chat and Stop; "waiting for your answer";
  "Reconnecting…" after three failed polls. The game switcher shows a spinner, "Needs
  your answer" or a new-reply dot per game.
- **Questions** are asked in the message box: while one is open the box is the question (the oldest
  first), its choices a numbered list (number keys pick), "(Recommended)" shown as a grey Suggested, an
  own-answer field, Send answer once every question has one, and Stop while the agent works. Answered,
  they become a step with the answers as chips. Approvals take the box the same way, with their choices.
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
- **Provider marks** (the owner: "it needs to be their official icons"): the button, the rail and each model row
  show the provider's official logo from `page/shared/art/providers/` (taken only from the company's own site, brand
  kit or GitHub organisation; the source of each is beside it in `index.js`), in the brand's version for the theme
  on screen (the SDK's `useTheme`). A provider without one (custom endpoints, Mixture of Agents, ones Hermes adds
  later) shows its first letter, two when another provider starts the same. A new Hermes provider gets its brand
  added to that index. `tests/page/page-build-logos.test.mjs` checks representative aliases, theme variants and the letter fallback.
- **Model and effort** (user picked mockup C, "one button, one panel"; its panel redrawn after the user's
  reference, round 2 direction F1): one button under the message box, "<mark> Claude Opus 5.5 · High". Its
  560 px panel (narrower, with shorter words, where the window or the box that scrolls the composer is narrower)
  has a rail on the left (Starred, one mark per `authenticated` provider with models from `model.options`, name on
  hover; + opens Settings > Providers), the models in the
  middle (search covers every provider and groups matches under each provider's name; ids shown as names:
  `claude-opus-5-5[1m]` → "Claude Opus 5.5" + 1M tag; a star on each row, kept in the page's storage as
  `buildModelStars` because Hermes's own starred list is not open to plugins), Effort as a list on the right (Off
  only when the model can disable reasoning; Minimal, Low, Medium, High, X-high, Max; what the level is for under
  it), and a bar along the bottom. The bar has Standard / Fast only on the tab of the model in use, when that is a
  ChatGPT or Codex Subscription (`openai-codex`) or OpenAI API (`openai-api`) model whose `capabilities` list `fast`
  (not on other providers' tabs, Starred or a search); Fast shows as a bolt on the button and is sent as
  `config.set {key: 'fast', value: 'fast'|'normal'}` (read back from `session.info.fast`); picking a model without
  fast mode sets it back to normal, because Hermes's priority tier would also turn on another provider's own fast
  mode. Changes are per conversation, never the profile default:
  `config.set {session_id, key: 'model', value: '<model> --provider <slug> --session'}` and
  `{key: 'reasoning', value}`; the app's client turns both into `session.mutate` on the canonical
  gateway (a raw `config.set` model is refused there with `use_session_mutation_model`). The current
  values come from `info` of `session.create`/`session.resume` and `session.info` events. A pick made
  while HermRetro works is held ("next message", and the bar says so) and applied when the turn ends. A model that asks
  first (`confirm_required`) shows its message in the panel with Use it (`confirm_expensive_model`).
  A provider that is no longer connected shows on the button. New Game and a game with no conversation
  use the same model/provider pair for the draft chip and `session.create`: a saved pick (`buildModel`) wins,
  else use the studio default returned by `model.options` if both values are known. Clicking the displayed default
  saves it as a pick. Creation passes the chosen `reasoning_effort` and the draft's `fast` choice for a ChatGPT or
  Codex Subscription or OpenAI API model. The first message is not bound or sent if the returned session already
  has history or does not confirm the model and provider sent with the request.
  A reply names its model when it differs from the message before.
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
