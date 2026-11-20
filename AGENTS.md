# hermretro: guide for agents and contributors

hermretro is a Hermes Agent plugin for making Game Boy and Game Boy Color games for the ModRetro
Chromatic. The repository root is the plugin root. Hermes installs a plugin by cloning the default branch
(`main`) with no build step, and every file in it is checked by Hermes's install scanner. So whatever
reaches `main` is exactly what users run.

This guide holds the rules and commands. Deeper references are in `docs/dev/` and the README.

## Map

| Path | What it is |
|---|---|
| `__init__.py`, `plugin.yaml` | The plugin's entry point and manifest (tools, hooks, RPCs, version) |
| `backend/` | Python backend, one folder per feature: `broker/` (the broker process, engine workers), `hermes/` (everything that touches Hermes), `setup/`, `library/`, `assets/` (RPCs for the page), `player/` (the browser player server), `system/` (locations, Linux/macOS differences) |
| `engine/` | `modretro-chromatic/`, the vendored ModRetro engine (changes are refused at run time), and `pins/<version>/` (its tool contracts and file manifest) |
| `page/` | Source of the Hermes Desktop page and the player frame script: `app/`, one folder per page under `pages/`, `shared/`, `frame/` |
| `desktop/plugin.js`, `player/frame-shim.js` | Generated from `page/` by `tools/bundle/bundle.mjs` and committed (as is `page/app/rpc-names.js`, from the backend's `@rpc` declarations) |
| `player/` | The browser player served to the page, and the device art |
| `skills/` | Skills the plugin gives the agent (adapted from the engine's own skills) |
| `profile/` | Files for the `hermretro` studio profile the plugin sets up |
| `tests/` | Mirrors the code: `backend/<feature>/` unit tests, `page/` page tests, `repo/` repository-wide checks (lock step, version, layout, portability), `acceptance/` real-engine run, `retrodev/` the development CLI's tests; `support.py` temp-folder helpers |
| `tools/` | `check.py` (all checks), `layout.toml` (the folder map), `bundle/` (page build), `ci/`, `engine/`, `debug/`, `npm/` (pinned npm tools for development only), `py/` (pinned Python tools: ruff and its settings), `retrodev/` (the development CLI) |
| `docs/dev/` | `ARCHITECTURE.md` (how it fits together, and the full folder Map), `TESTING.md`, `DEBUGGING.md`, `CONTRACT.md` (names and RPC shapes), `STUDIO-PAGES.md` (the page and the player frame), `ENGINE-UPDATE.md`, `INSTALL-SCANNER.md`, `RELEASE-CHECKLIST.md` |
| `.github/` | Workflows, templates, and `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md` for people opening pull requests or reporting problems |

Every file belongs to a folder in `tools/layout.toml`; `tests/repo/test_layout.py` fails on a file outside the map
and on Python or page source over 600 lines (it warns above 400; a split leaves every piece under 400), and
`tests/repo/test_portable.py` fails on a personal home folder, user id or name. A new folder gets a line in
`tools/layout.toml` and the same line in the Map of `docs/dev/ARCHITECTURE.md`.

## Checks

One-time setup: `python tools/py/setup.py` (ruff, pinned by hash, into the git-ignored `.dev/py`; a no-op when
current) and `npm ci --prefix tools/npm --ignore-scripts` for page work (needs Node 22 or newer).

```sh
python tools/check.py            # fast: unit, bundle, lint, page, scan (together, about 28 s on an idle machine)
python tools/check.py full       # plus the real-engine acceptance run (python tools/ci/prepare_toolchain.py first)
python tools/check.py unit page  # just these
python -m unittest tests.backend.<feature>.test_<name>   # one module (unittest; pytest is not used)
node tests/page/<name>.test.mjs    # one page test (rebuild the bundle first after editing page/)
python tools/check.py fix        # apply every automatic lint fix and the Python formatting (ruff), then lint
node tools/bundle/bundle.mjs            # rebuild the generated page files after editing page/
node tools/bundle/bundle.mjs --watch    # rebuild on every save
node tools/bundle/lint-page.mjs --fix   # the page lint's automatic fixes (boundaries between pages)
```

`python tools/retrodev check` runs the same checks through `check.py`, but only those whose input files changed
since their last pass on the branch (a cached pass prints `ok (cached)`; `--again` reruns, `--full` adds the
real-engine run and the clean install). It adds the real-engine run itself when the branch changed `backend/`,
`engine/`, `player/`, the toolchain or `plugin.yaml` (about 1 minute), the clean install (about 40 s; with the update
check when files moved or were deleted) when it changed the registration side, and the `scaffold` check (`retrodev
new` run on a throwaway copy of the tree, about 50 s) when it changed the scaffolds or the files whose structure they
parse (`tools/retrodev/policy.toml` `[checks.triggers]`; the table rows `new` writes in the docs do not count), and
nested (the full suites in a grown copy, about 110 s) when it changed `tests/repo/`, `tests/support.py` or the page
test harness (`[checks.nested_triggers]`). A
branch that adds a tool or an RPC takes about 2 minutes to check on an idle machine; several agents checking at once
on one machine can double the times. Budgets are in `tools/retrodev/policy.toml`
`[checks.budgets]`; a check over its budget twice in a row gets a warning, never a failure. Run `python tools/check.py
fix` and commit before `retrodev check`: the clean install installs the committed tree, so `check` refuses an
uncommitted one when it is due.
`python tools/retrodev check --watch` reruns the affected checks on every save. `python tools/retrodev doctor` says
what this machine is missing, each with its fix.

CI runs the same checks, plus a clean install into a throwaway Hermes home (`python tools/ci/clean_install_check.py`;
with `--update-from` it installs the newest release first and updates it to the commit)
and, when a change touches `backend/`, `engine/` or the toolchain, the real-engine run on Linux and macOS. A
nightly run repeats them against the newest Hermes and on Intel macOS. Every failure ends with a `FIX:` line
naming the exact command or change. Read CI results with `gh pr checks <n>` and `gh run view <run> --log-failed`.
At the start of a session, look at the last nightly run (`gh run list --workflow nightly.yml -L 1`) and any open
"Nightly failed" issue.

## Rules that protect users

1. **Generated files.** Never edit `desktop/plugin.js`, `player/frame-shim.js` or `page/app/rpc-names.js` (the
   page's RPC names, from the backend's `@rpc` declarations) by hand. Change `page/` or the backend, run
   `node tools/bundle/bundle.mjs`, and commit the generated files with the sources.
2. **The engine is untouched.** Nothing under `engine/` changes outside a deliberate engine update.
3. **Install scanner.** One line rated high makes every install ask for confirmation; one rated critical
   blocks installs entirely. `python tools/check.py scan` must say `safe`. Things that trip it: piping a
   download into a shell; instruction verbs aimed at agent configuration file names (write "this guide"
   instead); `sudo` in workflow files; zero-width or other invisible characters; binaries; symlinks that
   leave the repository; a `package.json` at the root (it makes every install ask about Node packages).
4. **Linux and macOS, Apple Silicon and Intel.** Every change works on both systems. Locations come from
   `backend/system/paths.py`; a call that exists on only one system needs a branch for the other in the same
   place. Windows is not supported.
5. **One studio profile.** The plugin's tools, skills, hooks and prompt register only in the Hermes profile
   named `hermretro`; the page's chats go only there. To try the tools from another profile while
   developing, set `HERMRETRO_EVERY_PROFILE=1` in the gateway's environment.
6. **Hardware.** Tests and CI never run the hardware tools (`flash`, `play`, `setup`, capture). They stay
   behind the user's setting and Hermes's approval prompt.
7. **Never the real Hermes home in tests.** User state lives in `~/.hermes/hermretro/` (games, library,
   downloads, broker), and Hermes's plugin data folder (`host._data_dir()`: history snapshots, asset versions)
   lives in the profile; `HERMRETRO_HOME` does not move that folder. In a test's `setUp`, call
   `isolated_home(self)` from `tests/support.py`: it moves both, plus its own short broker folder (`throwaway_deps`
   for downloads). A test that calls a real event emitter reaches every feature's listeners, so it needs this too.
   Import helpers as `from tests.support import ...`, never with `tests/` on `sys.path`. `python tools/check.py unit`
   runs the suite with an empty home folder and an empty `TMPDIR` and fails if anything is written to the home or
   left in `TMPDIR`, naming the test module. The unit tests must pass on a machine without Hermes.
8. **Notes stay local.** Plans, reports, logs, summaries and evidence written while working go in `notes/`, which
   git ignores. Committed documents are only those listed in `tools/layout.toml` `[docs]`; `tests/repo/test_docs.py`
   fails on any other.

## How work lands

- `python tools/retrodev` walks each change through these steps and refuses to skip one (`tools/retrodev/README.md`):
  `plan new <topic>` writes the plan in `notes/plans/` (fill it in: `plan approve` refuses the untouched template);
  `plan approve <topic> --words "..."` records the owner's go in their words; `start <kind>/<topic>` makes the
  worktree from a fresh `dev`, sets it up and writes the pull request body `notes/pr/<topic>.md` from the plan to
  fill in (docs and chore branches may skip the plan with `--no-plan`; `takeover <branch>` does the same for a
  teammate's pushed branch); `new feature|rpc|tool|event|listener|page|tab|slot|contribution ...` writes a piece
  with every registry line it needs (`--dry-run` shows the diff first, also on `dev`); `check`; `ship --title ...` stops until the body is
  filled in (writing it when missing; a dry run too), then pushes and
  opens the draft pull request only for a committed tree that passed `check`; after that a bare `ship` reuses the
  recorded title and body; `report` gives the facts for the report to the owner; `approve <n> --words
  "..."` records the owner's approval of the pull request in their words; `land <n>` takes it through up to three
  read-only review rounds, CI on its exact head and the squash merge (`answer <n> <round> <index> "..."` records
  how each finding was fixed, between rounds); `summary <n>` gives the facts for the note after it lands; `status`
  names the next step; `sync` merges `dev` in and rebuilds generated files on their conflicts; `gc` tidies merged
  worktrees.
  Exit codes: 0 ok, 1 failed, 2 waiting, 3 needs the owner; `--json` for agents.
- `dev` takes changes only through pull requests, squash-merged. `main` moves only when the owner
  releases: a fast-forward to a green `dev` commit, a tag and generated release notes.
- Work in a worktree on its own branch from `dev`, named `feat/…` (a new ability), `fix/…` (a bug), `docs/…`
  (documentation only) or `chore/…` (refactors that change no behaviour). A checkout that a
  Hermes profile loads as its live plugin stays on `dev`.
- One concern per pull request, opened with `python tools/retrodev ship` (into `dev`, after `check`). The title is a
  plain sentence; it becomes the commit and the release-note line.
- Fill in every section of the pull request template. Say which systems you tested on, and say so when an
  agent made the change.
- The owner approves each pull request once. An agent then merges only through `python tools/retrodev land <n>`:
  CI green on the exact head and the review loop done on that head (a clean round of it, or the one head that
  fixes round 3's findings, or reviews skipped because the reviewer was unavailable, recorded); a replacement pull
  request needs its own approval. GitHub auto-merge stays off.
- When `dev` moved on, `python tools/retrodev sync` merges it in. On a conflict in a source file, edit the
  conflicting hunks (never take one side of a whole file with `git checkout --ours/--theirs`: its other hunks were
  merged), `git add` them and run `sync` again; it rebuilds the generated files and makes the merge commit. Resolve only the
  conflict there; new work goes in its own commit after `sync`.
- Backend features declare their RPCs, tools, hooks and events in their own folder and connect only through
  front doors and events (`docs/dev/ARCHITECTURE.md`, "The agent half"; checked by `tests/repo/test_boundaries.py`,
  registrations pinned by `tests/repo/test_registration_snapshot.py`). Names that must still change together
  (manifest, step words, docs; the page's RPC names are generated) are checked by `tests/repo/test_lockstep.py`, whose opening comment
  lists every place to edit when adding a plugin tool or an RPC, and which also keeps the engine version in
  agreement.
- This guide changes in the same pull request as any command or rule it describes.

## Releases (only when the owner asks)

`python tools/retrodev release prepare|publish|verify` runs these steps with their gates (`tools/retrodev/README.md`,
"Releases"); it refuses without the owner's words asking for a release. By hand:

The version lives only in `plugin.yaml` (`tests/repo/test_version.py` refuses copies elsewhere); versions are
patch-only (`0.0.N`) unless the owner names another.

1. Run `docs/dev/RELEASE-CHECKLIST.md` on a real machine (a MacBook at least), or say in the release notes that
   it was not run.
2. A pull request `chore/release-0.0.N` that changes only the `version:` line; merge it into `dev` when green.
3. Fast-forward `main` to that `dev` commit: `git push origin <sha>:main` (never a merge commit or force).
4. `git tag v0.0.N <sha>`, `git push origin v0.0.N`, then
   `gh release create v0.0.N --verify-tag --generate-notes --notes-start-tag v<previous stable> --draft`
   (grouped by `.github/release.yml`). Read the draft, then publish it: releases are immutable once published.
5. For a release candidate: tag `v0.0.N-rc.M` on a `dev` commit and add `--prerelease`; `main` does not move.
