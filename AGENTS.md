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
| `adapter/` | Python backend: the broker process, engine workers, RPCs for the page, the browser player server |
| `engine/modretro-chromatic/` | The vendored ModRetro engine. Hash-pinned by `release/baseline/`; changes are refused at run time |
| `desktop-src/` | Source of the Hermes Desktop page and the player frame script, one folder per feature |
| `desktop/plugin.js`, `player/frame-shim.js` | Generated from `desktop-src/` by `tools/bundle.mjs` and committed |
| `player/` | The browser player served to the page, and the device art |
| `skills/` | Skills the plugin gives the agent (adapted from the engine's own skills) |
| `profile/` | Files for the `hermretro` studio profile the plugin sets up |
| `schemas/`, `release/` | Pinned engine tool contracts and the engine's file manifest |
| `tests/` | Python unit tests, `tests/desktop/` page tests, `tests/acceptance/` real-engine run |
| `tools/` | `check.py` (all checks), `bundle.mjs` (page build), `dev/` (pinned npm tools for development only) |
| `docs/dev/` | `CONTRACT.md` (names and RPC shapes), `STUDIO-PAGES.md` (the page and the player frame) |

## Checks

One-time setup for page work: `npm ci --prefix tools/dev --ignore-scripts` (needs Node 22 or newer).

```sh
python tools/check.py            # fast: unit, bundle, page, scan (about 25 s)
python tools/check.py full       # plus the real-engine acceptance run (needs the toolchain from setup)
python tools/check.py unit page  # just these
node tools/bundle.mjs            # rebuild the generated page files after editing desktop-src/
node tools/bundle.mjs --watch    # rebuild on every save
```

CI runs the same checks. Every failure ends with a `FIX:` line naming the exact command or change. Read
CI results with `gh pr checks <n>` and `gh run view <run> --log-failed`.

## Rules that protect users

1. **Generated files.** Never edit `desktop/plugin.js` or `player/frame-shim.js` by hand. Change
   `desktop-src/`, run `node tools/bundle.mjs`, and commit both generated files with the sources.
2. **The engine is untouched.** Nothing under `engine/` changes outside a deliberate engine update.
3. **Install scanner.** One line rated high makes every install ask for confirmation; one rated critical
   blocks installs entirely. `python tools/check.py scan` must say `safe`. Things that trip it: piping a
   download into a shell; instruction verbs aimed at agent configuration file names (write "this guide"
   instead); `sudo` in workflow files; zero-width or other invisible characters; binaries; symlinks that
   leave the repository; a `package.json` at the root (it makes every install ask about Node packages).
4. **Linux and macOS, Apple Silicon and Intel.** Every change works on both systems. Locations come from
   `adapter/paths.py`; a call that exists on only one system needs a branch for the other in the same
   place. Windows is not supported.
5. **One studio profile.** The plugin's tools, skills, hooks and prompt register only in the Hermes profile
   named `hermretro`; the page's chats go only there. To try the tools from another profile while
   developing, set `HERMRETRO_EVERY_PROFILE=1` in the gateway's environment.
6. **Hardware.** Tests and CI never run the hardware tools (`flash`, `play`, `setup`, capture). They stay
   behind the user's setting and Hermes's approval prompt.
7. **Never the real Hermes home in tests.** User state lives in `~/.hermes/hermretro/` (games, library,
   downloads, broker); in tests use `tests/support.py` and point `HERMRETRO_HOME` (or the other
   `HERMRETRO_*` folders) at a temp directory. `python tools/check.py unit` runs the suite with an empty
   home folder and fails if anything is written there. The unit tests must pass on a machine without Hermes.

## How work lands

- `dev` takes changes only through pull requests, squash-merged. `main` moves only when the owner
  releases: a fast-forward to a green `dev` commit, a tag and generated release notes.
- Work in a worktree on its own branch from `dev`, named `feat/…`, `fix/…`, `docs/…` or `chore/…`. A
  checkout that a Hermes profile loads as its live plugin stays on `dev`.
- One concern per pull request. Run `python tools/check.py` before pushing, then
  `gh pr create --base dev`. The title is a plain sentence; it becomes the commit and the release-note line.
- Fill in every section of the pull request template. Say which systems you tested on, and say so when an
  agent made the change.
- Agents never merge. The owner merges.
- When two pull requests both change the page, the generated files conflict. Fix it with
  `git merge origin/dev`, then `node tools/bundle.mjs`, then commit the two generated files.
- Names that must change together are checked by `tests/test_lockstep.py`, whose opening comment lists every
  place to edit when adding a plugin tool or an RPC (manifest, registration, page names, step words, docs) and
  which also keeps the engine version in agreement.
- This guide changes in the same pull request as any command or rule it describes.

## Releases (only when the owner asks)

The version lives only in `plugin.yaml` (`tests/test_version.py` refuses copies elsewhere); versions are
patch-only (`0.0.N`) unless the owner names another.

1. A pull request `chore/release-0.0.N` that changes only the `version:` line; merge it into `dev` when green.
2. Fast-forward `main` to that `dev` commit: `git push origin <sha>:main` (never a merge commit or force).
3. `git tag v0.0.N <sha>`, `git push origin v0.0.N`, then
   `gh release create v0.0.N --verify-tag --generate-notes --notes-start-tag v<previous stable> --draft`
   (grouped by `.github/release.yml`). Read the draft, then publish it: releases are immutable once published.
4. For a release candidate: tag `v0.0.N-rc.M` on a `dev` commit and add `--prerelease`; `main` does not move.
