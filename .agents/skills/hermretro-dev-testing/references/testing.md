# Testing

`python tools/check.py` runs the fast checks (unit, bundle, engine, lint, page, scan) at the same time; CI runs the same ones. Every failure ends with a `FIX:` line. This page gives no times: they depend on the machine.

One test module: `python -m unittest tests.backend.<feature>.test_<name>` (unittest; pytest is not used), or `-k <pattern>` for some of its tests. One page test file: `node tests/page/<file>.test.mjs`; a scenario on `harness.mjs` (`page-*.test.mjs`) also takes an optional node_modules folder, relative or absolute (`node tests/page/page-games.test.mjs tools/npm/node_modules`; without one it looks where `tools/bundle/node-modules.mjs` says). A scenario tests the built bundle, so after editing `page/` run `node tools/bundle/bundle.mjs` first: otherwise it stops with `desktop/plugin.js is stale (...)` and `Run: node tools/bundle/bundle.mjs`.

| Check | Command | What it proves |
|---|---|---|
| unit | `python tools/check.py unit` | The Python tests, run with an empty home folder, an empty `TMPDIR` and no Hermes; fails if a test writes into the home or leaves anything in `TMPDIR`. Several processes at once (`tools/py/unit_shards.py`): the modules dealt into up to four by their times from the last run (`.dev/unit-times.json`), each with its own home and `TMPDIR` |
| bundle | `python tools/check.py bundle` | `desktop/plugin.js` and `player/frame-shim.js` match `page/` (each banner's `sources: sha256` covers whole folders: all of `page/` for the bundle, `page/frame/` and `page/shared/` for the shim, so an edit in `page/shared/` changes the shim's `sources` line even when the shim bundles none of it; commit that line with the edit) |
| engine | `python tools/check.py engine` | The engine's `dist/server.js` is byte for byte what `node tools/engine/bundle.mjs` builds from its `src/` modules (`src/entry.js` is the server's own), with the esbuild and packages pinned in `tools/engine/npm/` |
| lint | `python tools/check.py lint` | ESLint over `page/` (`tools/bundle/lint-page.mjs`): the boundaries between pages, the shell, `shared/` and the frame (`tools/bundle/lint-rules.mjs`), and a few correctness rules (undefined names, hooks order, duplicate keys…; unused names warn). At the same time ruff over the Python (`tools/py/ruff.toml`): `ruff check` (syntax errors, unused or undefined names, likely bugs, older syntax) and `ruff format --check` (one formatting for everyone). `python tools/check.py fix` applies every automatic fix and the formatting |
| page | `python tools/check.py page` | Every `tests/page/**/*test*.mjs` with `node --test --test-reporter=spec`; it reports `N files, M checks passed, K failed` (each scenario file's checks, from its last line, plus each `node:test` test; TAP output is read too, and output it cannot count says `N files passed (check count unavailable)`). The built page in jsdom (`tests/page/page-*.test.mjs`, the files run in parallel), the inline player, and the page registry, events, slots and tabs from the sources (`tests/page/registry.test.mjs`) |
| scan | `python tools/check.py scan` | Hermes's install scanner on exactly what a commit ships says `safe` |
| acceptance | `[HERMRETRO_DEPS_ROOT=<folder>] python tools/check.py acceptance` | The real engine, compiler and emulator through the broker |
| clean install | `python tools/ci/clean_install_check.py` | A throwaway Hermes home installs the commit; tools register only in `hermretro` |
| update | `python tools/ci/clean_install_check.py --update-from [REF]` | A throwaway Hermes home installs a release (default: the newest `v*` tag on `origin/main`, what users have), uses it (studio profile, a library game, a New Game chat, a running broker), then `hermes plugins update`s it to the commit: no prompt, the agent side only in `hermretro`, the library read back, the old broker (held open until then, so it cannot idle out) replaced when its code changed and kept otherwise, each ignored leftover file judged on its own. Needs the tags (`git fetch --tags`) |

Run the fast checks before opening a pull request; CI runs the slow ones its changes select
(`tools/ci/changes.py`) on the exact head. Commit before `python tools/ci/clean_install_check.py`: the install checks
install the committed tree. `python tools/check.py acceptance` (part of `full`) needs the toolchain: with no folder named, the development one
(`~/.cache/hermretro-dev/deps/toolchain`, or under `$XDG_CACHE_HOME`; `tools/py/dev_toolchain.py`) when there is one,
otherwise the one the hermretro page installed (`<hermretro home>/.cache/toolchain`); without either the check is skipped and said as not
proven here (PR CI runs it on Linux and macOS when the change touches what it covers). It installs nothing, but it is not
read-only there: its brokers and games live in a temporary folder, yet an engine worker that finds no prepared engine for
the bundled version makes one in that `.cache` from an earlier copy's device CLI
(`refresh_prepared_engine` in `backend/setup/provision.py`), then removes the other engines' copies of the same CLI build that no worker runs in, and the run writes `notes/evidence/broker-acceptance.json`.
To make the development toolchain, run `python tools/ci/prepare_toolchain.py` once: every checkout and worktree on the
machine uses it, and a restart keeps it. To use one somewhere else, name the same folder for both:
`HERMRETRO_DEPS_ROOT=<folder> python tools/ci/prepare_toolchain.py`, then
`HERMRETRO_DEPS_ROOT=<folder> python tools/check.py full` (a relative `<folder>` is resolved from where each command
runs, and handed on absolute). Outside GitHub Actions `prepare_toolchain.py` never writes the installed plugin's cache
(in GitHub Actions, with no folder named, it installs into the runner's hermretro home), and it refuses to run with
`GB_STUDIO_SETUP_ROOT` set. It
installs through a broker of its own, started in a new folder under `/tmp`; it keeps that broker's process and, at the
end, on a failure or on Ctrl-C, SIGTERM or SIGHUP, sends it SIGTERM (it closes its workers, an unfinished installer
included) and SIGKILL if it has not exited 30 s later. Only a run that succeeded and saw the broker exit removes that
folder; any other names it. So a broker already running is never reused, replaced or stopped. What it still reads from
the real Hermes home: Node discovery looks in the Hermes tools folder (`<Hermes home>/tools/node-*`, `paths.find_node`),
and its broker is handed `HERMRETRO_HOME` (`spawn_broker`), which the install only reads (where games live).

A change that has to hold on another system (this machine is Linux and the change touches macOS, or the other way):
commit, then `python tools/dev remote <ssh host> [CHECK ...]` runs `tools/check.py` (by default `unit`) on that commit
on the host, in a checkout of its own (`~/.cache/hermretro-dev/checkout` there), from the user's login shell.

One-time setup: `python tools/dev setup` (the Python lint and the npm tools for the page checks; Node 22 or newer). The checks never install anything themselves.

## Linting and formatting the Python

ruff is pinned to one version with the SHA-256 of every published file (`tools/py/requirements.txt`);
`python tools/py/setup.py` makes a venv of the Python running it in `.dev/py` (git-ignored) and installs it with
`pip --require-hashes --only-binary=:all:`, so nothing else can land and nothing is built. Run again, it returns
at once unless `requirements.txt` changed (then `lint` says so and names the command). Settings, in
`tools/py/ruff.toml`: lines up to 120 characters, Python 3.11 syntax, the rule groups E9 F B PLE UP SIM (with
the few ignores it lists and why), quotes kept as written. The engine, the vendored player, `skills/`, `tools/npm/`
and `.dev/` are not linted.

- `python tools/check.py lint` checks; `python tools/check.py fix` applies ruff's safe fixes, `ruff format` and the
  page lint's fixes, lists the files it changed, then lints again. `.dev/py/bin/ruff rule <CODE>` explains a rule.
- A deliberate exception is ruff's own `# noqa: <CODE>` on the line, followed by its reason after ` - ` or ` — `:
  `lock = open(path, "a+")  # noqa: SIM115 - a lock held until the process exits`; an import after the
  `sys.path` line says `# noqa: E402 - the repository root goes on sys.path first`. Prefer changing the code. (The page's escape is `// hermretro: allow <rule> — <reason>`.)
- Updating ruff: change the version in `requirements.txt`, replace the hash lines with the digests listed at
  `https://pypi.org/pypi/ruff/<version>/json`, run the setup and `python tools/check.py fix`, and commit any
  reformatting as its own commit.
- Editors: the root `pyrightconfig.json` puts `tools/py/` and `tools/dev/` on pyright's (and Pylance's) import path,
  as the tools put them at run time, and leaves out the vendored and installed folders.

## CI tiers

- **Every pull request** (`.github/workflows/ci.yml`): plugin and repository unit tests on Linux (Python 3.11 and
  3.14), Apple Silicon and Intel macOS. CI also runs bundle, engine (with the engine's build tools) and page, the install scan,
  `plugins validate`, the clean install and the update from the newest release with the oldest supported Hermes. Job
  `engine-version` fails a pull request that changes the engine without raising its version
  (`tools/engine/version.py`).
- **Integration** (`integration.yml`): toolchain install (cached) and acceptance on Linux and Apple Silicon
  macOS, for pull requests that touch the backend, engine or toolchain, and on every push; not for a change of only
  `plugin.yaml`'s `version:` line (a pull request, or a push of that one commit: `tools/ci/changes.py`).
- **Update scope** (`tools/ci/changes.py`, the same `changes` job): the `update-dev` job's update from the PR
  checkout's `dev` parent (`HEAD^1`) runs on pull requests that delete or move files or change the install,
  registration, broker or update paths or a `.gitignore` (`UPGRADE`). The update from the newest release (job `update`) runs
  on every run, beside the validate job. A missing decision fails the job.
- **Nightly** (`nightly.yml`, from `main`): the newest Hermes (validate, scan, clean install, update) on Linux and macOS,
  integration on Linux, Apple Silicon and Intel macOS, and the unit, bundle, engine, lint and page checks on Linux.
  The schedule tests `dev` (with `main`'s copy of this workflow, so a check added on `dev` runs there only after the
  next release); the Sunday run checks all three toolchains without the cache, while
  other nights can reuse it. To test a published release separately, dispatch `nightly.yml` on its version tag
  once that tag contains this workflow. It tests the dispatched SHA and upgrades it from the preceding published
  stable release, not from itself or from a moving `dev`. Read back the run ID and verify `headSha` against the tag.

The single required check is **All checks pass**.

## The Hermes names check

`tools/ci/hermes_api_check.py` checks that a Hermes still has every name in `backend/hermes/api.py` `USED`. CI runs
it with Hermes's own Python (`$HERMES_RUNTIME_PY`, built from a hermes-agent checkout by `tools/ci/hermes_runtime.py`
in `.github/actions/hermes`): on every pull request at `HERMES_REF` (`ci.yml`, the oldest supported Hermes) and
nightly on Hermes `main`. Locally it needs the Python of your Hermes install, which has Hermes's dependencies:

```sh
hermes --run-module site | grep site-packages   # the .../venv/lib/python3.X/site-packages line: <venv>/bin/python
<venv>/bin/python -c 'import hermes_cli.config'  # no output: this Python imports Hermes
<venv>/bin/python tools/ci/hermes_api_check.py
```

Another Python fails first with each module's import error and a `FIX:` saying to use this Python, never with a
rename `FIX:`.

CI and nightly also run `tools/ci/build_session_check.py` with that Python. The check starts
Hermes in a throwaway home, creates untitled Build sessions on both supported gateway paths, and checks that the
sessions are distinct, empty, and on the requested model/provider. One pick is created twice with identical
parameters, so a gateway that reuses an untitled session for the same route fails on its runtime or stored ID. It
needs no API key and submits no prompts.

## The clean install and update checks

`tools/ci/clean_install_check.py` installs the committed checkout into a throwaway Hermes home (the `hermretro`
profile and the default one; the install scanner must not ask) and checks the tools register only in `hermretro`.
With `--update-from [REF]` it runs the update check (`tools/ci/update_check.py`): it installs REF (default: the newest
stable `v*` tag on `origin/main`, else local `main`) from a local bare copy of the repository, uses it as the page
does (studio profile, a library game, a New Game chat, a running broker), moves the copy's `main` to HEAD and runs
`hermes plugins update hermretro`: no prompt, the folder at HEAD, no leftover files that are not bytecode, the agent
side only in `hermretro`, `hermes plugins validate` still matching `plugin.yaml`, the library read back, the old
broker replaced when its code changed, and a gateway of a published release that keeps running (Hermes not restarted)
keeping the broker the new version started. Both need `hermes` on PATH (or `--hermes-python <a Python that imports
hermes_cli>`) and no model; the update check also needs the history and tags (`git fetch --tags`) and a
REF that HEAD contains. Run it locally after moving, renaming or deleting files a running process loads:

```sh
python tools/ci/clean_install_check.py --update-from          # from the newest release
python tools/ci/clean_install_check.py --update-from v0.0.N   # from that tag
```

The throwaway folder goes in `HERMRETRO_CLEAN_INSTALL_TMP`, else `TMPDIR`, else `/tmp`, and is removed afterwards. It
must be outside the real Hermes home and short enough for the broker's socket path (27 bytes at most:
`$XDG_RUNTIME_DIR` or `/tmp`); a `TMPDIR` that is not is passed over for `/tmp`, such a `HERMRETRO_CLEAN_INSTALL_TMP`
is refused.

## The benchmark

`python tools/dev bench run` measures what making a game costs. Every prompt in `tools/dev/bench_games/` (one game
each) goes at the same time to its own one-shot chat in the `hermretro` profile (`hermes -p hermretro chat
--query-file <prompt> --oneshot -Q --reasoning high`), on the checkout that profile loads (`python tools/dev live`).
It spends real model calls, so run it on purpose and in the background: it waits for every chat, keeps each one's
output and `run.json` (process, start, exit, session, profile home, checkout and commit) in `notes/bench/<time>/`, then prints
the report (if that fails, the run stays there for `report`). `run bolt tide` runs only the games whose names contain
those words. The chats and the report use the same Hermes root: `HERMES_HOME`'s, by Hermes's own rule.

`run` runs this checkout: it refuses when the studio profile loads another (`python tools/dev live` first) or when
`HERMES_TUI_GATEWAY_URL` would send the chats to another gateway. The running gateway serves the chats with the
plugin code it loaded, not what is on disk, so `run` then asks hermretro's `status` there (with Node, `sync: false`
so it writes nothing) where its code came from (`plugin.root`) and whether it changed since (`restart_needed`, what
the page's update banner shows). When the gateway runs other code it reloads every profile that loads hermretro, as
`python tools/dev reload` does, and asks again; it starts no game when no gateway answers, the reload fails or the
code is still old (restart Hermes then).

`python tools/dev bench report` prints the newest run's report again; `--run <folder>` reports another run,
`--sessions <id> ...` any sessions. It reads a copy of the profile's `state.db` and its `-wal`, taken while neither
changed (SQLite writes a `-shm`, and makes a `-wal`, beside a WAL database it opens even read-only, so nothing in the
profile is opened), and `logs/errors.log*`, and gives
each game: wall time, estimated cost and model calls (auxiliary ones such as compaction summaries included, and
counted apart), tool calls (counted from the stored results: the session's own count leaves out what a compaction
removed), `chromatic_emulator_step` calls, builds and failed builds (`success: false` from the compiler counts),
compactions, the identical tool calls Hermes dropped (`Removed duplicate tool call`, one log line each; `unknown` when
the retained logs begin after the session started, as its first lines may have rotated out), terminal
commands and file reads into GB Studio's or the engine's source (apart), checkpoint restores, whether the chat ended
with a final answer, and the tool errors by code. Every compaction stores copies of the messages before it (the same
`message_uid`, `compacted` 1, a tool result's copy often Hermes's `[tool] ...` summary of it) and a prune leaves such a
stub where the full message was (the full one moves to a later row), so the report takes each message once, as its
full copy: a tool result's first copy that does not start with `[`, a call's longest arguments. A tool result counts
once per call (`tool_call_uid`, else `tool_call_id`), anything else once per `message_uid` (Bolt's 3,107 rows are
1,425 messages). A chat stopped before it printed its session id is found by its prompt: the one session with it that started
while that chat ran, else none; a session the stopped chat left open ends when the chat exited. Its tests use a
fixture database (`tests/dev/test_bench.py`) and, for `run`, a stand-in gateway and `hermes`
(`tests/dev/test_bench_run.py`): no test reloads or reaches the real gateway.

`python tools/dev bench compare` sets a run (`--run <folder>`, default the newest) beside an earlier one
(`--against <folder>`, default the newest finished run that started before it in the same folder, by `run.json`'s
start, and made exactly its games): for each game both made, every measure of the report in each run and its
change, both sessions and the error codes whose count changed, then the games that got clearly worse. With no such
run it says so; name one with `--against`. A named run of other games is compared too, with `workload differs`: the
games of a run share the machine and the subscription, so another set changes every chat's time and errors. It exits
1 when a game got clearly worse: when it no longer ended normally or, when both chats ended normally, when a measure
rose by at least its floor and by more than its share of the earlier value:

| Measure | Floor | Share |
|---|---|---|
| wall time | 5 minutes | 25% |
| estimated cost (in whole cents) | $2 | 25% |
| model calls | 20 | 25% |
| tool calls | 40 | 25% |
| failed builds, compactions | 2 | 50% |
| duplicate drops (when known in both) | 5 | 50% |
| source commands, source file reads, tool errors | 3 | 50% |

Step calls, builds and checkpoint restores move with how a game was made more than with how well, so they are shown,
not judged. The thresholds are `MEASURES` in `tools/dev/bench_compare.py`; the floors leave room for one chat running
differently from the next, so a game called worse is a session to read, not proof. A game either run cannot speak for
is `not judged`, and with no game worse the exit is 2: the run was made in another profile home than the one read
(`run.json`'s `home`, else its profile's name), its chat had not exited when the run was last recorded (the run is
still going, or was stopped), or its session is not in the profile's `state.db`. It reads what `report` reads, the
same way. Its tests use fixture runs and a fixture database (`tests/dev/test_bench_compare.py`).

Run Bolt and Starling on each release candidate: `python tools/dev bench run bolt starling` (in the background) on
the candidate, then `python tools/dev bench compare --against <folder>`, naming the last release's Bolt and Starling
run (without `--against`, the newest earlier run of exactly those two), and read the session of any game it calls
clearly worse, and of any it could not judge, before releasing.

## Where tests live

Tests mirror the code: `tests/backend/<feature>/test_*.py` for each backend feature, `tests/page/` for the page
(`page-*.test.mjs`, the shared `harness.mjs` and the browser preview), `tests/repo/` for repository-wide checks
(names in lock step, the version, the folder map and file sizes, only listed documents, no personal paths, the
bundle, the install scan) and
`tests/acceptance/` for the real-engine run and `tests/dev/` for the development loop. Each folder is a package, so discovery runs from the root:
`python -m unittest discover -s tests -t .`; one file: `python -m unittest tests/backend/broker/test_leases.py`;
one feature's tests: `python -m unittest discover -s tests/backend/<feature> -t .`. These run with your own home
folder; only `python tools/check.py unit` gives the suite an empty one (and fails on anything written there), so
run that before committing.

The real-engine run starts in `tests/acceptance/broker_acceptance.py`. Under `tests/acceptance/`,
`projects.py` covers builds and emulation, `replay.py` replaying a recorded attempt onto a rebuild, `art.py` art
import, sprite palettes and previews, `debugging.py` source-mode live state, `audio.py` music and sound import,
`music_compose` and a song the sound hardware plays, `ownership.py` leases and the Desktop view, `recovery.py`
worker and broker restarts and watched project folders that are replaced, and `update.py` the broker's replacement
after an update (and that a broker from before it gets nothing dispatched); these stages use the same two
games. `authoring.py` covers the engine's authoring rules
(project-unique symbols, scene transactions, script event ids and typed arguments) on a third game of its own, and
`events.py` the event catalog (against the toolchain's GB Studio), `event_describe`, the authoring skill's cookbook
recipes and `rom_build`'s authoring warnings on a fourth, with `unknown_events.py` (events GB Studio does not have,
refused on write and failing a build). `golden_path.py` makes one game of its own from a blank project to a presented
build with its report, in the order of the studio's workflow, as a studio chat with no model (`studio.py`: the
plugin registered into a plugin ctx as Hermes does, in an isolated home with Hermes's scratch folder in the run; each
call through the `pre_tool_call` directives, the registered schema, Hermes's result contract and the
`post_tool_call` outcome):
create, art, audio, scenes from an operations file, build, a recorded run played as one `inputs` list, the test plan's
checks bound to it and replayed with `chromatic_playtest`, a rebuild that names their stale results and the run is
replayed onto, the sound hardware, the game card, the pipeline gate holding `chromatic_present_game` and
`chromatic_build_report` until the checks pass on the rebuild (and `unfinished` passing it), and
`chromatic_build_report` naming the replay as its `finishRun`. A tool or gate that joins the pipeline joins it there, as a named step of its
own (one `@step` function and its `GP` check) or in the step that uses it. A call that never reaches its tool (a
broker denial, an adapter error, a block, an approval request, arguments the schema refuses) fails its step's check
with the tool, code and error, and stops the steps after it.

Shared helpers are `tests/support.py`, imported as `from tests.support import ...`; a test reaches another test's
helpers as `from tests.backend.<feature>.<module> import ...`. Never put `tests/` itself on `sys.path` (only the
repository root): `tests/backend` would then shadow the real `backend` package, and two test modules run together
(`python -B -m unittest tests.backend.setup.test_remove_tools tests.backend.library.test_games`) fail with an
ImportError that neither shows alone (`tests/repo/test_test_imports.py` refuses it).
A test that needs a library game calls `make_library_game(home, name="Game") -> (game id, project root)` from
`tests/support.py` (`home` is what `isolated_home(self)` returns): a real project, registered as the gateway does,
ready to present. `web=False`, `card=False` or `built=False` (`make_project`'s switches, all on by default) leave out
the playable copy, the game card or the native ROM; the id comes back either way. `add_images(root, count,
folder="sprites")` puts real PNGs where the `assets` RPC lists them (`tests/backend/assets/test_asset_list_limit.py`).
A test that needs a running broker patches in a `FakeBrokerClient(answer)` from there (it records `asked` and `calls`).

`python tools/check.py page` runs every `tests/page/**/*test*.mjs` with `node --test`. A scenario over the built
page is a `page-<name>.test.mjs` on `harness.mjs`, with exactly one `runScenario(...)` call: it ends the process when
its body finishes (the page's polling would keep it alive), so a second call in the same file never reports, and
nothing says so; put another scenario in its own file. Run one with `node tests/page/<file>`; a harness scenario also accepts a node_modules folder as its last argument. Check the page's text with its
`shows(expected, message)` and
`hides(...)` (a string or a RegExp), which fail with about 300 characters around the closest match instead of the
whole page. `tab(name)` clicks the studio nav; `pageTab(label)` clicks a page's own tab bar (`.cs-tabs`, drawn by
`app/page-view.js` for a page with `tabs`), so a nav entry and a tab with the same label cannot be mixed up.
`currentTab()` names the studio nav's open page; `currentPageTab()` the selected tab of the mounted page's own tab
bar (null when it has none; `.agents/skills/hermretro-dev-page/references/adding.md`, "Testing a tab", is a runnable example). A Build
page scenario starts with `buildScenario({ selected })` (setup finished, the Build page open, `selected` as
`storage.buildSelected`), then sets its own `scenario.games`. A unit
test of one page module goes in `tests/page/<page>-<module>.test.mjs` with `node:test`, imports
the module with `import()` after `registerAliases()` from `./aliases.mjs` (the page's `#app/`… aliases, React and
the SDK stand-in; it uses `module.registerHooks`, or `register('./aliases.mjs', import.meta.url)` on a Node without
it), like `tests/page/build-player.test.mjs`.

**Test a plain page helper** (a page test of a pure function, e.g. in `page/shared/`): add
`tests/page/<name>.test.mjs` (`node:test`), call `registerAliases()` from `./aliases.mjs`, then
`await import('#shared/...')`, as `tests/page/time.test.mjs` does; `check.py page` runs every
`tests/page/**/*test*.mjs`, so the name must contain `test`.
The SDK stand-in's react-query (`tests/page/sdk-stub.mjs`, listed in its header): `useQuery` (answers
`scenario[queryKey[1]]`, or, when that is a function, what it returns for the whole `queryKey`: a per-game query
such as `[ID, 'captures', gameId]` then answers each game differently) and `useQueryClient()` with `invalidateQueries` (a no-op), `setQueryData` and `getQueryData`
(one cache, `scenario.queryData`); add what else a page starts to use.

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

The total alone:
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
exist, so a moved or split test updates the docs that name
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
- Clean up every temp file and folder: `tempfile.TemporaryDirectory()` with its cleanup, or
  `self.addCleanup(shutil.rmtree, folder, ignore_errors=True)` right after `tempfile.mkdtemp()`. `check.py unit` gives
  the run an empty `TMPDIR`, fails on anything left in it, and names the leaking module.
- Never the hardware tools (`flash`, `play`, `setup`, capture); `device` with `command: "status"` is the only
  hardware call allowed, and only in acceptance.
- Unix sockets: keep `TMPDIR` short (`$XDG_RUNTIME_DIR` on Linux, `/tmp` on macOS); macOS caps socket paths at
  104 bytes. `check.py` does this for you.
- macOS temp folders live under `/var`, a link to `/private/var`: `.resolve()` a temp base before comparing paths.
- Names that must change together are checked by `tests/repo/test_lockstep.py`; the version by `tests/repo/test_version.py`.
  After adding or renaming a tool or an RPC, run just that check with `python -m unittest tests.repo.test_lockstep`
  (its opening comment lists every place to edit). For an RPC, `python tools/bundle/rpc_names.py` rewrites only
  the generated `page/app/rpc-names.js` from the backend's `@rpc` declarations (and only when it changes; `--check`
  writes nothing and exits 1 when it is stale); `node tools/bundle/bundle.mjs` runs it too, before rebuilding the
  page. Commit the generated file with the backend change.
- `tests/repo/test_tool_shapes.py` checks that fields of one name and meaning in the pinned engine tools have one
  shape (types, enums, number, length and item ranges, patterns, object and required keys) across them. After pinning
  a changed tool contract, a mismatch it names is fixed in the engine or its path is listed in
  `tests/repo/tool_shape_differences.py` with why it differs (`OWN`, `GROUPS`, `NARROWER` or `WIDER`); an entry no
  longer needed, or a schema form it does not compare, fails it.

## Looking at the page

`node tests/page/preview/build.mjs <out> [<Hermes checkout>/apps/desktop]` builds a browser preview with a stand-in
SDK, drawn with Hermes Desktop's own stylesheet. It needs that Desktop folder with its npm dependencies installed and
its `dist/assets` built (default: `~/.hermes/hermes-agent/apps/desktop`); open `<out>/index.html?s=<scenario>&mode=dark&p=<page>`. Scenario links are
listed on the page. Screenshot with Playwright and a short `TMPDIR`.
