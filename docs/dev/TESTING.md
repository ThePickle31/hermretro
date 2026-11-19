# Testing

`python tools/check.py` runs the fast checks (unit, bundle, lint, page, scan) at the same time (about 12 s; the install scan is the floor; machines and load differ, so read every time here as a rough guide); CI runs the same ones. Every failure ends with a `FIX:` line.

One test module: `python -m unittest tests.backend.<feature>.test_<name>` (unittest; pytest is not used), or `-k <pattern>` for some of its tests. One page test file: `node tests/page/<file>.test.mjs` (each file's first lines say so); a scenario on `harness.mjs` (`page-*.test.mjs`) also takes an optional node_modules folder, relative or absolute (`node tests/page/page-games.test.mjs tools/npm/node_modules`; without one it looks where `tools/bundle/node-modules.mjs` says).

| Check | Command | Time | What it proves |
|---|---|---|---|
| unit | `python tools/check.py unit` | ~9 s | The Python tests, run with an empty home folder and no Hermes; fails if a test writes there |
| bundle | `python tools/check.py bundle` | ~1 s | `desktop/plugin.js` and `player/frame-shim.js` match `page/` (each banner's `sources: sha256` covers whole folders: all of `page/` for the bundle, `page/frame/` and `page/shared/` for the shim, so an edit in `page/shared/` changes the shim's `sources` line even when the shim bundles none of it; commit that line with the edit) |
| lint | `python tools/check.py lint` | ~1 s | ESLint over `page/` (`tools/bundle/lint-page.mjs`): the boundaries between pages, the shell, `shared/` and the frame (`tools/bundle/lint-rules.mjs`), and a few correctness rules (undefined names, hooks order, duplicate keys…; unused names warn). At the same time ruff over the Python (`tools/py/ruff.toml`): `ruff check` (syntax errors, unused or undefined names, likely bugs, older syntax) and `ruff format --check` (one formatting for everyone). `python tools/check.py fix` applies every automatic fix and the formatting |
| page | `python tools/check.py page` | ~6 s | Every `tests/page/**/*test*.mjs` with `node --test`; it reports `N files, M checks passed, K failed` (each scenario file's checks, from its last line, plus each `node:test` test). The built page in jsdom (`tests/page/page-*.test.mjs`, the files run in parallel), the inline player, and the page registry, events, slots and tabs from the sources (`tests/page/registry.test.mjs`) |
| scan | `python tools/check.py scan` | ~11 s | Hermes's install scanner on exactly what a commit ships says `safe` |
| scaffold | `python tools/check.py scaffold` | ~4 s | `retrodev new` of every kind on a copy of the repository passes lint, the bundle, the structure tests and the page tests there (`tests/retrodev/test_scaffold_tree.py`; in `full`, `retrodev check --full`, CI's page job, and `retrodev check` when a branch changes the scaffolds) |
| acceptance | `python tools/ci/prepare_toolchain.py && python tools/check.py acceptance` | ~1–4 min | The real engine, compiler and emulator through the broker |
| clean install | `python tools/ci/clean_install_check.py` | ~35 s | A throwaway Hermes home installs the commit; tools register only in `hermretro` |
| update | `python tools/ci/clean_install_check.py --update-from [REF]` | ~55 s | A throwaway Hermes home installs a release (default: the newest `v*` tag on `origin/main`, what users have), uses it (studio profile, a library game, a New Game chat, a running broker), then `hermes plugins update`s it to the commit: no prompt, the agent side only in `hermretro`, the library read back, the old broker (held open until then, so it cannot idle out) replaced when its code changed and kept otherwise, each ignored leftover file judged on its own. Needs the tags (`git fetch --tags`) |

While working on a branch, `python tools/retrodev check` runs only the checks whose inputs changed since their last
pass there (`ok (cached)` for the rest; inputs per check in `tools/retrodev/policy.toml`), adds acceptance and the
clean install when the branch touched what they cover, and prints each time against its budget (`[checks.budgets]` in
`tools/retrodev/policy.toml`, measured on a loaded machine: fast checks 60 s together, unit 45 s, scaffold 30 s; a
check over its budget twice in a row on the branch gets a warning, never a failure).
`python tools/retrodev check --watch` reruns the affected checks on every save; `--again` ignores the cache. A pass
on the current tree is what `python tools/retrodev ship` requires.

- Run `python tools/check.py fix` and commit before `python tools/retrodev check`: when the clean install is due it
  installs the committed tree, so uncommitted edits are not what it tests (and `ship` needs a committed tree anyway).
- A branch that changes `backend/` (or `engine/`, `player/`, the toolchain, `plugin.yaml`) makes `retrodev check`
  add the real-engine acceptance run, about a minute more. Without the toolchain (`python
  tools/ci/prepare_toolchain.py`) it is skipped, and CI runs it on Linux and macOS. `retrodev check` always uses the
  toolchain that setup put in place: it clears `HERMRETRO_DEPS_ROOT` for the run. To use a toolchain somewhere else,
  run the check directly: `HERMRETRO_DEPS_ROOT=<folder> python tools/check.py acceptance`.

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

- `python tools/check.py lint` checks; `python tools/check.py fix` gives each bare `# noqa: E402` (in `.py` and
  `.py.tmpl` files outside `engine/` and `tools/npm/`) the standard reason below (`tools/py/noqa_reasons.py`; it
  says how many), applies ruff's safe fixes, `ruff format` and the
  page lint's fixes, lists the files it changed, then lints again. `.dev/py/bin/ruff rule <CODE>` explains a rule.
- A deliberate exception is ruff's own `# noqa: <CODE>` on the line, followed by its reason after ` - ` or ` — `:
  `lock = open(path, "a+")  # noqa: SIM115 - a lock held until the process exits`; an import after the
  `sys.path` line says `# noqa: E402 - the repository root goes on sys.path first`. Prefer changing the code;
  `tests/repo/test_noqa.py` fails on any `noqa` comment without its reason (the file-wide `# ruff: noqa` and
  `# flake8: noqa` too: `# ruff: noqa: F401 - this module only re-exports`) (outside `engine/` and `tools/npm/`). (The page's escape is `// retrodev: allow <rule> — <reason>`.)
- Updating ruff: change the version in `requirements.txt`, replace the hash lines with the digests listed at
  `https://pypi.org/pypi/ruff/<version>/json`, run the setup and `python tools/check.py fix`, and commit any
  reformatting as its own commit.
- Editors: the root `pyrightconfig.json` puts `tools/` on pyright's (and Pylance's) import path, so
  `from retrodev import ...` in `tests/retrodev/` resolves as it does at run time, and leaves out the vendored and
  installed folders.

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
bare origin and a fake `gh`; under discovery the whole package runs in one thread pool, about 1.3 s; a test there
never patches a module's global, since other threads use it: `tests/retrodev/pool.py`). Each folder is a package, so discovery runs from the root:
`python -m unittest discover -s tests -t .`; one file: `python -m unittest tests/backend/broker/test_leases.py`;
one feature's tests: `python -m unittest discover -s tests/backend/<feature> -t .`. These run with your own home
folder; only `python tools/check.py unit` gives the suite an empty one (and fails on anything written there), so
run that before committing.
Shared helpers are `tests/support.py`, imported as `from tests.support import ...`; a test reaches another test's
helpers as `from tests.backend.<feature>.<module> import ...`. Never put `tests/` itself on `sys.path` (only the
repository root): `tests/backend` would then shadow the real `backend` package, and two test modules run together
(`python -B -m unittest tests.backend.setup.test_remove_tools tests.backend.library.test_games`) fail with an
ImportError that neither shows alone (`tests/repo/test_test_imports.py` refuses it).

`python tools/check.py page` runs every `tests/page/**/*test*.mjs` with `node --test`. A scenario over the built
page is a `page-<name>.test.mjs` on `harness.mjs`; check the page's text with its `shows(expected, message)` and
`hides(...)` (a string or a RegExp), which fail with about 300 characters around the closest match instead of the
whole page. `tab(name)` clicks the studio nav; `pageTab(label)` clicks a page's own tab bar (`.cs-tabs`, drawn by
`app/page-view.js` for a page with `tabs`), so a nav entry and a tab with the same label cannot be mixed up. A unit
test of one page module goes in `tests/page/<page>-<module>.test.mjs` with `node:test`, imports
the module with `import()` after `registerAliases()` from `./aliases.mjs` (the page's `#app/`… aliases, React and
the SDK stand-in; it uses `module.registerHooks`, or `register('./aliases.mjs', import.meta.url)` on a Node without
it), like `tests/page/build-player.test.mjs`. A pure helper in `page/shared/`: add `tests/page/<name>.test.mjs`
(`node:test`), call `registerAliases()` from `./aliases.mjs`, then `await import('#shared/...')`; `check.py page`
runs every `tests/page/**/*test*.mjs`, so the name must contain `test`.

## Adding a test

Put it beside the tests of the code it covers, in the same folder. When the file you would add to is already over
the size limit (`tools/layout.toml` `[exceptions]` lists those, each with its reason, and they may not grow), make
a new file beside it named for what it tests (`test_<topic>.py`, `page-<page>-<topic>.test.mjs`).

**Proving a regression test.** Run it against the old code and see it fail, then against the fix: `git stash` the
fix (or check out the old file), run `PYTHONPYCACHEPREFIX=$(mktemp -d) python -B -m unittest
tests/<area>/<feature>/test_<name>.py`, restore, run again. An edit of the same size in the same second as a cached
`.pyc` makes Python reuse the old bytecode, so the "before" run would test the fixed code; `-B` alone does not stop
that (it only stops writing `.pyc` files), the fresh, empty `PYTHONPYCACHEPREFIX` does (or delete the
`__pycache__` folders first). `python tools/check.py unit` already gives its run a fresh, empty one.

## Moving or splitting tests

A move or split must not lose a test. From the repository root, list every Python test id before and after, then
compare the two lists (their counts too: `s.countTestCases()` on the same `discover(...)`):

```sh
python -c "import unittest; ids=lambda s: [i for t in s for i in (ids(t) if isinstance(t, unittest.BaseTestSuite) else [t.id()])]; print(*sorted(ids(unittest.defaultTestLoader.discover('tests', top_level_dir='.'))), sep='\n')" > notes/ids-before.txt
# move or split, then the same command > notes/ids-after.txt
diff notes/ids-before.txt notes/ids-after.txt   # only the moved module paths may differ
```

The listing walks nested suites, so it also lists `tests/retrodev`'s tests, which run on threads inside one
`ParallelSuite` (`tests/retrodev/pool.py`). The total alone:
`python -c "import unittest; s=unittest.defaultTestLoader.discover('tests', top_level_dir='.'); print(s.countTestCases())"`.
For a page scenario, compare its check names instead ("Splitting a page scenario", below).

## Splitting a page scenario

A `page-<name>.test.mjs` near the size limit splits by section, without losing a check:

1. Move the shared starting state (the scenario values, the registered page, the first render, helpers more than one
   file uses) into `tests/page/<topic>-fixture.mjs`, exporting a function that returns it. Do not put `test` in its
   name: `check.py page` runs every `tests/page/**/*test*.mjs`, and the fixture is not a test.
2. Each new `page-<topic>-<section>.test.mjs` starts from that fixture, then does the navigation that reaches its
   section itself (each file runs in its own process, so nothing carries over from the file it came from).
3. Prove no check was lost: a passing scenario prints `{ passed, checks, names }` (JSON), then one summary line
   (`<file>: N passed, M failed`, last so the tail of a long run shows it). Before the split, save the names:
   `node tests/page/page-<name>.test.mjs | sed '$d' > notes/before.json` (`sed '$d'` drops the summary line); after
   it, run each new file the same way and compare the sorted `names` of `notes/before.json` with the sorted union of the new files' `names`: the two
   lists must be equal (a check renamed on purpose is listed in the pull request).

Docs and READMEs name test files by path (`tests/...`); `tests/repo/test_doc_pointers.py` fails on one that does not
exist (and on a doc saying `retrodev new` lacks a kind it has), so a moved or split test updates the docs that name
it.

## Rules for tests

- Never the real Hermes home. In `setUp`, `isolated_home(self)` from `tests/support.py` points both
  `HERMRETRO_HOME` (games, library, broker) and Hermes's plugin data folder (`backend.hermes.host._data_dir()`:
  history snapshots, asset versions, frames; `HERMRETRO_HOME` does not move it) at one new temp folder, undone
  by the test's cleanups; use it rather than patching `_data_dir` by hand. `throwaway_profile` moves only the
  plugin data folder, `throwaway_deps` the downloads; `HERMRETRO_*_DIR` move single folders. `check.py unit` gives
  the run an empty `HOME` with `HERMES_HOME` inside it, so a write to either lands there and fails the check; it
  then reruns each test module alone in a fresh empty home and names the ones that write there. A test that calls a
  real emitter (a tool or RPC that calls `emit(...)`, such as `chromatic_build_report` or `chromatic_present_game`)
  reaches every feature's `listeners.py`, including ones added later: give it `isolated_home(self)` even when
  today's listeners write nothing. A clean-install or Hermes-CLI test must use a folder outside
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
