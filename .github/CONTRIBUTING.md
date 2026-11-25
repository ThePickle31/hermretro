# Contributing to hermretro

Thanks for helping. hermretro is a Hermes Agent plugin for making Game Boy and Game Boy Color games for the
ModRetro Chromatic. Whatever reaches `main` is installed by users exactly as it is, so changes go through a pull
request into `dev` and CI.

## Getting set up

1. Linux or macOS (Apple Silicon or Intel), Python 3.11 or newer, Node.js 22 or newer, Git.
2. Fork the repository, clone your fork and branch from `dev`: `feat/…`, `fix/…`, `docs/…` or `chore/…`.
3. `python tools/dev setup` (ruff, the Python linter and formatter, and the page tools; development only).
4. `python tools/check.py` must pass before you push. For backend or engine changes also run
   `HERMRETRO_DEPS_ROOT=<folder> python tools/ci/prepare_toolchain.py` once (the toolchain, into a folder of your
   own), then `HERMRETRO_DEPS_ROOT=<folder> python tools/check.py full`.


## Trying a change in Hermes Desktop

1. Link your checkout as the plugin instead of installing it (the README, "Contributing": "For development, link a
   checkout instead of installing the plugin"), and enable it. The studio profile loads the plugin through its own
   link, `${HERMES_HOME:-$HOME/.hermes}/profiles/hermretro/plugins/hermretro`: check with `ls -l` that it points at
   your checkout. Setup leaves an installed copy there alone, so with one, remove that install or try your checkout
   in a throwaway Hermes home (`HERMES_HOME=<temp folder>`).
2. Page changes (`page/`): `node tools/bundle/bundle.mjs`, then reload the app.
3. Changes to `backend/`, `__init__.py`, `plugin.yaml` or `skills/`: restart the studio profile's gateway
   (`hermes -p hermretro gateway restart`);
   tools and the prompt apply from the next chat.
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
- Only the maintainer changes `engine/` (ModRetro's release with the maintainer's changes, listed in
  `engine/CHANGES.md`); CI fails a pull request from anyone else that touches it. Need an engine change? Open an issue.
- `python tools/check.py scan` must say `safe` (`.agents/skills/hermretro-dev-testing/references/install-scanner.md` lists what trips it).
- Everything works the same on Linux and macOS; differences go in `backend/system/host.py`. Windows is not supported.
- Tests never touch the real Hermes home and never run hardware tools.

## Pull requests

- One concern per pull request, against `dev`. The title is `type(scope): what it does` (`feat`, `fix`, `docs`,
  `chore`, `test`, `ci`; the scope optional): it becomes the squash commit and the release-note line.
- Fill in the template: what changed and why, and how you verified it (on which systems).
- CI must be green (**All checks pass**). The maintainer reviews and merges; first-time contributors' workflow
  runs wait for approval.
- If your pull request conflicts in `desktop/plugin.js`, merge `origin/dev`, run `node tools/bundle/bundle.mjs` and commit
  the two built files.

## More

The development skills in `.agents/skills/` (AGENTS.md lists them) hold how each kind of work is done, with their
reference pages: architecture, the page, testing, debugging. Security problems: see `.github/SECURITY.md`,
never a public issue. Everyone here follows `.github/CODE_OF_CONDUCT.md`.
