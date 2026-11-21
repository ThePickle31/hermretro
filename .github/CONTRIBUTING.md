# Contributing to hermretro

Thanks for helping. hermretro is a Hermes Agent plugin for making Game Boy and Game Boy Color games for the
ModRetro Chromatic. Whatever reaches `main` is installed by users exactly as it is, so changes go through a pull
request into `dev` and CI.

## Getting set up

1. Linux or macOS (Apple Silicon or Intel), Python 3.11 or newer, Node.js 22 or newer, Git.
2. Fork the repository, clone your fork and branch from `dev`: `feat/…`, `fix/…`, `docs/…` or `chore/…`.
3. `python tools/py/setup.py` (ruff, the Python linter and formatter) and
   `npm ci --prefix tools/npm --ignore-scripts` (page tools); both for development only.
4. `python tools/check.py` must pass before you push. For backend or engine changes also run
   `python tools/ci/prepare_toolchain.py` once, then `python tools/check.py full`.


## Trying a change in Hermes Desktop

1. Link your checkout as the plugin instead of installing it (the README, "Contributing": "For development,
   link a checkout instead of installing the plugin"), and enable it.
2. Page changes (`page/`): rebuild with `node tools/bundle/bundle.mjs` (or keep `node tools/bundle/bundle.mjs
   --watch` running) and reload the app's window; the gateway keeps running.
3. Changes to `backend/`, `__init__.py`, `plugin.yaml` or `skills/` load only when the gateway starts: restart it
   yourself (`hermes gateway restart`), then reload the app.
   `profile/` is different: it holds templates that the page's setup copies into the `hermretro` profile when it
   makes it. A restart does not change a profile that already exists, and finishing setup again keeps its
   `SOUL.md` unless that file is an unedited older template (its hash is in `OLDER_SOULS` in
   `backend/setup/studio_profile.py`). Try a template change with a fresh studio profile in a throwaway Hermes
   home (`HERMES_HOME=<temp folder>`).
4. The plugin's tools, skills and prompt exist only in the profile named `hermretro` (the page's first setup step
   makes it). To try them from another profile, start the gateway with `HERMRETRO_EVERY_PROFILE=1` in its
   environment.

## The rules that protect users

The agent guide (`AGENTS.md`) lists them; in short:

- Never hand-edit `desktop/plugin.js` or `player/frame-shim.js`: change `page/`, run `node tools/bundle/bundle.mjs`
  and commit both built files with your sources.
- Nothing under `engine/` changes outside an engine update (`docs/dev/ENGINE-UPDATE.md`).
- `python tools/check.py scan` must say `safe` (`docs/dev/INSTALL-SCANNER.md` lists what trips it).
- Everything works the same on Linux and macOS; differences go in `backend/system/host.py`. Windows is not supported.
- Tests never touch the real Hermes home and never run hardware tools.

## Pull requests

- One concern per pull request, against `dev`. The title is one plain sentence: it becomes the squash commit and
  the release-note line.
- Fill in the template: why, what changed, how you verified it (and on which systems), risks, what is not done.
  If an AI agent wrote the change, say which one.
- CI must be green (**All checks pass**). The maintainer reviews and merges; first-time contributors' workflow
  runs wait for approval.
- If your pull request conflicts in `desktop/plugin.js`, merge `origin/dev`, run `node tools/bundle/bundle.mjs` and commit
  the two built files.

## More

`docs/dev/ARCHITECTURE.md` (how it fits together), `TESTING.md`, `DEBUGGING.md`, `CONTRACT.md` (names and RPC
shapes), `STUDIO-PAGES.md` (the page). Security problems: see `.github/SECURITY.md`, never a public issue. Everyone here follows `.github/CODE_OF_CONDUCT.md`.
