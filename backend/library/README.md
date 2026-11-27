# backend/library

- `games.py` owns registry storage, file locking and broker observations. `bindings.py` handles Build conversation
  ownership, session aliases, pending New Game records and the game's linked chat.
- `thumbnails.py` reads title-screen thumbnails and decodes PNG uploads.
- `project.py` handles game IDs, reads project titles, settings, the game's ROM and build files. `freshness.py` says
  whether the playable copy is the current game (`export_freshness`; the sources, `source_files`, `source_digest`,
  `sources_newer_than`).
- `shelf.py` assembles shelf entries and the smaller game object used by the emulator.
- `game_card.py` reads and writes `game.json`. `game_cover.py` validates `cover.png` (a byte-identical copy of a PNG
  under `assets/` is refused).
- `layout.py` keeps every game folder in the game layout (below); `release.py` says what a publish holds and records.
- `playtest.py` keeps the test plan's checks bound to recorded attempts and the last run's results
  (`.hermretro/playtest.json`), each result tied to its ROM, binding and check words, and the checks a build report
  took on their own evidence (`verified`, tied to the ROM and the check's words); `playtest_run.py` replays them
  on the game's ROM, one `emulator_replay` per check that judges and finishes itself in the engine. `pipeline.py` is
  the gate `chromatic_present_game` and `chromatic_build_report` hold a game to (its ROM the last build of its
  sources, its bound checks and F1 passed on it) and what a build left to replay (`after_build`).
- `installs.py` installs and updates a game from a link (below): `install_source.py` (links), `install_git.py` (git),
  `install_check.py` (what a fetched game must be), `cartridge.py` (a ROM a Chromatic cartridge can hold),
  `install_swap.py` (the update's swap) and `game_workers.py` (the broker's hold on the game).
- `rpcs.py`, `hooks.py` and `tools.py` connect the library to the page and Hermes.

## What it adds

- RPCs (`rpcs.py`): `games`, `game_build_status`, `game_thumb`, `player`, `presentations`, `captures`, `capture_image`, `build`.
- Tools (`tools.py`): `chromatic_present_game`, `chromatic_game_info`, `chromatic_playtest` (in `playtest_tools.py`:
  binds test-plan checks to recordings and replays them through the engine), `chromatic_build_report` (in
  `report_tools.py`, held to the game's test plan and the last playtest run by `report_plan.py` and `plan_checks.py`,
  its finishable run's recording read by `finish_run.py`).
- Hooks (`hooks.py`): `pre_llm_call` — tells a game's Build conversation which game it works on; `pre_tool_call` —
  blocks Hermes's `write_file` and `patch` (`file_guard.py`) from writing into a game's `.hermretro/` (wherever a link
  takes it), into a library game's folder from any chat but that game's own conversation, and into a game without its
  source (`ownership.editable`: an install without its source). The game is the deepest library folder holding the
  path, matched by file-system identity (`ownership.py`); `..` is read both by spelling and through links; a patch is
  read with Hermes's V4A grammar, a delete or move by its directory entry. Relative and `~` paths are refused (Hermes
  reads them against the chat's own working folder, which is not plugin API), and so is every write while
  `games.json` cannot be read. A terminal command is not parsed, so a shell command is not checked.
- Events emitted: `library.build_reported` (`game`: the game's id, `None` when the chat has no project; `assets`: the images the card shows, which assets keeps), `library.game_presented`, `library.game_moved` (an installed game's edited copy moved to its own folder; `old`, `new`: its library ids). Listens to: none.

## Front door

`backend.library`: `Registry`, `after_build`, `built_rom_sha256`, `source_digest`, `ROM_STEM`, `canonical_rom`, `plays_game_rom`, `installed_rom`, `install_record`, `is_installed`, `plays_in_shell`, `rom_only_record`, `verified`, `shell_rom`, `no_shell_rom`, `build_allowed`, `record_test_build`, `editable`, `folder_lock`, `game_id`, `valid_id`, `cover_path`, `project_file`, `has_web_export`, `web_dir`, `web_rom`, `file_sha256`, `read_json`, `SELECTORS`, `PNG_MAGIC`. Standard library only (the broker and the player import it).

## Tests

`tests/backend/library/`.

Read-only paths use `host.try_connect` to reach an already running broker. The tests use
`FakeBrokerClient` from `tests/support.py` and guard against starting the broker or invoking the engine.

## games.json

`<hermretro home>/library/games.json` (`paths.library_dir()`, `HERMRETRO_LIBRARY_DIR` overrides; `Registry`), written under `games.lock` and replaced atomically. Unknown top-level keys are kept. Times are Unix seconds (floats). An absent file starts an empty registry. A read or parse failure prevents replacement.

- `version`: `1`.
- `games`: game id (`game_id(root)`: the first 12 hex digits of SHA-1 over the real project path; `valid_id` accepts exactly that) → entry:
  - `id`, `projectRoot` (the real path), `title` (the `.gbsproj` name, else the web export's, else the folder name), `kind` (`gbstudio` with a `.gbsproj`, else `gbdk`).
  - `addedAt`: when the library first recorded the game. Never changes.
  - `updatedAt`: the last time the library recorded something about the game: the broker saw it created or selected (`project_create`, `project_create_blank`, `project_select`), built (`rom_build`) or exported (`web_preview` open), or `chromatic_present_game` showed it (`Registry.upsert` and `Registry.present`; each `games` RPC also adds projects the running broker has selected that the library lacks, setting it only for those). Binding a conversation, editing the game card or a thumbnail does not change it. The Games page lists games newest `updatedAt` first: this is what "recent" means. Nothing records when the user opened a game.
  - `chat`: `{conversationId, sessionId, profile}` of the chat that last selected, created (with `select`), built, exported or presented it (the seeded entries carry only `sessionId`).
  - `lastBuild`: the last `rom_build` the broker saw: `{t, ok, rom (path or null), sha256 (or null), error (`games.ERROR_CHARS`, 240, characters at most, or null), sources?}` (`sources`: after a successful build, `freshness.source_digest` of the sources the broker took before it started, kept only when they are the same when it ends; `pipeline.rom_state` compares it with the current one and never passes a build without it).
  - `lastWebExport`: `{t, sources}` of the last successful `web_preview` open into the game's own `build/web` (the engine may reuse an export without rewriting it); `sources` is `freshness.source_digest` of the game's sources (`freshness.source_files`) at that moment, which `export_freshness` compares with the current one.
  - `presented`: `{t, note, unfinished?}` of the last `chromatic_present_game` (`note` may be null; `unfinished`: `{request, notVerified[], notCurrent?}` when it was shown before it passed its checks).
  - `initialPlan`: the mode recorded when New Game first bound the project. True for Plan first, false for Build it.
    Kept across conversation changes. An older entry can still carry the mode in its session. For an older
    conversation without a saved mode, Studio looks for planning files written after it was bound and checks
    for activity that predates it.
  - `session`: the game's Build conversation, `{storedId, profile, createdAt, aliases, plan?, edit?}` (`aliases`:
    up to 16 later session ids of it, since compression rotates them, `plan`: true when it began with Plan first,
    `edit`: true when Edit opened a game with no recorded New Game mode). Absent when the game has none.
- `presentations`: the last 100 presentations, oldest first: `{gameId, t, note, title, sessionId, conversationId, profile, unfinished?}`.
- `pending`: pending builds, the Build page's New Game conversations whose project does not exist yet, stored id → `{storedId, profile, createdAt, name, plan}` (the newest `games.MAX_PENDING` are kept). Written by the `build` RPC's `start` (`Registry.build_start`) and removed by its `cancel` (`Registry.build_cancel`) or when the conversation's first project claims it (`claim_pending`).

`Registry.load()["games"]` holds raw entries, including games whose folders are gone. The registry key determines
the game id used by the shelf, chat bindings, and thumbnails. The `games` RPC reads one snapshot for seeding,
the games, pending conversations, and chat ownership. It skips registered broker lane roots and rereads the
snapshot after attempting to register a missing root under lock. `Registry.library_listing()` returns the games
described through `shelf.describe` in descending `updatedAt` order and the IDs of unreadable entries.
The emulator checks one game through `game_build_status`, including whether its project is unavailable or gone.
That RPC reads the build files and chat link, while shelf descriptions also inspect source timestamps and card
files. A recorded native ROM path that cannot be read does not invalidate a healthy web ROM. The shelf keeps a
game whose web ROM cannot be read, with `web: null`, and `game_build_status` reports `UNAVAILABLE` if the export
exists but its ROM cannot be read. Card display validation and image encoding share a cache based on the cover file's identity. Presentation
validates the current cover and checks for copies from `assets/` on every call.

Automatic capture fills a missing thumbnail once. Thumbnails are `<library>/thumbs/<id>.png`; the card is the project's own `game.json` and `cover.png` (`game_card.py`).

Which title the user sees: the card's `title` (the project's `game.json`, set by `chromatic_game_info`; `game_card.scaffold` writes a starter card with the project's name), which the `games` RPC answers as `displayTitle` and the pages show (`game.displayTitle || game.title`). The registry's and the RPC's `title` is the project's own name (`project.project_title`: the `.gbsproj` name, else the web export's, else the stored title or folder name).

## The game's ROM

Every build of a project writes one ROM, `project.canonical_rom(root)` (front door `canonical_rom`): `build/game.gbc`,
or `build/game.gb` when `project/settings.gbsres` says `colorMode: "mono"`. The broker sets `chromatic_rom_build`'s
`outputPath` to it and refuses any other (`game_rom_arguments` in `backend/broker/broker.py`, code `ROM_PATH`); a
standalone C build (`sourcePath`) is not a project build. The engine writes that ROM's bytes into the web export of the
same sources (`engine/CHANGES.md`), so `export_freshness` counts a copy that plays other bytes as stale, except in a
project with batteryless saves on, whose web copy GB Studio compiles without them. The shelf's
`rom` is that file; a game last built before it existed falls back to `lastBuild.rom`, then to the web export's ROM.
Other ROMs left in `build/` are never the game.

## The game folder

Every game has one layout from the moment it is made (`layout.py`), so it can be published later, alone or with its
source, and updated without being reshaped:

- **game** (every publish): `game.json`, `cover.png`, `README.md`, `CHANGELOG.md`, `LICENSE`, `.gitignore`
  (`project.GAME_FILES`) and the ROM, `layout.game_rom(root)`: `project.canonical_rom(root)`, or for a game
  installed without its source the `build/game.gb[c]` its `game.json` names.
- **source** (a publish with the source): the `.gbsproj`, `project/`, `assets/`, `plugins/`, `art/`.
- **local** (never published): `build/` but the ROM, `docs/` (the agent's plans), `scratch/` (its helper scripts and
  working files), `captures/`, `save-states/`,
  `artifacts/`, `node_modules/`, `.hermretro/`, and anything else (`check` warns about an unknown top-level entry).

`layout.ensure(root)` runs when a project is created (`Registry.observe`), whenever the shelf describes a game
(`shelf.describe`) and after `chromatic_game_info` changes the card. It gives the game an id (32 hex digits, the same
on every machine, unlike the library's path id) kept in `.hermretro/identity.json` and copied into `game.json`
(`id`), `gameVersion` (`0.1.0` until a release raises it) and `rom` in `game.json` (`game_card.set_fields`; the card's
own `version` is its schema), writes `README.md` from the card, `CHANGELOG.md` and `.gitignore`, and restores an
edited id. It rewrites only files whose first line says hermretro made them (and a template project's own README),
adds `/scratch/` to a `.gitignore` of the user's own that has no line for it, and never moves or deletes anything; for a game installed without its source it only keeps the author's id. None of
these files is game source (`freshness.source_files` leaves them out). `layout.new_identity` makes a copy (a remix) a
game of its own: a new id, the first version, a fresh changelog, no publish or install record, and `remixOf: {id,
version}` in `game.json`.

`layout.check(root)` answers `{ok, problems, warnings}` (each `{code, path, message}`), which the games RPC returns
as `layout`. A problem (`NO_PROJECT`, `NO_ROM` for a game without its source, `NO_SOURCE`, `CARD_UNREADABLE`,
`ID_CHANGED`) makes `chromatic_present_game` refuse with `LAYOUT`; a warning (`UNKNOWN_ENTRY`, `OWN_README`) shows the
Games card's Layout tag.

`publish_ready.py` is whether a game may be published: `readiness(root, source=..., last_build=...)` (layout, a
complete card naming a licence whose `LICENSE` it has, a ROM that is the last build of its sources, fits a Chromatic
cartridge and is the one `game.json`'s `romSha256` names, the project for a source publish, nothing `scan` blocks, and
an install of exactly the published files passing the installer's own checks), and `scan(root, source=...)`
(`publish_scan.py`: secrets, home-folder paths, files an install would refuse, and the code under `plugins/`).
`release.py` is what a publish holds and records (nothing reaches the network): `prepare_release(root, version, notes)`
before the commit (`gameVersion`, one changelog entry, the README), `files(root, source=...)` (exactly what to commit:
no hidden files, links or linked folders), and after the push `record_publish` (`.hermretro/publish.json`: `{repo,
commit, version, source, payload, t}`, `payload` being `payload_digest`); `published`, `unpublished_changes` and
`next_version` read it. `record_install`/`installed` keep where an installed game came from, and `local_edits`
compares the game's files with its `fingerprint` (`installed_digest`, below).

`licence.py` holds the licences a card may name (`LICENSES`) and the `LICENSE` text of each; `layout.ensure` writes
it (never over a `LICENSE` of the user's own; the digests of those it wrote are `.hermretro/licence.json`, which an
update never carries; in a game made here the engine template's `LICENSE`, GB Studio's own that every new game starts with, is replaced;
an installed game's `LICENSE` is always its author's). After each successful build of a game's ROM, `build_record.record_build` records that file's
`romSha256` and `builtWith` (the engine, and GB Studio's version and commit when the CLI the build ran is the one the
toolchain's setup installed) in `game.json`; `layout.ensure` gives an older game its `format`. Two library folders that hold
one game (one id) carry `duplicateId` in the games RPC.

## Installing a game from a link

`installs.py` installs a published game from a link and updates it, the way Hermes installs a plugin from git (written
again here: Hermes's helpers are not plugin API). Nothing here is on the page yet; the page and the agent reach it
later, passing `workers=game_workers.BrokerWorkers()`.

- **Links** (`install_source.resolve`): `owner/repo`, `owner/repo/sub/dir`, `owner/repo#sub/dir`, a GitHub page or
  clone URL (`…/tree/<rest>`), SSH (`git@host:path`, `ssh://host/path`) with `#sub/dir`, and `file://` only where the
  caller allows local sources (`allow_local`, tests). Only HTTPS to github.com and SSH otherwise; a link with
  credentials (a password or token in it, a query) is refused (`BAD_LINK`), never scrubbed. `…/tree/<rest>` is
  settled against the repository's branches and tags, the longest that `rest` starts with winning (`feature/demo`
  may be a branch or `feature` and a folder); a link without one gets the default branch, so a source always records
  its branch. A source read back from an install record is checked again the same way before git sees it.
- **Same source** is the same repository and folder in it (`Source.canonical`: no branch, user name or `.git`); the
  branch may differ, and a reinstall from another branch updates the game to the branch reviewed.
- **git** (`install_git`) never prompts and never reads the user's git configuration, hooks, credential helpers or
  `GIT_*` settings; every step has a timeout and its output is capped. A GitHub URL refused anonymously is tried once
  more with the user's token (`GITHUB_TOKEN`, `GH_TOKEN`, else `gh auth token --hostname github.com`) as a one-shot
  header in git's environment, never in its arguments or a file, with redirects off. `ls-remote` runs in a
  temporary folder, never inside a checkout.
- **A fetch** is shallow and partial (`--filter=blob:limit=20m`, `--no-checkout`). Its tree is listed first
  (`install_git.tree`) and refused before checkout for a link, a submodule, a file over 20 MB (or left out by the
  filter), more than 5000 files or 50 MB, or two paths that are one on a Mac's disk (letter case, Unicode spelling).
- **What is taken** (`install_check.take_payload`): only what the game's mode publishes. A game alone (`game`): the
  game files and the ROM its `game.json` names; with its source (`game+source`, one regular `.gbsproj`): the
  `.gbsproj` and the source folders too, hidden files included. Everything else (`build/web`, other build output,
  notes, another machine's `.hermretro/`) is left behind and deleted: no fetched browser code is ever served, the
  playable copy is made again here. Source folders without a `.gbsproj` are refused (`SOURCE_WITHOUT_PROJECT`), as
  is a `.gbsproj` that is not a file (`BAD_PROJECT`) or more than one.
- **The check** (`install_check.check`, `cartridge.inspect`): a `game.json` of at most 64 KB with a game id and a title,
  a `format` this hermretro reads (`layout.FORMAT_VERSION`; newer is `NEWER_FORMAT`), a ROM at `build/game.gb[c]` that
  a Chromatic cartridge can hold (32 KiB times a power of two up to 8 MiB, matching its header; the Nintendo logo and
  both checksums; a cartridge type GB Studio or GBDK writes, `cartridge.CARTRIDGE_TYPES`; `.gbc` only for a colour
  game), equal to the card's `romSha256`, which a game alone must have (`NO_ROM_SHA`), a usable cover (its size read
  from its header before it is decoded, and never decoded past what that size needs), and the project's folder for a
  game with its source. A game with its source installs either way, but is built here only with the user's consent
  (`needsBuildConsent`; `plugins` lists its plugin files for them to see), see the test build below.
- **`inspect(link)`** answers what the link holds (title, id, version, format, mode, ROM, cover, README, problems,
  `needsBuildConsent` and `plugins`, the games that already have its id) with the exact `commit` and `source` (`{canonical, url, ref,
  subdir}`). **`install(source, commit, workers=)`** installs that commit (`SOURCE_MOVED` when the branch moved), gives
  it its layout and record and renames it into place (`<Title>`, `<Title> 2`, …), then registers it; a folder an
  earlier install placed but did not register is found by its id and registered instead of copied. `testBuildDue`
  says a game with its source has not been built here from the commit installed; `allow_build=True` (also on an
  update, and on installing the same commit again) is the user's consent, and then it is built at once.
- **One id per machine**: installing a game the library has from the same source is an update; from another source it
  is refused (`ALREADY_HAVE`).
- **`check_update(root)`** reads the branch with `git ls-remote`. **`update(root, workers=, choice=)`** installs the
  newest commit of the recorded branch over the game (`install_swap`): it keeps the user's local files (`docs/`,
  `captures/`, `save-states/`, `scratch/`, `build/`'s other files but the ROM and `web/`, `.hermretro/`), merging
  folders, and keeps a file whose name the update now uses beside it as `<name> (yours)`; it drops the game's
  recorded build and playable copy. A game edited since it was installed answers `needsChoice` until the user picks
  `keep_mine`, `take_theirs` or `keep_both`: the edited copy becomes `<Title> (edited)`, a remix with its own id
  (`layout.new_identity`, its changelog kept) that keeps the library entry (its chat, session and builds) and, through
  `library.game_moved`, its build history; the new version at the old place starts with a fresh entry. A source that
  now holds another game is refused (`ANOTHER_GAME`).
- **Locks.** Each game id has one install or update at a time (`<games>/.hermretro-installs/<id>.lock`, outside every
  game folder), from the id check to the registration; names and folders in the games folder change under its
  `games.lock`, so no install claims a game's name while an update has it vacant. An update also holds the game
  folder's lock (`game_card.folder_lock`, which follows the folder when it is renamed; a history restore takes it too)
  and the broker's hold on the game (`hold_game`, `backend/broker/holds.py`): `GAME_BUSY` while a conversation has the
  game open, and conversations that open it meanwhile are refused; releasing it closes a worker that has the old files
  loaded. Local edits are checked again right before the swap.
- **Nothing is lost.** The old folder is deleted only once the new one is in place and registered. A failed step puts
  everything back; when even that fails, the old copy is kept in `<games>/.hermretro-installs/recovered/` and the error
  (`RECOVERY_NEEDED`) names it.
- **The record**, `.hermretro/install.json`: `{source: {canonical, url, ref, subdir}, commit, mode, rom: {path,
  sha256}, fingerprint, fingerprintVersion, installedAt}` (`url` carries no credentials; `rom` is the ROM the install
  checked). `installed_digest` (the `fingerprint`, version 3) covers the game files but the README, `.gitignore` and
  `LICENSE` hermretro writes and `game.json`'s fields it writes itself (`layout.MANAGED_FIELDS`: `format`, `romSha256`,
  `builtWith`), every file of the project and the source folders (hidden ones too), and for a game alone its ROM; a
  game with its source rebuilds its ROM, so its ROM and build output never count as an edit, and a game alone that
  gains a project counts. A record with no `fingerprintVersion` (version 2, the whole `game.json`) is compared as it
  was made, with or without the fields this hermretro now adds, and an untouched one is upgraded in place.
  `release.installed_rom(root)` (front door) is a game alone's checked ROM, `{romPath, sha256, source, commit}`, while
  it is still those bytes; the shelf shows that ROM.
- **Ids.** The game id in `game.json` (32 hex digits, `layout.game_identity`) is the same on every machine and through
  every publish and install; the library's id (`game_id`, 12 hex digits of the folder's path) is this machine's, and
  changes when a folder moves (`Registry.move`).
- **Out of scope here**: building an installed game's source runs its project's own content through GB Studio
  (plugins, custom HTML header settings), its own trust boundary, for the build step.
- **Playing it** (`play.py`): an installed game always plays its ROM in the player's shell (the bundled GB Studio
  player the demo cartridge uses, `player/web`), with its source or without, never a web export: a web export is GB
  Studio's `index.html` with the project's settings in it, and GB Studio's custom HTML header setting lets a project
  put its author's script there, so even a copy built here from imported source could run that script. Every ROM the
  shell plays is read once (`verified`: a regular file in the game's folder reached through no link, at most 8 MiB),
  and the player serves exactly those bytes under a URL pinned to their SHA-256 (`rom-<sha>/`; 409 once they
  changed). A game without its source (`rom_only_record`: installed so, or the edited copy an update kept, whose
  `.hermretro/kept-rom.json` keeps the checked ROM) plays only its checked ROM while it is those bytes: the shelf
  shows no other file in `build/` for it, and `romChanged` when that ROM changed. One with its source plays its own
  `build/game.gb[c]`. The games RPC describes that ROM as its `rom`/`webExport`/`web` (`shell: true`);
  `chromatic_present_game` takes a game alone's checked ROM as current (`play.playable_freshness`,
  `pipeline.rom_state`), its test plan's checks still applying.
- **Its conversation**: a game alone has no project; its own chat's worker has its folder as its workspace and runs
  only reads, the emulator and the hardware tools on its checked ROM (`backend/broker/installed.py`). The Install on
  Chromatic prompt goes to the game's own Build conversation and claims only what was verified for its very ROM.
- **The test build** (`install_build.py`): building a game with its source runs its author's code here (its plugins,
  the project's own engine in `assets/engine/`, compiler settings GB Studio hands to a shell), so it waits for the
  user's consent, `install.json`'s `buildConsent: {commit, digest, at}` for the commit installed and the digest of its
  source as installed (`sourceDigest`; an update asks again, the user's own edits since do not). Then
  `BrokerWorkers.test_build` builds it once in the broker (`test_build`), under an exclusive hold and the game's
  folder lock, which records `testBuild: {sha256, commit, matches, t}` (`matches`: the ROM it was installed with, the
  author's `romSha256` the install checked, never what `game.json` says now) and an ordinary `lastBuild`, so it can
  be presented like a build in its chat. Builds are repeatable, so the same source gives the same bytes.

Tests: `test_installs.py`, `test_install_swap.py`, `test_install_git.py`, `test_install_source.py`,
`test_cartridge.py`, `test_game_workers.py`, `test_play.py` (real git repositories through `file://`),
`tests/backend/broker/test_game_holds.py`, `tests/backend/broker/test_installed_chat.py`,
`tests/backend/history/test_moved_game.py`, `tests/acceptance/installed.py`.

## Captures

Screenshots and videos saved from the player live in `<project>/captures/` (the demo cartridge's in `<library>/captures/demo`): `captures_dir(root, game_id)` in `backend/player/captures.py` (not in the player's front door) names the folder, and `player.list_captures(root, game_id)` (`from ..player import list_captures`) lists its media files newest first as `{id, path, kind, createdAt, file}` (`kind` from the `.json` sidecar, else `screenshot` for a PNG and `video` otherwise; `createdAt` an ISO time; there is no size field: `stat` the `path`). The `captures` RPC (`rpcs.py`) reads them through `list_captures` and answers `{path, kind, createdAt, url}` for each. Writes go through `save_capture`: the `capture_image` RPC saves a page-sent game-screen PNG there as an `annotation` capture, and the player server's `codex-captures` POST saves the player's own.

## Save states

The player's save states live in `<project>/save-states/<build digest>/<id>.gbstate.json`, written by the engine's
web preview (`engine/src/web-preview-states.js`, `PreviewStateStore`); the plugin only keeps them
out of source checks and snapshots (`project.NOT_SOURCE`, `backend/history/snapshots.py`). `<build digest>` is the
SHA-256 of the JSON `{romSha256, runtimeSha256, sourceRevision, cartridgeType}` (so each build has its own folder) and
`<id>` the SHA-256 of the file's canonical text. Each file is one JSON object (`engine/src/web-annotations/save-state.js`):
`format` (`codex-gb-studio-save-state`), `version` (`1`), `identity` (that build identity), `frame`, `createdAt` (an
ISO time), `title` (160 characters at most), and `state`, `framebuffer`, `sgbFramebuffer`, each `{encoding: "base64",
byteLength, sha256, data}` (1 MiB decoded at most). Each build keeps its newest 8 (`MAX_PREVIEW_STATES`; a save
prunes older ones) and refuses a save once its folder holds 64 entries.

## Project files

What the plugin reads from a GB Studio project (the engine writes them; `backend/assets/sprites.py` `_project_index` reads them for the Build page's assets):

- `<root>/project/scenes/<folder>/scene.gbsres`: one scene, a JSON object with its `name` and `id` (and `_index`, its order); its actors are `<root>/project/scenes/<folder>/actors/*.gbsres`.
- `<root>/project/settings.gbsres`: the project's settings (JSON).
- Captures (screenshots, recordings, the page's annotated images; the plugin writes these, not the engine): media files directly in `<root>/captures/`, listed newest first by `player.list_captures(root, game_id)` and saved by `player.save_capture` (`backend/player/captures.py`). The demo cartridge has no project, so its captures live in `<library>/captures/demo/`. Get the right `root` for any game id with `player.capture_root(game_id, host._game_root)` (None for an unknown game), as the `captures` and `capture_image` RPCs and the player server do.
- `<root>/project/palettes/*.gbsres` (`id`, `colors`) and the sidecars `<root>/assets/sprites/*.gbsres` and `<root>/assets/backgrounds/*.gbsres` (`id`; the image is the same name without `.gbsres`).

## Adding here

Every place each piece touches is in `.agents/skills/hermretro-dev-architecture/references/architecture.md`, "Adding things".

- an RPC: an `@rpc("<name>")` handler in `rpcs.py`; one about one game takes a `game` param and answers `NO_GAME` unless `host._game_root` finds it.
- card state: `game_card.status(root, strict=True)` answers `{complete, missing, problems, cover}`,
  `game_card.cover_problem(root, strict=True)` only the cover's problem text by the same rules (None when usable) and
  `game_card.next_step(missing)` the sentence telling the agent what to fill in. `game_card.scaffold(root, title)` writes a
  starter card (title only) when there is none; every other card change is saved by `game_card.update(root, fields,
  cover_source=..., build_sha=..., default_title=...)`, called only by `chromatic_game_info` (`tools.py`). Its result's `was_complete` is the strict completeness before
  the change: `result["status"]["complete"] and not result["was_complete"]` is the moment the card became complete.
- a tool: its schema, handler and `Tool(...)` entry in `tools.py`. A tool that acts on the current game takes the project from `tool_args.tool_project(tool, args, kwargs)` (the `project` argument, else this chat's; a game's Build conversation gets only its own game), answers failures with `tool_args.tool_error(message, code, next_step)` (the next step tells the agent what to do) and reads the library with `host._registry()` (`from ..hermes import host`, looked up at call time so tests can patch it). Import them from `tool_args.py`, never from `tools.py` (they live in `backend/hermes/tool_args.py`, which other features' tools import).
- a game in a test: `make_library_game(isolated_home(self), "<name>")` (`tests/support.py`) is ready to present (a
  ROM, a fresh web copy, a complete card); `web=False` gives one with no playable copy, `card=False` one with no card
  (`built=False` drops only the native ROM), and it answers `(game id, root)` either way
  (`tests/backend/library/test_library_fixture.py`). Pictures for the Assets panel: `add_images(root, count)` writes
  real PNGs into `<root>/assets/sprites/` (`folder="backgrounds"` etc.), as `tests/backend/assets/test_asset_list_limit.py` does.
- splitting `tools.py` past 400 lines: each `<name>_tools.py` holds its schemas, handlers and its own `TOOLS = (Tool(...), ...)`, and `tools.py` takes them in with `from . import game_tools`. The `TOOLS` order is the order Hermes registers them in: existing tools moved out keep their places (put `*game_tools.TOOLS` where the moved `Tool(...)` entries were: moving `chromatic_game_info` gives `TOOLS = (Tool(PRESENT_TOOL, ...), *game_tools.TOOLS, Tool(BUILD_REPORT_TOOL, ...))`), and a new tool goes last. A tool module imports `tool_error` and `tool_project` from `tool_args.py`; a name a handler still uses is imported in the module that uses it. Patch dependencies in the module that defines the handler (for example, `mock.patch.object(game_tools, "emit")`).
- an event: declare `"library.<what happened>"` in `EVENTS` (`__init__.py`) with a function in `emits.py` that emits it, and call `emits.<what happened>(...)` (`from . import emits`) where it happens.
- changing an event's payload: edit the `emit("library.<name>", ...)` call in `tools.py` (or `emits.py`'s function, when it has one), the `EVENTS` description in `__init__.py` (each key with what it holds and its type, e.g. `root=<the project folder, str>`), the `.agents/skills/hermretro-dev-architecture/references/contract.md` events row and its test (`tests/backend/library/test_build_report.py` for `library.build_reported`; `tests/backend/library/test_event_<name>.py` for one `new event` wrote), and every listener that reads the key (`backend/assets/listeners.py` hears `library.build_reported`).
- a listener: an `@on("<feature>.<event>")` function taking `**_payload` (so a new payload field never breaks it) in this folder's `listeners.py`, its test, "Listens to" above and the CONTRACT events row's "Heard by". A listener reaches the library with `host._registry()` and logs with `host.logger` (`from ..hermes import host`), as a tool does: `listeners.py` is Hermes-side and the broker never imports it (`tests/repo/test_broker_imports.py`). What stays standard library only is the front door, `__init__.py` and the modules it imports (the broker imports it): never import `listeners.py`, `tools.py` or `backend.hermes` there. Listeners run synchronously in the emitting process and thread on the Hermes side (the gateway, a plugin host or a turn process), so module state a listener keeps is that process's own; state other processes must read goes in a file under `backend.system.paths.hermretro_home()`, written atomically (a temp file, then `os.replace`, as `games.json` is), not in module state.
- a field in the games RPC answer: `Registry.describe` (`games.py`), the key set pinned by
  `tests/backend/library/test_games.py` (its failure message names these places), the `.agents/skills/hermretro-dev-architecture/references/contract.md` games row
  and the `.agents/skills/hermretro-dev-page/references/player.md` games JSON. `rpcs.py` drops `updatedAt` before answering.
- a hook: `@hook("post_tool_call")` on a callback in `hooks.py` (`needs_ctx=True` for a factory given the ctx). A hook name other features already use is chained after theirs in `backend/features.py` order; a new name goes under `provides_hooks` in `plugin.yaml`.
