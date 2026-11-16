# Testing

`python tools/check.py` runs the fast checks at the same time (about 11 s; the install scan is the floor); CI runs the same ones. Every failure ends with a `FIX:` line.

| Check | Command | Time | What it proves |
|---|---|---|---|
| unit | `python tools/check.py unit` | ~3 s | The Python tests, run with an empty home folder and no Hermes; fails if a test writes there |
| bundle | `python tools/check.py bundle` | ~1 s | `desktop/plugin.js` and `player/frame-shim.js` match `desktop-src/` |
| page | `python tools/check.py page` | ~9 s | The built page in jsdom (`tests/desktop/wizard_test.mjs`, 225 checks) and the inline player |
| scan | `python tools/check.py scan` | ~11 s | Hermes's install scanner on exactly what a commit ships says `safe` |
| acceptance | `python tools/prepare_toolchain.py && python tools/check.py acceptance` | ~1–4 min | The real engine, compiler and emulator through the broker (27 checks) |
| clean install | `python tools/clean_install_check.py` | ~35 s | A throwaway Hermes home installs the commit; tools register only in `hermretro` |

One-time setup for the page checks: `npm ci --prefix tools/dev --ignore-scripts` (Node 22 or newer).

## CI tiers

- **Every pull request** (`.github/workflows/ci.yml`): unit on Linux (Python 3.11 and 3.14), Apple Silicon and
  Intel macOS; bundle and page; scan; `plugins validate` and the clean install with the oldest supported Hermes.
  About 3 minutes.
- **Integration** (`integration.yml`): toolchain install (cached) and acceptance on Linux and Apple Silicon
  macOS, for pull requests that touch the backend, engine or toolchain, and on every push.
- **Nightly** (`nightly.yml`, from `main`): the newest Hermes (validate, scan, clean install) on Linux and macOS,
  and integration on Linux, Apple Silicon and Intel macOS.

The single required check is **All checks pass**.

## Rules for tests

- Never the real Hermes home: `tests/support.py` (`throwaway_profile`, `throwaway_deps`) and `HERMRETRO_HOME` /
  `HERMRETRO_*_DIR` pointed at a temp folder. A clean-install or Hermes-CLI test must use a folder outside
  `~/.hermes` (Hermes treats a home inside its real root as the real root).
- Never the hardware tools (`flash`, `play`, `setup`, capture); `device` with `command: "status"` is the only
  hardware call allowed, and only in acceptance.
- Unix sockets: keep `TMPDIR` short (`$XDG_RUNTIME_DIR` on Linux, `/tmp` on macOS); macOS caps socket paths at
  104 bytes. `check.py` does this for you.
- macOS temp folders live under `/var`, a link to `/private/var`: `.resolve()` a temp base before comparing paths.
- Names that must change together are checked by `tests/test_lockstep.py`; the version by `tests/test_version.py`.

## Looking at the page

`node tests/desktop/preview/build.mjs <out>` builds a browser preview with a stand-in SDK (needs a Hermes
Desktop checkout for its theme); open `<out>/index.html?s=<scenario>&mode=dark&p=<page>`. Scenario links are
listed on the page. Screenshot with Playwright and a short `TMPDIR`.
