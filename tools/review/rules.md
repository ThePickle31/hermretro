# Review rules

What a review of a hermretro change holds it to, by the paths each rule covers. Skip the generated files
(`desktop/plugin.js`, `player/frame-shim.js`, `page/app/rpc-names.js`, `page/pages/build/workflow.js`,
`engine/dist/server.js`), `engine/contract/manifest.json` and lockfiles: CI checks that they match their
sources.

## Findings

- **Important**: the change gives a wrong result or fails in normal use, breaks a contract that another part
  or a released version relies on, loses or damages a user's games, library or setup, or adds needless
  complexity, such as a workaround on a workaround or a copy of something that exists. Normal use is
  installing hermretro, updating it from the newest release (Hermes may run the old code until it restarts),
  making, building and playing games, setting up, repairing and removing the tools, the factory reset, and the
  development steps the skills document. Name the class of bug, and look for every other instance of it in the
  change.
- **Nit**: anything smaller worth saying. At most three; the author may decline one.
- **Pre-existing**: a real bug in code the change didn't write. It isn't the change's to fix.
- **Question**: a choice to justify, with what you'd do instead.
- **Out of scope**: what would change what was approved.

A claim about behavior cites the `path:line` that shows it, not an inference from a name. A failure that
needs a file edited by hand, a process killed, an old checkout, or two processes timed within milliseconds of
each other is a Nit or a Question, not Important. A finding that a rule here was broken quotes the rule and
applies only where its paths cover the file. Don't report:

- what CI already enforces: formatting, lint, the page and engine bundles, the engine's manifest and
  version bump, the file size limit, the committed-documents list, the install scan;
- code that looks wrong but is correct;
- nitpicks a senior engineer wouldn't raise;
- general concerns, such as more tests or another design, that no rule here names.

## Every change

- A finding is about what the changed lines introduce. Older code is Pre-existing at most; don't ask for
  cleanup outside the change.
- Linux and macOS, Apple Silicon and Intel, behave the same. A call that exists on one system only has its
  branch for the other in the same place, and locations come from `backend/system/paths.py`. Tests too: no
  file name that isn't UTF-8 (APFS refuses one), no path that exists on one system only.
- Flag a change that leaves `AGENTS.md`, a skill, a README, a reference page or this folder saying something
  untrue.
- Never accept a change that weakens a test or a check to get a pass: a deleted or loosened assertion, a
  skipped or removed test, a raised limit, a `tools/layout.toml` exception for a file that could be split, or a
  new `# noqa` or lint exception without its reason. Flag each and ask why it is needed.
- A test fails without the change it covers, and checks what its name says.
- A test that touches state uses `isolated_home(self)` from `tests/support.py`: never the real Hermes home.
  Tests never run the hardware tools.
- No real people, accounts, email addresses or home folders in fixtures.
- Every failure a check or tool reports ends with a `FIX:` line.

## `__init__.py`, `plugin.yaml`, `backend/**`

- A gateway may run the previous release's code until Hermes restarts, against the new files on disk, and
  start brokers from them. The broker handshake's `loaded_fingerprint` follows the published releases' rule
  (`paths.release_fingerprint`) and never changes; a new rule gets a new field. `LOADED_FILES` lists exactly the
  files outside `backend/` that the backend reads as it loads.
- A file a running process loads is moved, renamed or deleted only with the update check passing
  (`python tools/ci/clean_install_check.py --update-from`).
- Features reach each other only through their front doors and events, and Hermes only through
  `backend/hermes/api.py`.
- The plugin's tools, skills, hooks and prompt register only in the `hermretro` profile.
- The hardware tools stay behind the user's `hardware_enabled` setting and Hermes's approval prompt
  (`pre_tool_call` in `backend/hermes/hooks.py`).

## `backend/broker/**`

- Nothing creates a file or folder while the socket's umask is set; work started beside the broker's start
  begins after it is restored.
- A broker's handshake names the code it loaded, read once at its start, never the files on disk now.
- A broker of other code is replaced: at once when idle, after its running work otherwise. Never two brokers
  for one run folder.

## `backend/setup/**`, `backend/broker/lane.py`

- A prepared engine copy (`.cache/engine-<identity>/`) is named by the engine its process loaded, and holds
  exactly that engine: it is checked against that engine's manifest before it is published.
- No copy is removed or replaced while a worker holds its lease (`copy_lease.py`). A copy without a lease file
  was made before leases and counts as in use, except for Setup's removal with the broker stopped.
- Anything that changes the download folder holds the provision lock (`provision.lock`).
- The device CLI is downloaded only after the user accepts ModRetro's terms, and checked against its pinned
  SHA-256 before anything uses it.

## `backend/player/**`

- The loopback server answers only `127.0.0.1` or `localhost` with its token in the path, and serves only
  what its routes name: the game's web export and captures, the engine's player files and the demo cartridge.
  No path escapes its folder.

## `engine/**`

- The server is changed in its `src/` modules; `engine/dist/server.js` is rebuilt from them, never edited.
- Every engine change raises `version` in `engine/package.json` and adds its line under that version's heading
  in `engine/CHANGES.md`. CI checks the bump: check that the line describes the change.
- A changed tool contract is pinned in `engine/contract/tools.json`, with its passing `schema-reconcile.json`.
- Names that games, setup folders or browsers hold stay as they are (`engine/README.md`, "Names kept").
- Text a person or the agent reads names Hermes and hermretro's engine, never Codex. The device stays "ModRetro
  Chromatic", and the Chromatic CLI stays ModRetro's.

## `page/**`

- No supporting UI copy the owner didn't ask for: taglines, subtitles, helper or instructional text, process
  explanations, footers or repeated branding. Headings, labels, placeholders and action text stay concise.
- An RPC the page calls exists in the backend with the shape the page reads (`page/app/rpc-names.js` is
  generated from them).

## `skills/**`, `profile/**`, `.agents/**`, `AGENTS.md`, `tools/review/**`

- What these say is what the code does, by its current names and paths.
- Nothing in them trips the install scanner: instruction verbs aimed at agent configuration file names (write
  "this guide" instead).
- A command or rule they describe changes in the same pull request as its code.

## `.github/**`, `tools/ci/**`

- A pull request's checks run with its own copy of the workflows: a change here is read for what it lets a
  pull request do, as well as what it checks.
- Third-party actions are pinned by commit SHA.
