# Testing

`python tools/check.py` runs the fast checks (unit, bundle, lint, page, scan) at the same time (about 11 s; the install scan is the floor); CI runs the same ones. Every failure ends with a `FIX:` line.

| Check | Command | Time | What it proves |
|---|---|---|---|
| unit | `python tools/check.py unit` | ~3 s | The Python tests, run with an empty home folder and no Hermes; fails if a test writes there |
| bundle | `python tools/check.py bundle` | ~1 s | `desktop/plugin.js` and `player/frame-shim.js` match `page/` |
| lint | `python tools/check.py lint` | ~1 s | ESLint over `page/` (`tools/bundle/lint-page.mjs`): the boundaries between pages, the shell, `shared/` and the frame (`tools/bundle/lint-rules.mjs`), and a few correctness rules (undefined names, hooks order, duplicate keys…; unused names warn). `node tools/bundle/lint-page.mjs --fix` applies the automatic fixes; an exception is `// retrodev: allow <rule> — <reason>` on its line |
| page | `python tools/check.py page` | ~6 s | The built page in jsdom (`tests/page/page-*.test.mjs`, 226 checks over five files run in parallel), the inline player, and the page registry, events, slots and tabs from the sources (`tests/page/registry.test.mjs`) |
| scan | `python tools/check.py scan` | ~11 s | Hermes's install scanner on exactly what a commit ships says `safe` |
| acceptance | `python tools/ci/prepare_toolchain.py && python tools/check.py acceptance` | ~1–4 min | The real engine, compiler and emulator through the broker (27 checks) |
| clean install | `python tools/ci/clean_install_check.py` | ~35 s | A throwaway Hermes home installs the commit; tools register only in `hermretro` |

One-time setup for the page checks: `npm ci --prefix tools/npm --ignore-scripts` (Node 22 or newer).

## CI tiers

- **Every pull request** (`.github/workflows/ci.yml`): unit on Linux (Python 3.11 and 3.14), Apple Silicon and
  Intel macOS; bundle and page; scan; `plugins validate` and the clean install with the oldest supported Hermes.
  About 3 minutes.
- **Integration** (`integration.yml`): toolchain install (cached) and acceptance on Linux and Apple Silicon
  macOS, for pull requests that touch the backend, engine or toolchain, and on every push.
- **Nightly** (`nightly.yml`, from `main`): the newest Hermes (validate, scan, clean install) on Linux and macOS,
  and integration on Linux, Apple Silicon and Intel macOS.

The single required check is **All checks pass**.

## Where tests live

Tests mirror the code: `tests/backend/<feature>/test_*.py` for each backend feature, `tests/page/` for the page
(`page-*.test.mjs`, the shared `harness.mjs` and the browser preview), `tests/repo/` for repository-wide checks
(names in lock step, the version, the folder map and file sizes, no personal paths, the bundle, the install scan) and
`tests/acceptance/` for the real-engine run. Each folder is a package, so discovery runs from the root:
`python -m unittest discover -s tests -t .`; one file: `python -m unittest tests/backend/broker/test_leases.py`.
Shared helpers are `tests/support.py`; a test reaches another test's helpers as `from tests.backend.<feature>.<module>
import ...`.

## Rules for tests

- Never the real Hermes home: `tests/support.py` (`throwaway_profile`, `throwaway_deps`) and `HERMRETRO_HOME` /
  `HERMRETRO_*_DIR` pointed at a temp folder. A clean-install or Hermes-CLI test must use a folder outside
  `~/.hermes` (Hermes treats a home inside its real root as the real root).
- Never the hardware tools (`flash`, `play`, `setup`, capture); `device` with `command: "status"` is the only
  hardware call allowed, and only in acceptance.
- Unix sockets: keep `TMPDIR` short (`$XDG_RUNTIME_DIR` on Linux, `/tmp` on macOS); macOS caps socket paths at
  104 bytes. `check.py` does this for you.
- macOS temp folders live under `/var`, a link to `/private/var`: `.resolve()` a temp base before comparing paths.
- Names that must change together are checked by `tests/repo/test_lockstep.py`; the version by `tests/repo/test_version.py`.

## Looking at the page

`node tests/page/preview/build.mjs <out>` builds a browser preview with a stand-in SDK (needs a Hermes
Desktop checkout for its theme); open `<out>/index.html?s=<scenario>&mode=dark&p=<page>`. Scenario links are
listed on the page. Screenshot with Playwright and a short `TMPDIR`.
