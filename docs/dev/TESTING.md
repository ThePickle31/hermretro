# Testing

`python tools/check.py` runs the fast checks (unit, bundle, lint, page, scan) at the same time (about 11 s; the install scan is the floor); CI runs the same ones. Every failure ends with a `FIX:` line.

| Check | Command | Time | What it proves |
|---|---|---|---|
| unit | `python tools/check.py unit` | ~3 s | The Python tests, run with an empty home folder and no Hermes; fails if a test writes there |
| bundle | `python tools/check.py bundle` | ~1 s | `desktop/plugin.js` and `player/frame-shim.js` match `page/` |
| lint | `python tools/check.py lint` | ~1 s | ESLint over `page/` (`tools/bundle/lint-page.mjs`): the boundaries between pages, the shell, `shared/` and the frame (`tools/bundle/lint-rules.mjs`), and a few correctness rules (undefined names, hooks order, duplicate keys…; unused names warn). At the same time ruff over the Python (`tools/py/ruff.toml`): `ruff check` (syntax errors, unused or undefined names, likely bugs, older syntax) and `ruff format --check` (one formatting for everyone). `python tools/check.py fix` applies every automatic fix and the formatting |
| page | `python tools/check.py page` | ~6 s | The built page in jsdom (`tests/page/page-*.test.mjs`, 226 checks over five files run in parallel), the inline player, and the page registry, events, slots and tabs from the sources (`tests/page/registry.test.mjs`) |
| scan | `python tools/check.py scan` | ~11 s | Hermes's install scanner on exactly what a commit ships says `safe` |
| acceptance | `python tools/ci/prepare_toolchain.py && python tools/check.py acceptance` | ~1–4 min | The real engine, compiler and emulator through the broker (27 checks) |
| clean install | `python tools/ci/clean_install_check.py` | ~35 s | A throwaway Hermes home installs the commit; tools register only in `hermretro` |
| update | `python tools/ci/clean_install_check.py --update-from [REF]` | ~55 s | A throwaway Hermes home installs a release (default: the newest `v*` tag on `origin/main`, what users have), uses it (studio profile, a library game, a New Game chat, a running broker), then `hermes plugins update`s it to the commit: no prompt, the agent side only in `hermretro`, the library read back, the old broker replaced. Needs the tags (`git fetch --tags`) |

While working on a branch, `python tools/retrodev check` runs only the checks whose inputs changed since their last
pass there (`ok (cached)` for the rest; inputs per check in `tools/retrodev/policy.toml`), adds acceptance and the
clean install when the branch touched what they cover, and prints each time against its budget (fast checks 15 s
together, lint 2 s, the scan 15 s, others 6 s; over twice a budget is a warning, not a failure).
`python tools/retrodev check --watch` reruns the affected checks on every save; `--again` ignores the cache. A pass
on the current tree is what `python tools/retrodev ship` requires.

One-time setup: `python tools/py/setup.py` for the Python lint, and `npm ci --prefix tools/npm --ignore-scripts`
for the page checks (Node 22 or newer). The checks never install anything themselves.

## Linting and formatting the Python

ruff is pinned to one version with the SHA-256 of every published file (`tools/py/requirements.txt`);
`python tools/py/setup.py` makes a venv of the Python running it in `.dev/py` (git-ignored) and installs it with
`pip --require-hashes --only-binary=:all:`, so nothing else can land and nothing is built. Run again, it returns
at once unless `requirements.txt` changed (then `lint` says so and names the command). Settings, in
`tools/py/ruff.toml`: lines up to 120 characters, Python 3.11 syntax, the rule groups E9 F B PLE UP SIM (with
the few ignores it lists and why), quotes kept as written. The vendored engine and player, `skills/`, `tools/npm/`
and `.dev/` are not linted.

- `python tools/check.py lint` checks; `python tools/check.py fix` applies ruff's safe fixes, `ruff format` and the
  page lint's fixes, lists the files it changed, then lints again. `.dev/py/bin/ruff rule <CODE>` explains a rule.
- A deliberate exception is ruff's own `# noqa: <CODE>` on the line, followed by its reason after ` — `:
  `lock = open(path, "a+")  # noqa: SIM115 — a lock held until the process exits`. Prefer changing the code;
  a `noqa` without a reason will not pass review. (The page's escape is `// retrodev: allow <rule> — <reason>`.)
- Updating ruff: change the version in `requirements.txt`, replace the hash lines with the digests listed at
  `https://pypi.org/pypi/ruff/<version>/json`, run the setup and `python tools/check.py fix`, and commit any
  reformatting as its own commit.

## CI tiers

- **Every pull request** (`.github/workflows/ci.yml`): unit on Linux (Python 3.11 and 3.14), Apple Silicon and
  Intel macOS; bundle and page; scan; `plugins validate`, the clean install and the update from the newest release
  with the oldest supported Hermes.
  About 3 minutes.
- **Integration** (`integration.yml`): toolchain install (cached) and acceptance on Linux and Apple Silicon
  macOS, for pull requests that touch the backend, engine or toolchain, and on every push.
- **Nightly** (`nightly.yml`, from `main`): the newest Hermes (validate, scan, clean install, update) on Linux and macOS,
  and integration on Linux, Apple Silicon and Intel macOS.

The single required check is **All checks pass**.

## Where tests live

Tests mirror the code: `tests/backend/<feature>/test_*.py` for each backend feature, `tests/page/` for the page
(`page-*.test.mjs`, the shared `harness.mjs` and the browser preview), `tests/repo/` for repository-wide checks
(names in lock step, the version, the folder map and file sizes, only listed documents, no personal paths, the
bundle, the install scan) and
`tests/acceptance/` for the real-engine run, `tests/retrodev/` for the development CLI (temp git repositories with a
bare origin and a fake `gh`; its modules run their tests on threads to stay under a second). Each folder is a package, so discovery runs from the root:
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
