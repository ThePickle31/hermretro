# retrodev reference

Every detail behind `tools/retrodev/README.md` (the entry: what retrodev is, the quick path, the flow): each command,
`new` kind by kind, what `land` does, releases, state and settings.

## Taking over a branch, and status

**Taking over a teammate's branch** (theirs, pushed, with or without a plan): `python tools/retrodev takeover
<branch>` (from any checkout) fetches, makes the worktree under the configured worktree root
(`<worktree_root>/<topic>`) on a local branch tracking `origin/<branch>`, sets it up as `start` does and prints the
next steps: when it lacks commits of `origin/dev`, first "read `git diff HEAD...origin/dev -- <files>` and `git log
--oneline HEAD..origin/dev -- <files>` before sync merges it" for the files both changed (`status` says the same
while it has no plan), then `sync`, so the plan is written knowing what dev rewrote; `plan new <topic>` describing what
the branch does and what is left, then `plan approve <topic> --words "<the owner's words>"` while it has no approved
plan (a branch named `<kind>/<topic>` works under it; another name: `plan link <topic>` in its checkout), then `check` (while the
branch's own `tools/retrodev` is older than `origin/dev`'s, each of these is the main checkout's, `python
<main>/tools/retrodev ...`, run in the worktree, until `sync` brings the branch's copy up to date); then `ship` as for
your own; its plan and pull request body stay in the main checkout's `notes/` (`notes/plans/<topic>.md`,
`notes/pr/<topic>.md`), shared by every worktree, never in the worktree. When the branch is checked out already (for instance in the only checkout, a clone made for it), skip the
worktree: run `sync`, `plan new`, `plan approve`, `check` and `ship` there. `sync`, `check` and `ship` work in any
checkout of the branch; only `start` and `land` need the main checkout on `dev`.

At any time `status` names the one next step (once `notes/pr/<topic>.md` exists, the `ship --title ... --body <path>`
to run, with the title and body given before (also to a dry run), else the plan's title and `notes/pr/<topic>.md`,
saying `(fill in every section of the body first)` only while that body fails ship's body gate and `(ship --dry-run
passed at <time>)` when the last dry run passed every gate (the base gate last) on this tree and this very body; and
`behind origin/dev: N commits (python tools/retrodev sync)` with `sync` as the next step whenever HEAD lacks commits
of `origin/dev`, counted from the last fetch, offline, in a worktree, on a branch in the main checkout and in the main
checkout's list alike), `doctor` checks the machine, `sync` brings in `dev`, `gc` tidies up. While building, `new
<kind> ...` adds a feature, RPC, tool, event, listener, page, tab, slot or contribution in the repository's shape, and
`stats` shows how the flow is going. `engine update <version>` walks an engine update, only with the owner's words.
Beyond one change: `try <pr>` runs any pull request's full checks in a throwaway checkout, `mac` runs the checks on a
MacBook, `preview` builds the page's browser preview, and `release ...` makes a release when the owner asks (below).

## Commands

### `plan new <topic>`

Writes the plan template (a `Title:` line, one plain sentence of at most 100 characters without a trailing period that
check, status and ship then suggest as `--title`, and say why when they skip it (`the plan's title is N characters;
the limit is 100`); Goal, What changes (in the present tense, 'X does Y': start copies it into the body), Where files
go (its comment points to `new ... --dry-run`, which lists a piece's files), How it is tested, How the owner and users
use it, Not in scope) unless the file exists; edit it in place

### `plan show [topic]`

The plan and its approval; with no topic, the current branch's plan (else every plan)

### `plan approve <topic> --words "..."`

Refuses (exit 1, `FIX: fill in <main checkout>/notes/plans/<topic>.md first`) a plan with a section that still holds only the
template's comments, as ship refuses such a body, and a `Title:` line that ship's title gate refuses, with the same
FIX (`shorten it to 100 characters or fewer (yours is 105)`, `drop the trailing period`). Records the owner's go with
the time, their exact words and the plan's hash (status notes a later change), and rewrites the plan's `Status:` line
(the template's `draft for the owner's approval`) to `approved <YYYY-MM-DD>: "<words>"` before taking that hash. Next step: `start <kind>/<topic>`,
naming the kinds (feat, fix, docs, chore: refactors that change no behaviour), or, when branches already work under
the plan (recorded ones, and any local `<kind>/<topic>` branch made by hand), `cd <worktree> && python tools/retrodev
check` for each (`sync (HEAD lacks N commit(s) of origin/dev), then check` while that worktree is behind, status's
rule) and `start <kind>/<topic> --plan <plan>` for another. Run in a work branch that works under the plan (any name,
a taken-over `test/x` too), it also writes that branch's pull request body as `start` does

### `plan link <topic>`

From a branch made by hand: record that it works under that plan

### `start <kind>/<topic> [--plan <topic>] [--no-plan] [--no-setup]`

kind: feat (a new ability), fix (a bug), docs (documentation only), chore (refactors that change no behaviour).
`--plan` names the plan when one plan covers several branches (default: the branch's topic). Needs an approved plan
(docs and chore may say `--no-plan`), the main checkout on `dev` and clean. Fetches, makes the worktree at
`<worktree_root>/<topic>` on a new branch from `origin/dev` (no upstream: it can never push to `dev`), runs `npm ci
--prefix tools/npm` and `python tools/py/setup.py` there, prints the path. It writes the pull request
body `notes/pr/<topic>.md` in the main checkout (the file `ship` reads; never over an existing one) from
`.github/pull_request_template.md` (with `--no-plan` too: the template with the `Made by` line and the `<!-- no plan:
say why -->` Why, its absolute path printed in the next step, so a docs change needs one ship dry run): Why from the plan's Goal, What changed from its "What changes", Not done from its
"Not in scope" (each only when the plan says something there; under a plan shared by several branches, one whose
`## Branches` (or `## PRs`) list names more than one or that a branch started earlier works under, landed or not, Why comes only
from a section whose heading names this branch or its topic, Not done stays the template's, and the plan's `Title:`
is not offered as the `--title`), and the `Made by` line (while it names only the generic
agent, the next step says to name yours there or set `RETRODEV_AGENT=<agent, model>`); ship's body gate still refuses
it until How verified and Risk and rollback say something too

### `takeover <branch> [--no-setup]`

A teammate's pushed branch: fetches, makes `<worktree_root>/<topic>` on a local branch tracking `origin/<branch>`
(refused when that local branch exists or the folder is taken), runs `start`'s setup, records the branch, notes a kind
the repository does not name (`test/x`: it keeps its name, since ship, land and CI accept any work branch, and
retrodev's record follows that name), and prints the next steps: `sync` while HEAD lacks commits of `origin/dev`
(first, so the plan is written knowing what dev rewrote), `plan new` and `plan approve` while it has no approved plan
(`plan approve` then writes the pull request body; otherwise takeover writes `notes/pr/<topic>.md` from the template
itself, as `start --no-plan` does, and the next steps name its absolute path to fill in), then `check`; while the branch's own copy of retrodev
is older than `origin/dev`'s, every one of these runs the main checkout's retrodev in the worktree, as every later
next step does until `sync` (`plan approve`, `status`, `sync`'s own, `land`'s conflict fix). Needs nothing of the main
checkout but its git folder

### `check [names...] [--again] [--full] [--watch]`

When the tree passes and the branch has no pull request yet while its body (`notes/pr/<topic>.md`, or the recorded
one) still fails ship's body gate, its last line is `next: fill in <the sections still empty> in <path>, then python
tools/retrodev ship --title '<title>'` (while the body does not exist yet: `next: fill in the pull request body
(missing: <path>; ...)`). Runs `tools/check.py` for the checks whose inputs changed since their last pass on the
branch (`ok (cached)` otherwise; a check's inputs, in `policy.toml` `[checks.inputs]`, include the tools it runs and
their pins, `tools/check.py` and `policy.toml`); `--watch` runs again on every file change and on a commit or a
clean/dirty change, so committing lets the waiting install checks run, and reads `policy.toml` again before each run
(a trigger added while watching runs its check at once); `--watch --again` ignores earlier passes on its first run,
later runs rerun only what changed; adds `acceptance` and the clean install (and the update check when files moved or
were deleted) when the branch changed what they cover (not for a file `[checks.trigger_ignore]` lists: a backend
`README.md` adds no acceptance run); prints times against budgets (`policy.toml` `[checks.budgets]`,
from measured cold runs on a loaded machine: unit 45 s, scaffold 58 s, the fast checks together 60 s). A check over
its budget twice in a row on the branch (each check's last passing time is recorded in the branch record's
`durations`: a failed run measures nothing) gets a warning that it was slower than usual (machines and load differ),
never a failure; one slow run (a cold cache, a busy machine) warns nothing. The clean install and update check install
the committed HEAD, so they run only on a committed, clean tree: when one is due and the tree has uncommitted changes,
`check` refuses before running anything (`FIX: commit first: the clean install installs the committed tree`);
`--watch` instead runs the rest and lets them wait for the commit. When scaffold is due, lint runs first, by itself;
on a tree that fails lint (in the same run, or lint's recorded failure on the same inputs) scaffold does not run (it
would fail after a minute and more: new's code is linted) and is reported as `scaffold: skipped: the tree fails lint
(fix lint first)`, not as scaffold's rerun FIX (likewise `scaffold: skipped: the tree fails page (fix page first)`
when the tree fails page: check.py scaffold looks at page once, before any scaffold test, reusing page's row of the
same run or its recorded pass); once lint passes, scaffold runs beside the other checks. A
generated bundle (`player/frame-shim.js`, `desktop/plugin.js`) whose banner's `body: sha256` is unchanged (only its
`sources:` line moved) adds no check. A pass of everything the branch needs records the tree's digest (contents and
file modes) and which checks those were; ship accepts it only while they cover what the policy requires now; a failed
rerun takes it back

### `ship [--title "..."] [--body <file>] [--new-body] [--dry-run]`

The title defaults to the branch's recorded one (its pull request's, else the last ship's, also a dry run's or one a
gate stopped); with none recorded its title gate fails with `FIX: python tools/retrodev ship --title '<the plan's
title>'` (when the plan's `Title:` line fails the title gate, the message says why), and every other gate still runs,
so one run reports every refusal (a body skeleton written just now is the body gate's refusal too). The body defaults
to the recorded one while that file exists, else `notes/pr/<topic>.md`. Ship records the title and the resolved body
path before any gate can stop it, so `status` names that exact body. Gates: a work branch, the owner approved its plan
(the record's plan, else the branch's topic; docs and chore may go without one), a one-line title of at most 100
characters without a trailing period (its FIX names the problem: `shorten it to 100 characters or fewer (yours is
105)`, `drop the trailing period`), a branch that changes at least one file (`nothing to ship: the branch changes no
file` when its tree is `origin/dev`'s), every template section filled in and a line saying an agent made it,
everything committed, `check` passed on this exact tree, commits beyond `dev`, the remote branch not moved (if it
moved: `git fetch origin && git merge origin/<branch>`, then check and ship again). Then a plain `git push -u` and `gh
pr create --draft --base dev` with area labels, or `gh pr edit` of the open one. An open pull request into another
branch (one opened by hand into `main`) is refused with `FIX: gh pr edit <n> --base dev`; ship never retargets it. The
body: `--body`, else `notes/pr/<topic>.md` in the main checkout (git-ignored, outside the worktree, so `gc` is never
blocked by it), which `start` (or `plan approve` inside the linked branch) writes early under a plan. Only when that
file is missing (or with `--new-body`; an existing one is kept) ship writes it from
`.github/pull_request_template.md`, with the plan's Goal as the Why and the line `Made by an agent (<name>) for
@<account>.` in place of the template's comment (`RETRODEV_AGENT` names the agent, default Hermes; the account is the
GitHub remote's; with no GitHub remote it is `Made by an agent (Hermes) for the owner.`: add the model, and name your
agent if it is not Hermes; the body gate takes the line as written),
then exits 1 with `FIX: fill in <path>, then ship --title '<the title given>' --body <path>`. With `--no-plan` or an
empty Goal the Why holds a visible `<!-- no plan: say why -->` instead. `--dry-run` writes the same skeleton (a
git-ignored note, not a push), reports the body gate as `NO body: fill in <path>` with that FIX, still a `--dry-run`
(a dry run's FIX never turns it into a push), and exits 1; `status` keeps `--dry-run` in the next ship it names while
the last ship was a dry run and no pull request exists. With no GitHub remote (a sandbox, another host) the dry run
prints `note: no GitHub remote; the open pull request lookup was skipped` instead of gh's error. Every printed command is shell-quoted (`output.cmd`): a title with an apostrophe is in double quotes
(`--title "Fix the player's frame"`) unless it holds a `"`, `$`, backtick, backslash or `!`, which keep shlex's
quoting; either pastes as it is. When the body passes its gate, ship (and `check`'s last
line) warns, never fails, about each backtick-quoted identifier of its What changed (`games.rom_path`: an underscore,
a dot or a capital inside) whose name appears nowhere in the branch's diff against `dev` (either side) or its tracked
files: a name renamed while building (`games.built_rom`); and about each backtick-quoted repository path there (a slash in it, under
one of the repository's top folders: `tools/retrodev/sync.py`, `backend/library/`, `desktop/plugin.js`) that the
branch's changes do not touch (a renamed file counts at both its old and its new path). A bare file name (`sync.py`,
`games.json`), a path under `engine/` and a path a citation clause holds (`checked against`, `see`, `comes from` ...)
never warn. The next step it prints is `report`, or, when the owner
already approved this pull request (`approve`), `cd <main checkout> && python tools/retrodev land <n>`

### `report`

The factual half of the step-5 report (`--json` too), with the owner's approval and the review rounds; a cached check
says when its pass ran and how long it took

### `approve <pr> --words "..."`

Records the owner's approval of that pull request (time, exact words, its number and head then) in its branch record
(found by the pull request's head branch) and its review record; marks a draft ready (`gh pr ready`). The approval
belongs to that number: review-fix pushes to it keep it; a replacement pull request from the same branch needs its own
(`ship` moves the old one to the branch record's `approvals` history). Empty words: exit 3

### `land <pr> [--no-review [--reason TEXT]] [--ci-timeout S] [--dry-run]`

Takes an approved pull request through the review loop, CI and the merge (below). Resumable: run it again after each
stop, also after the merge (it finishes the steps after it, never merging again). `--no-review` skips the reviews;
`--reason TEXT` says why (recorded, default `land --no-review`; `stats` prints it as `reviews skipped: TEXT`, never
naming who decided). `--dry-run` prints the gates and the next step and changes nothing

### `answer <pr> <round> <index> "<text>"` / `answer <pr> <round> --all "<text>"`

The answer to one finding (or every finding of a round): the fix's commit, or why it is wrong with proof. The next
round's reviewer reads them. Its next step fits the pull request: merged, `summary <n>`; the fixes shipped (the
worktree's head is the pull request's head, past the reviewed one), `land <n>`; else commit, check and ship them, then
`land <n>`

### `summary <pr>`

The step-8 note's facts: files added, changed, moved, removed by area (from the squash commit; before the merge, the
head against the base branch), the findings fixed with their answers, the rounds, CI, and whether the owner restarts
the gateway (`backend/`, `__init__.py`, `plugin.yaml`, `skills/`, `profile/`) or reloads the app
(`desktop/plugin.js`). Read-only

### `status`

On a branch: plan, approval, checks on this tree, PR, pushed head, CI, and the next step. In the main checkout: every
record and worktree. A first line names `RETRODEV_STATE_DIR` when it is set (as `doctor` does). A feat or fix branch
without an approved plan says so on its first line, with the exact commands: `plan: <topic> (none written): a feat
branch ships only under an approved plan: python tools/retrodev plan new <topic>, fill it in, show the owner, then
python tools/retrodev plan approve <topic> --words "..."` (`(NOT approved)` once written), and next `plan new
<topic>`; a branch behind `origin/dev` gets `sync` as its next step before any plan step (`sync (...), then <the plan
step>`); a docs or chore branch without one shows `plan: none needed (docs/chore)`; with no GitHub remote, the CI
lookup prints the same note as ship (also in `report`)

### `sync`

`git fetch`, then merges `origin/dev` (never a rebase). Conflicts only in generated files: takes dev's side, rebuilds
them, finishes the merge. Any other conflict: stops with the source files and leaves the merge open (for a hunk whose
`dev` side is empty, the FIX adds `<file>:<lines>: dev moved this block to <file> (or deleted it); delete the HEAD side
of this hunk, git add, sync again, then add your lines in <file> in a new commit`, the file found by `git grep -l -F`
on `origin/dev` for the hunk's longest distinctive line (one it holds once, of 8 characters or more), with \`git log -p
origin/dev -S<that line>\` to show the move; the whole tree, since blocks move into tests too; when no other file has
any of its lines: `dev deleted this block`, the same steps); resolve only the conflict in the merge (never the generated ones), `git add` those files and run `sync` again:
it rebuilds the generated files and makes the merge commit (no `git commit` by hand). If `dev` rewrote the code your
side changed, the FIX says to take dev's lines in the merge and redo your change on top in its own commit after sync,
and where: for a table row of a markdown file, the subsection headed with the row's first cell (else the most alike
heading and its lines, never a table row); when two places match about as well, `git diff HEAD...origin/dev -- <file>`.
When the resolved conflicts hold lines neither side had (only the files that were in conflict count; binary files are
read as bytes and never counted; compared word by word with line breaks and spaces normalised, so a paragraph rewrapped
around an edit from each side adds nothing), it warns `new work belongs in its own commit after sync (a resolution over N lines
needs a full review round at land)` (N: `[land] max_sync_resolution_lines`). A clean merge rebuilds the generated
files too and commits them if they changed. Each generator prints as `rebuilt: <command>`, as a person would type it
(`python ...`)

### `gc [--dry-run]`

Removes worktrees whose pushed branch is merged into `origin/dev`, whose pull request merged, or which the remote
deleted, only when clean and holding no ignored file beyond the rebuildable caches in `policy.toml` `[gc] caches`
(`node_modules/`, `.dev/`, `__pycache__/`, `*.pyc`, ...): a worktree with ignored `notes/`, `games/`, scratch or logs
is kept with its branch, naming those paths and a `FIX:` (move them out, e.g. into the main checkout's `notes/`).
Deletes those branches and their records. A worktree folder deleted by hand loses only git's note of it: its branch
and record stay unless the branch passes the same checks, and every later gc judges that recorded branch again
(removed once merged). Removes folders in the main checkout whose whole subtree is bytecode caches and empty folders
(a hidden or skipped folder, a symlink or any other file keeps it). A dry run fetches nothing and changes nothing.
When it removes the worktree it was started in, it says `your shell may still be in <folder>: cd <main checkout>`

### `doctor [--all]`

git, gh and its account, git identity, Python, Node, the npm tools and ruff, Hermes and a hermes-agent source for the
scan, the main checkout clean, the worktree root, a short temp folder (a warning when it has under 1 GB free); each
problem with its fix. The main checkout off `dev` is a warning (`!!`, never a problem): only `start` and `land` need
it there. `--all` adds the reviewer (`review_profile` set, and a live probe of its provider) and the MacBook's
reachability (optional, never a problem)

### `config list` / `get <key>` / `set <key> <value>`

Personal settings; `set <key> ""` goes back to the default. `list` shows where an empty `worktree_root` resolves to

### `try <pr> [--keep] [--no-setup]`

Fetches the pull request's head (`<remote> refs/pull/<n>/head`, forks too) into a detached throwaway worktree in a
short temp folder outside the repository, sets it up and runs `check --full` there (a `skipped` row, such as
acceptance without the toolchain, makes it unverified: exit 1, never a pass); removes it afterwards (the folder, then
`git worktree prune`), also on a failure, unless `--keep` (its path and the commands that remove it are printed).
Nothing in any agent's worktree changes

### `mac [--host H] [-- <check.py args>]`

Optional: the checks on a MacBook over ssh. The host is `--host` or the personal `mac_host` (no default: unset prints
"no mac configured; CI's macOS runners cover it", exit 0). It must answer `ssh -o ConnectTimeout=3 -o BatchMode=yes
<host> true` (else exit 2: unreachable, CI covers macOS). The commit must be on the remote; on the mac, in `mac_repo`
(default `~/Projects/hermretro`, `~` expanded there), it fetches, adds a fresh detached worktree of the commit in a
`/tmp/rd-mac.*` folder (the clone's `.dev` and `tools/npm/node_modules` linked in), runs `python3 tools/check.py
--strict [args]` there, streaming its output, and removes the worktree. A requested check that cannot run there
(acceptance without the toolchain) fails under `--strict`, and any `skipped` row in the output is reported as
unverified (exit 1), never as passed. The clone's own checkout is never switched or reset, so its local changes
neither reach the result nor get lost. It never pushes from the mac

### `preview [--serve] [--out DIR] [--desktop DIR]`

Builds the page's browser preview (`node tests/page/preview/build.mjs`, docs/dev/TESTING.md) into `<state>/preview`
and prints its `index.html`. Needs a built Hermes Desktop source: `--desktop`, else `$HERMES_SOURCE/apps/desktop`
(default `~/.hermes/hermes-agent`), symlinks resolved either way. `--serve` serves it on 127.0.0.1 on a free port (the
standard library's http.server, loopback only, the Desktop's stylesheets included) until Ctrl+C

### `stats`

Read-only: pull requests landed through retrodev (review records with a merge) against all merged into `dev` (git
subjects ending `(#N)`); per landed pull request its review rounds, findings per round and answers; the mean time from
the first `ship` (recorded from now on) and from the owner's approval to the merge; check times from the branch
records; rows and open rows of the main checkout's `notes/friction.md`

### `engine update <version> --owner-words "..." [--done N ...] [--dry-run]`

`docs/dev/ENGINE-UPDATE.md` as a checklist. Without the owner's words exit 3 (a dry run too): anything under `engine/`
needs the owner. Then only on `chore/engine-<version>`; records the words in `<state>/engine/<version>.json`; judges
each step from the tree (the vendored `package.json`, the local patch, `engine/pins/<version>/`, `ENGINE_VERSION`),
runs only the read-only helpers (`manifest.py verify`, the lock-step test) and prints the others with the version
filled in. A step the tree cannot show (comparing the skills, the full checks) is manual: once done, `--done <its
number>` records it (the time, and that the agent did it) in the same record; `--done` on a step the tree judges is
refused. Exit 2 while a step is left, an unrecorded manual one included (the next one named, with its `--done`), 0
only when every step is done. It never changes `engine/` itself. `--dry-run` records and runs nothing

### `release prepare [--rc] [--version X.Y.Z] --owner-words "..."`

Only when the owner asks for a release: without their words (naming a release) exit 3. Below

### `release publish <version> [--dry-run]`

The gates, the update check, then main, the tag and the draft release. Below

### `release verify <version> [--publish]`

Reads the draft and proves the update path; `--publish` publishes it. Below

## new

### The rules every kind follows

Each `new` writes from the templates in `templates/<kind>/` (`{key}` filled in; `{{` and `}}` are literal braces),
prints every file it created (`create`) or changed (`change`), formats the Python it touched with the pinned ruff
(before the `--dry-run` diff too, so the diff is what the write produces),
rebuilds the generated files when the change feeds them (`policy.toml` `[generated] regenerate`), runs the checks
those files are inputs of (lint, bundle, unit, page; the page kinds, `page`, `tab`, `slot` and `contribution`, run
only lint, bundle and page, leaving unit to `check`; the install scan waits for `check`; when lint fails, new lints its
own files again, alone, with lint's own commands and settings (`python tools/check.py lint-files FILE...`); when that
passes, every tool those files need being there (a missing ruff fails it: `python tools/py/setup.py`), the failure is
reported as `pre-existing on this tree (not from new)` and the scaffold stands, exit 0, when every other check it ran
passed (one skipped for a missing tool keeps the exit 1: it proves nothing); a
unit or page failure is always new's, since new's code may break a test it did not write) and
prints the next steps
(for a change the clean install covers, such as `plugin.yaml` or `backend/features.py`: commit, then `check`, then
`ship`, since that install takes only the committed tree). It refuses (`FIX:`) a name that exists or breaks the naming
rules (features, RPCs, tools and events: lowercase and underscores; pages and tabs: lowercase and dashes; slots:
camelCase), never overwrites a file, and writes only on a work branch (never `dev` or `main`; `--dry-run` writes
nothing, the branch record included, so it runs on `dev` too and a plan can list the files). It refuses a tool whose
schema constant or handler name the module binds already (a second binding would replace the first), a page or tab
label with a quote, backslash or line terminator (it goes into a JavaScript string), and an RPC, tool or event in a
stdlib-only feature (`policy.toml` `[new] stdlib_only`: broker, system; their gateway-side pieces go in setup, library
or another feature). `--dry-run` lists the files, prints the unified diff of every file it would create or change
(from the plan's in-memory edits; `diff` in `--json`) and writes nothing; `--no-check` skips the checks; `--no-build`
skips the rebuild (when several `new` run in a row, let the last one rebuild). It never writes a broken or partial
change: every edit is made in memory first, each Python file of it must parse, and only then is anything written. It
extends a declaration only in a shape it knows (`TOOLS` a plain tuple or list; `EVENTS` a dict literal, on one line or
several, its entries kept) and otherwise refuses with a `FIX:` and changes no file (the hermes feature's `TOOLS` is a
function: its tools come from the engine). Step words may hold quotes; each is written as a proper Python and
JavaScript string. The generated code passes the real checks as written: `python tools/check.py scaffold`
(`tests/retrodev/test_scaffold_tree.py` with `RD_SCAFFOLD_FULL=1`; a few seconds, so not in the fast unit run) runs
every kind on a copy of the repository, then lint, the bundle, the structure tests and the page tests there. It is
part of `check.py full` and `check --full`, `check` adds it when the branch changed the scaffolds or the files whose
structure they parse (`policy.toml` `[checks.triggers]`; not ARCHITECTURE.md or CONTRACT.md, whose rows `new` adds,
nor a change to `page/pages/index.js` or `step-words.js` made only of the lines `new page` and `new tool` write there,
`[checks.new_lines]`),
and CI's page job runs it with `RD_SCAFFOLD_FULL=nested`: after the base tree's unit suite (a failure there is
`scaffold: skipped: the tree fails unit (fix unit first)` with that run's last lines and `FIX: python tools/check.py unit`, checked once for the whole check, as page is; in GitHub Actions only when the same invocation runs unit, since CI's unit job covers it), it runs each kind once more on a real feature or page (an
rpc and a tool in library, an event and a listener in history, `tab --from-page` and a tab on setup, `tab --from-page`
on prompts, a slot on home, a contribution from home to a declared slot), then the full unit and page suites, so a test that
pins the real tree's current content fails in CI, not in a contributor's branch that used `new`. `check` runs it in
that nested mode itself (its `adding scaffold:` line ends `run nested (RD_SCAFFOLD_FULL=nested), as CI's page job
runs those tests in its grown copy`; about 110 s, budget `scaffold_nested`) when the branch changed a test the grown
copy runs that may read the surrounding tree: `tests/repo/`, `tests/support.py` or the page test harness
(`policy.toml` `[checks.nested_triggers]`; never the generated `tests/repo/registration.json` that `new tool` and
`new rpc` rewrite); a fast-mode pass never stands for a nested one.

### `new feature <name> [--purpose "..."]`

`backend/<name>/` (front door `__init__.py` with its docstring, `__all__ = []` and `EVENTS = {}`; `README.md`),
`tests/backend/<name>/` (a front-door test), and the registry lines: `backend/features.py`, the area in
`tools/layout.toml`, the Map row and the "The agent half" row in `docs/dev/ARCHITECTURE.md` (after the last row of the
table that starts `| Feature | Declares |`, whatever other tables that section holds). An empty feature registers
nothing, so the registration snapshot stays

### `new rpc <feature> <name> [--module <module>] [--game]` or `new rpc <feature>.<name>`

`--game`: an RPC about one library game, `{ game }` -> `{ ok, game }` (the rule: a game's library id is `game`, as
`builds`, `build_restore`, `build`, `assets` and the event payloads take it; the older `player`, `captures`,
`game_thumb` and `capture_image` keep `id`), its next steps running the query in the component that has the game with
`queryKey: [ID, '<name>', game.id]` (no `viaProfile`, with either call, as the `captures` and `player` queries) and `{ game: game.id }`,
answering `NO_GAME` when `host._game_root(game)` finds none (as `builds` does), its test registering a game with
`tests.support.make_library_game(home, name)`. `--module <module>` (e.g. `<name>_rpcs`) puts the handler factory in
`backend/<feature>/<module>.py` (the README's RPCs line names it: ``RPCs (`rpcs.py`, `<module>.py`)``) and keeps in
`rpcs.py` a short `@rpc("<name>")` function calling it (`from . import <module> as _<module>_mod`: a private alias,
which no `rpc_<x>` or public name can equal; `new rpc` refuses, before writing, a wrapper, factory or alias name that
`rpcs.py` binds already, so a new RPC never rebinds an earlier one's): `tools/bundle/rpc_names.py` and the lock-step
test read `@rpc` in `rpcs.py` only, so the declaration stays there; without it, an `rpcs.py` within 50 lines of the
one size rule's warning (`tools/layout.toml` `[size]` `warn`) gets a note suggesting `--module`. RPC names are global
and flat: the page calls `plugin.hermretro.<name>` whichever feature declares it, so `library.recent` means feature
`library`, RPC `recent`. An `@rpc("<name>")` stub in `backend/<feature>/rpcs.py` (made with its imports when missing;
the handler its factory returns is always named `_answer`, so an RPC named `host`, `logger` or a builtin never shadows
what the handler uses), `tests/backend/<feature>/test_rpc_<name>.py` (its `setUp` calls `isolated_home(self)` from
`tests/support.py`: `HERMRETRO_HOME` and the data folder in a temp folder, so it never reads the real library), a `###
\`<name>\`` section in `docs/dev/CONTRACT.md`, the README line; then rebuilds `page/app/rpc-names.js` (`RPC_<NAME>`;
the page imports it from `#app/rpc.js`, which re-exports it) and `tests/repo/registration.json`. Its next steps give
one rule for the call, chosen by what the handler reads, not by the feature: `callStudioOnly` (the hermretro profile
only) if the handler reads or binds a profile's Build conversations or its plugin data folder (`host._data_dir()`:
snapshots, asset versions), otherwise `callStudio` (the library's way; history and assets RPCs usually need
`callStudioOnly`, so the suggested code uses it there and the step says to check what yours reads), `callBackend` resolving to `{ data }`; the page's `useQuery`
(`queryKey: [ID, '<name>', shell.viaProfile]` in the page's own Page component with `callStudio`, without viaProfile
with `callStudioOnly`; for `--game`, in the component that has the game, as above), whose second word the page tests
answer (`scenario.<name>`); that a page reading a new shell field adds it to its fixture in `tests/page/shells.mjs`
(`homeShell()`); the page's README and a bullet in its `### <Page>` subsection under `## Pages` of
`docs/dev/STUDIO-PAGES.md` (the table row stays short); and the row to add to the RPC table under
CONTRACT.md's "Studio pages (desktop) and their RPCs", naming the RPCs it lists. It also names the RPC in the
feature's "The agent half" Declares cell in `docs/dev/ARCHITECTURE.md` (`nothing yet` becomes `RPC \`<name>\``, else
it joins the RPCs, as `new tool` does with tools and `new event` with the row's events), and when the module docstring
of `rpcs.py` lists every RPC the file declares (`status, doctor, ... and remove_tools`), adds the new one last there
(the paragraph rewrapped at 120 columns when it grows past them), said on a `done:` line

### `new tool <feature> <name> [--step RUNNING DONE]`

A schema, handler and `Tool(..., step_words=(RUNNING, DONE))` in `backend/<feature>/tools.py` (`TOOLS` made when
missing), its unit test, the `provides_tools` line in `plugin.yaml` (after the plugin-owned tools), the page's
`step-words.js` entry, the counts, the tool's name at the end of the sentence in `CONTRACT.md` that lists the
plugin-owned tools (with what it does in brackets to fill in; the lock-step test counts only that sentence's names),
the README line; then the snapshot. Tool names take the `chromatic_` prefix (given or not). The plugin-owned count is
a word up to twenty, digits past it. `--module <name>` writes the tool into `backend/<feature>/<name>.py` with its own
`TOOLS` and adds `from . import <name>` and `*<name>.TOOLS` to `tools.py`'s `TOOLS` (made when missing); a name
`tools.py` already binds to anything but `from . import <name>` is refused before anything is written; without it,
when `tools.py` is over 400 lines or only takes in sibling modules (no `Tool` of its own), the tool goes into
`<tool>_tools.py` that way, and a note says so. Splitting `tools.py` by hand works the same way: each module has its
own `TOOLS`, `tools.py` aggregates them (`from . import <module>`, `*<module>.TOOLS`), and tests patch names on the new
module (`mock.patch("backend.<feature>.<module>.<name>")`), not on `tools.py`. In a sibling module the README's Tools line names it too (`Tools
(\`tools.py\`, \`<module>.py\`)`). `--project` is for a tool that acts on the game's project (most library tools): a
`project` schema property, a handler that calls `tool_args.tool_project` (the `project` given, else this chat's) and
answers failures with `tool_error`, and a test with `isolated_home(self)` that passes a temp project and a missing
one. It is on by default in a feature with `tool_args.py` (library); in another feature `--project` imports them from
`backend/hermes/tool_args.py` (`from ..hermes.tool_args import tool_error, tool_project`), refused while that file is
missing; next steps add `host.library_game_for([root])` for a tool about the selected game; `--no-project` for a
library tool that touches no project. After `root, error = tool_project(...)` the handler returns `error or
tool_error(..., "NO_PROJECT")` when either is missing, so pyright sees `root` as a `str`. The next steps list the
error codes the tool modules answer with (read from `backend/*/tools.py`, `*_tools.py` and `tool_args.py`). A library
`--project` tool's next steps point at `backend/library/README.md` "Project files" and `games.project_title(root)`

### `new event <feature> <name> [--payload "..."] [--when "..."]`

`--payload` works either way: comma-separated (`--payload 'game=<id>, root=<project>'`) or repeated (`--payload
'game=<id>' --payload 'root=<project>'`), the parts joined in order. The `"<feature>.<name>": "<when>; key=<...>,
..."` entry in the front door's `EVENTS` (each `--payload` key written `key=<...>` as the existing entries are, a part
that says what it holds kept as given; `--when` names tools and RPCs in backticks) (no comment inside it: the hint is
in the printed next steps; a description too long for one line is wrapped as the front doors wrap theirs, a
parenthesised string per line within ruff's 120 characters, and the comma after the entry before it goes after that
entry's closing parenthesis, found from the parse), its CONTRACT events row after the owner feature's last one
(Payload: `` `key` (what it holds) `` per `--payload` part, as the other rows write it, `` `root` (<...>) `` for a key
given without; Emitted when: `--when`), a function in `backend/<feature>/emits.py` that emits it (the
boundary test refuses an event nothing emits), `def <name>(*, key1, key2)` with a keyword-only parameter per
`--payload` key (`**payload` when it names none, or a key is not a Python name; a key that is a parameter of
`backend/system/events.py`'s `emit` itself, `name`, is refused before anything is written), with its test emitting
those keys with sample values; the `EVENTS` entry drops `--when`'s backticks (the CONTRACT row keeps them), the
CONTRACT events row and the README line. A key given without what it holds (`--payload root`) is written `root=<...>`:
the next steps name those placeholders to replace in the `EVENTS` entry (`new listener` copies it into its docstring),
and say to assert the event in the test of the code that emits it (`grep -rln <caller> tests/backend/<feature>`), and
that the broker process never emits (`backend/system/events.py`): call it from Hermes-side code (an RPC, tool or hook)
that sees it happen. The `--when` text is both the CONTRACT row's "Emitted when" cell and the start of the `EVENTS`
description, so phrase it as the existing entries do, a sentence about what happened: `--when 'Setup finished
installing the toolchain'` (without `--when` both say `say when`/`say when it is emitted`, placeholders to replace).
Another feature listens with `new listener`. Changing its payload or name later: "Changing an event's payload or
name" below (new event's and new listener's next steps point there)

### `new listener <feature> <event>`

An `@on("<event>")` function `on_<owner>_<what>(*, <the payload keys>, **_payload)` in
`backend/<feature>/listeners.py` (made when missing; `backend/system/events.py` imports every feature's `listeners.py`
on the first emit, so nothing registers it), `tests/backend/<feature>/test_listener_on_<owner>_<what>.py`
(`HERMRETRO_HOME` in a temp folder), the README's "Listens to", which names the file and gives each event an entry of
its own (`Listens to: none.` becomes ``Listens to (`listeners.py`): `<event>` — say what this listener does.``; after
an event already listed, ``; `<event>` — say what this listener does``: the placeholder gate refuses it until
written), the CONTRACT events row's "Heard by" cell and the feature's row in ARCHITECTURE.md "The agent half". The
test calls it with the event's payload keys (its CONTRACT row, else its `EVENTS` entry); the next steps say to test
what it does, name `host.library_game_for([path])` and `tests.support.make_library_game` for a payload with a path or
root but no game, and list the emitting feature's tests that mock `backend.hermes.host` helpers and emit this event
(they name it, or call its emitter in `emits.py` or a function that calls that or `emit("<event>")`, found by parsing
the feature's code): the listener now runs against those mocks. The next steps say to log with `host.logger` (`from
..hermes import host`); the docstring says that a listener runs synchronously in the emitting process and thread on the Hermes side (the gateway, the plugin host or a turn
process), never in the broker, so module-level state is per process: state other processes must read goes in a file
under `backend.system.paths.hermretro_home()`, written atomically. The next steps add: export a reader other code
needs in the feature's `__init__.py` `__all__` and name it on the README Front door line. Its next steps name the
placeholders to replace (`<feature> (say what it does)` in the Heard by cell, `say what this listener does` in the
docstring, and in the README entry when new wrote one) and the event entry's `key=<...>` placeholders it copied into
the docstring, and list the test classes that emit the event (they name it or call its emitter) and now run the
listener: those whose `setUp` lacks `isolated_home(self)`, and those `already isolated`. The docstring's first
paragraph copies the `EVENTS` description wrapped within 120 characters, then `say what this listener does.` on a
line of its own (its replacement has the whole line); the test's call gives each key a sample of
the type its `EVENTS` entry hints (`<..., int>` 1, `str` `"probe"`, `pathlib.Path` `Path("/games/probe")`, `bool`
`True`). The last next step points to "Changing an event's payload or name". Refuses an event no front door's `EVENTS` declares, one the feature hears
already, and the stdlib-only features

### Changing an event's payload or name

An event `<feature>.<name>` is spelled out in six places; change them together, in one commit:

1. its function in `backend/<feature>/emits.py` (`def <name>(*, key1, key2)`: add, rename or drop the keyword);
2. every caller of that function, which passes the keys (`grep -rn '<name>(' backend/<feature>`);
3. its `EVENTS` entry in `backend/<feature>/__init__.py` (`key=<what it holds, type>` per key);
4. its row in `docs/dev/CONTRACT.md` "Events between backend features" (Payload);
5. `tests/backend/<feature>/test_event_<name>.py`, which emits the keys and asserts what a listener hears;
6. the emitter's own tests that assert the payload (`grep -rln '<feature>.<name>' tests/backend/<feature>`).

Then each listener (the CONTRACT row's "Heard by"; `grep -rn '@on("<feature>.<name>")' backend`): its parameters,
its docstring's copy of the `EVENTS` entry and its test's call (`tests/backend/<listener>/test_listener_on_*.py`).

Renaming `<feature>.<old>` to `<feature>.<new>` touches the same places (the `EVENTS` key, the CONTRACT row's Event
cell, the `emit("<feature>.<new>", ...)` string in `emits.py`), plus:

- the `emits.py` function's name (`def <old>(` becomes `def <new>(`) and every caller (`grep -rn '<old>(' backend`);
- `git mv tests/backend/<feature>/test_event_<old>.py tests/backend/<feature>/test_event_<new>.py`, then its
  docstring (`Run alone: ... test_event_<new>`), its class (`Event<Old>` becomes `Event<New>`) and the event name in it;
- the feature's row in `docs/dev/ARCHITECTURE.md` "The agent half" and the `Events emitted` line (and the Tests line,
  which names `test_event_<old>.py`) of `backend/<feature>/README.md`;
- each listener: `@on("<feature>.<new>")`, its function `on_<feature>_<old>` and test
  `tests/backend/<listener>/test_listener_on_<feature>_<old>.py` (`git mv`, then the names inside), the CONTRACT
  row's "Heard by" stays, and the listening feature's README `Listens to` line and ARCHITECTURE row name it;
- `grep -rn '<old>' tools tests/retrodev` for fixtures and examples that use it as an existing event (the retrodev
  tests listen to real events such as `library.build_reported`).

`tests/repo/test_boundaries.py` fails on an event emitted or listened to under a name no `EVENTS` declares, so a
missed place shows up in `python tools/check.py unit`.

### `new page <id> [--label "..."]`

`page/pages/<id>/` (`index.js` with the `<ID>_PAGE` descriptor, `<id>-page.js`, `README.md`), its import and place
(last) in `PAGES` of `page/pages/index.js`, and the nav list in `tests/page/registry.test.mjs`; then the bundle. Its
next steps name the places that list the pages (README.md "What works today", the first sentence under CONTRACT.md's
"Studio pages (desktop) and their RPCs", STUDIO-PAGES.md's Pages table: a row of cells of at most 160 characters plus
a new `### <Page>` subsection under `## Pages`, with "not designed yet" in the design columns)

### `new tab <page> <id> [--label "..."] [--from-page]`

`page/pages/<page>/<id>/index.js` (`<PAGE>_<ID>_TAB`: `{ id, label, Page }`; the page is one bundle, so every exported
name is unique, and new refuses a taken one), imported and listed in the page's `tabs`, appended to the README's
**Tabs:** line (every tab, not only the first) and, when the README's "Adding a tab here" names taken ids (setup's
"`install` and `onboarding` are taken"), to that list (a `done:` line); then the bundle. On a page without tabs that still
renders its own Page, the first next step is ``this page has no tabs yet: run new tab <page> main --from-page first so
its current content becomes a tab`` with how to undo the tab just made (it is not refused: a Page meant to stay above
every tab is a real choice, and `--dry-run` shows the step before anything is written). An id whose folder exists is refused, naming what
that folder is (the first line of its `index.js` comment) and the same command with another id and `--label <the
label>`. The tab template opens with `Heading` (`page/shared/ui/text.js`). With tabs, the page's own Page still
renders, between the tab bar and the chosen tab, with a `tab` prop (`app/page-view.js`); the next steps say so while
the descriptor has a Page, say that a single tab shows a tab bar of one while `tabs` holds exactly one, say that the
shell's player and BelowPlayer stay under every tab when the descriptor has `pad` or `BelowPlayer`
(`page/app/studio-page.js` draws them after the page's body), and name each `tests/page/*.mjs` that renders
`pageOf('<page>').Page` (new never edits `tests/page/`), and on a page without tabs that keeps its Page the automatic
page check is skipped with a note (its tests were written for the page alone). `--from-page` on a page without tabs
makes the page's own Page that first tab instead: the tab's `index.js` imports it as `#pages/<page>/<file>.js` (a tab
never imports `../`), and the descriptor loses its `Page` (a Page defined in `index.js` itself, as `function
<Page>(...)` or `const <Page> = ...`, moves into `<page>-page.js` first, with the whole comments directly above it (no
blank line between): made, or appended to with the imports it needs (a matching one-line import is rebuilt from its
parsed names), exported, and `index.js` drops the imports only it used; every edit comes from acorn's parse of both
files (`scaffold_move.mjs`, the pinned npm tools: without them the move is refused with `npm ci --prefix tools/npm
--ignore-scripts`); refused when it uses a helper defined beside it in `index.js`, or a name `index.js` imports from
`<page>-page.js` under another name than that file's own declaration; refused, before anything is written, for a
default or namespace import or a Page `index.js` neither imports nor defines). An aliased import keeps its exported
name (`import { SetupPage as SetupPanel }` stays that in the tab). Its automatic page check runs:
`tests/page/registry.test.mjs` takes a page whose tabs each have a Page. Every tab's next steps say to describe it in the page's README **Shows:** line and as a bullet
where `docs/dev/STUDIO-PAGES.md` describes the page: its `### <Page>` subsection under `## Pages`, else a `## <Page>...`
section of its own (Build's `## Build: one game, one conversation`, and there its `### Page` subsection), else a new
`### <Page>` subsection to add (the table row stays short); and to add the tab's checks to one of the page's own
`tests/page/page-<page>*.test.mjs` that covers it, or a new `tests/page/page-<page>-<tab>.test.mjs` (picked up
automatically; named on the README's **Tests:** line). A `**Tabs:** none (...)` line becomes the first tab, its
parenthetical dropped; a Page moved out of `index.js` whose page
`tests/page/registry.test.mjs` still names in `PAGE_IN_INDEX` gets a step to remove it there (new never edits
`tests/page/`)

### `new slot <page> <name> [--doc "..."]`

`'<page>.<name>'` (camelCase) in the page's `slots`, the declared-slots list in `tests/page/registry.test.mjs`, the
README's **Slots:** line (``declares `<page>.<name>`: <doc, its first letter lowercased>. Contributes none.``, as
`page/pages/emulator/README.md` writes it: the doc's `{ ... }` props objects and identifiers such as `hardwareOn` or
`go(pageId)` in backticks, the paragraph wrapped at 120 columns); then
the bundle. Rendering `jsx(Slot, ...)` where it goes stays the author's; the next steps add the `HOSTS` recipe in
`tests/page/slots.test.mjs`, and `new contribution` fills it from another page

### `new contribution <page> <slot> <Component>`

A component of `<page>` in another page's declared slot (an undeclared slot is refused, naming the declared ones;
with `--dry-run` only, a slot of an existing host page that is not declared yet is previewed with the note `slot not
declared yet: run new slot <page> <name> first`, so a plan that adds a slot and fills it can list both): the
stub `page/pages/<page>/<component-file>.js` (`InstallButton` -> `install-button.js`, returning `null`), its import
and `contributes: { '<slot>': [Component] }` in `page/pages/<page>/index.js` (after the slot's list when the page
fills it already), the page README's **Slots:** line (`contributes none` becomes ``contributes `<Component>` to
`<slot>` ``), the host page README's **Slots:** line (``<Page> fills it with `<Component>`.`` after what it says of
the slot; a next step when that line does not declare it in those words), and the `filled` assertion's `expected` in `tests/page/registry.test.mjs` with its import (in `PAGES`
order; imported as `<Component>From<Page>` when the test names `<Component>` already, e.g. `Text`, and refused when it
names that too; when its shape is not the usual one, a note says to add it and the page check is skipped). A slot key
already in `contributes`, in any quote style, is extended only when its value is a one-line array, else refused before
anything is written (as `new slot` refuses a slot declared in either quotes); then the bundle and
lint, bundle and page. The edits it made that read like steps (the `filled` assertion, the host's **Slots:** line)
print as `done: ...` lines, apart from the `next:` ones. Its next steps name what it leaves to the author: the
component itself, docs/dev/STUDIO-PAGES.md's "Events and slots today" and the `HOSTS` recipe in
`tests/page/slots.test.mjs`

Every command takes `--json` (one JSON object: `command`, `ok`, `code`, `status`, the command's data, and `error` with
`message` and `fix` on a failure).

## What land does

Gates first, all reported at once: the owner's approval of this pull request (its number) is recorded (else 3); the
pull request is open, into `dev` (a draft is marked ready); the worktree's head is the pull request's head and pushed;
the tree is clean and `check` passed on it. A pull request GitHub reports as conflicting (`gh pr view --json
mergeable` says `CONFLICTING`, checked right after the gates and again before waiting for CI; `UNKNOWN` goes on) stops
with exit 1 (`action: sync`) and the fix `cd <worktree> && python tools/retrodev sync`, resolve, `check`, `ship` (with
the branch's recorded title and body), then `cd <main checkout> && python tools/retrodev land <n>`; `gh pr merge`
refused for merge conflicts says the same. Then, from the records (`records.next_action`):

- **a round is due: none at this head yet, fewer than 3, earlier findings all answered**: probes the reviewer once;
  unavailable, or no `review_profile`: reviews skipped with the reason recorded, on to CI. Else runs the round (minutes;
  CI runs meanwhile)
- **the round has findings**: prints each (severity file:line problem, fix) and the steps: fix, `check`, commit,
  `ship`, `answer` each, `land` again. Exit 1 (`action: fix`)
- **findings not answered yet**: names them. Exit 1
- **every finding answered, nothing new pushed**: the next round judges the answers
- **round 3 had findings, all answered**: no 4th round: on to CI with this head, recorded as the one accepted
  (`accepted` in the review record)
- **3 rounds ran and the head moved past round 3's clean head or the accepted head (a CI fix, say)**: exit 3 (`action:
  reviews-exhausted`): nothing after it was reviewed; the owner decides: `land <n> --no-review`, or not
- **the head only merged `dev` after the clean or accepted head (`sync`)**: the review carries over: no new round when
  every commit since it (beyond `dev`'s) is a merge or touches only generated files, and the head differs from git's own
  merge of the reviewed head and `dev` (`git merge-tree`, generated files aside) by at most `policy.toml` `[land]
  max_sync_resolution_lines` (20) lines of conflict resolution, counting only code: a line whose change is only in a
  comment counts 0 (Python: compared as its tokens and nesting depth, so a `#` comment or spacing between tokens counts
  0 while string text and indentation count; every other file, JavaScript included: exact lines, since only Python's own
  tokenizer tells a comment from code reliably), and a conflicted file is compared with git's merge of its two sides'
  code, so a resolution that keeps both sides' code with either side's comments (24 bare noqa comments given their
  reason) counts 0 (`code_lines.py`); recorded (`carried` in the review record), and `summary` shows `merge resolution,
  not reviewed: N lines`. A larger resolution, a commit of its own or anything it cannot judge: a round is due as for
  any new head (after round 3, the owner decides)
- **the round was void (the audit failed) twice, or gave no valid JSON twice**: exit 3 with the audit's findings: the
  owner decides
- **clean on this head (a clean round counts only for the head it reviewed), or reviews skipped**: waits for CI on the
  exact head, polling every 20 s up to `--ci-timeout` (default 1500 s)
- **CI failing**: names the jobs and links, `gh run view <run> --log-failed`. Exit 1 (`action: fix CI`)
- **CI still running at the timeout**: exit 2: run `land` again (nothing is reviewed twice)
- **CI green**: the pull request rechecked (open, into `dev`, at the head), then `gh pr merge <n> --squash
  --delete-branch --match-head-commit <sha> --subject "<title> (#<n>)"`, `git pull --ff-only` in the main checkout when
  it is on `dev` and clean, `gc` of that branch only, then `summary <n>`. Exit 0. Run land from the main checkout (`cd
  <main checkout> && python tools/retrodev land <n>`): the merge removes the worktree, and a shell left in it fails
  every later command (land and gc say `your shell may still be in <folder>: cd <main checkout>` when they remove the
  folder they were started in). Each step after the merge is recorded (`landing` in the review record): when one fails
  (the pull cannot fast-forward), fix it and run `land <n>` again; it does the steps left, never merging again

CI is green when every job passes or is skipped, except those in `policy.toml` `[land] ignore_jobs`, and the `[land]
required_jobs` ("All checks pass") are there. Every poll and the moment before the merge recheck the pull request: a
push (its head moved), a close, a merge by someone else or a retarget away from `dev` (the head unchanged, so
`--match-head-commit` would not catch it) stops land with the reason, and nothing is merged. GitHub auto-merge stays
off: land merges only itself, only through this path.

### The reviewer stays read-only

Hermes runs an agent's tools inside its gateway, so no sandbox around the command holds. Instead (`review/`): the
reviewer gets only the `file` toolset (no terminal, so no git, gh or network), reads a throwaway `git archive` export
of the head with no `.git` plus a `review/` folder of patches and the brief (`review/brief.md`, filled in per round),
in `<state>/reviews/<pr>/round<N>/`, outside every worktree's files. After the round its session's tool calls are read
from the reviewer profile's `state.db`: anything but `read_file`/`search_files`, or a path outside the round folder,
voids it. Snapshots before and after must match: the pull request's own worktree (status, the changed files' bytes,
HEAD), its branch on `origin`, and the export's digest. Other worktrees are not watched (agents at work there change
them). A void round is discarded and run once more from a fresh export; a second void stops for the owner. Every
round, its raw output and audit are in `<state>/reviews/<pr>.json`, readable in the main checkout's
`notes/reviews/pr<N>.md`.

## Releases

Only when the owner says "make a release". The rules are in the agent guide's "Releases"; these commands carry them out. The version lives only in `plugin.yaml`
and moves one patch at a time unless the owner names another (`--version`).

1. `release prepare --owner-words "<the owner's exact words>"`: refuses (exit 3) without words that ask for a release.
   Fetches; the version is the patch after `plugin.yaml` on `dev` (or `dev`'s own version when it is not tagged yet:
   an earlier candidate bumped it, and no pull request is needed). Records the words in
   `<state>/releases/<version>.json` (asked again, it forgets the commit an earlier publish chose), then `start
   chore/release-X.Y.Z --no-plan` (a worktree left from an earlier run is reused only when it is on that branch,
   clean, and differs from `origin/dev` by the `version:` line alone; otherwise it refuses with the FIX), changes only
   the `version:` line, stages only `plugin.yaml`, commits `Release X.Y.Z`, runs `check` and `ship`s the pull request
   "Release X.Y.Z". Then it lands like any pull request: `approve <n> --words "..."`, `land <n>`. When no pull request
   is needed, the record says so explicitly (`no_pr`). When `check` or `ship` fails, the branch is recorded but not
   the pull request: the FIX prints `release prepare --version X.Y.Z --owner-words '...'`, which resumes (the same
   worktree, `check`, `ship`, and the pull request recorded); run after the pull request exists, even merged, it finds
   it with `gh pr list --head chore/release-X.Y.Z --state all` and records it.
2. `release publish <version> --dry-run`, then without `--dry-run`. Gates, all reported: the owner's words are
   recorded for this version; the version pull request is merged (its merge commit is the release commit; only when
   prepare recorded that none was needed, `origin/dev`'s head; a record with the branch but no pull request (an
   interrupted prepare) has its pull request looked up by that branch and kept, or is refused with the prepare command
   that finishes it, never `origin/dev`'s head when publish first runs, kept in the release record so a retry after
   `dev` moves releases the same commit, its gates checked again); that commit is on `origin/dev` and its
   `plugin.yaml` says the version; "All checks pass" is green on that exact commit (`gh api
   repos/{owner}/{repo}/commits/<sha>/check-runs`; still running: exit 2); `origin/main` is an ancestor of it (main
   only fast-forwards; otherwise exit 3); the tag is free or already at that commit. Then
   `tools/ci/clean_install_check.py --update-from` runs on that commit in a throwaway checkout (its pass is kept for
   the commit). Then, each step skipped when done already, so a stopped publish resumes: `git push origin <sha>` onto
   `main` (a plain fast-forward push, with `HERMES_RELEASE=1` in that one push's environment for the local guard
   hooks), `git tag -a v<version> <sha>`, `git push origin refs/tags/v<version>`, `gh release create v<version>
   --verify-tag --generate-notes --notes-start-tag v<previous stable> --draft`. It prints the draft's address and the
   next step. Before the steps it records that commit as approved (all gates passed) in the release record.
   `--dry-run` fetches nothing, runs nothing and changes nothing: it prints the gates and every command.
3. Read the draft (add a short summary on top, and whether the real-machine checklist ran), then `release verify
   <version>`: the release exists and its notes are not empty; the tag points at `main`'s head and `plugin.yaml` there
   says the version; `clean_install_check.py --update-from v<previous stable>` passes on it. `release verify <version>
   --publish` does the same, and also needs the owner's words recorded for the version, the tag at exactly the commit
   `release publish` approved, and "All checks pass" green on it (so a draft made by hand or a tag moved since is
   refused, exit 3); when all is well, it says that a published release is immutable and runs `gh release edit
   v<version> --draft=false`.

A release candidate: `release prepare --rc ...` names `X.Y.Z-rc.M` (the next M); `release publish X.Y.Z-rc.M` tags the
`dev` commit and adds `--prerelease`; `main` does not move; `release verify` checks it is a prerelease on `dev`.

## State and settings

Records live in `<git common dir>/retrodev/` (the main checkout's `.git/retrodev/`, shared by every worktree, never
committed): `branches/<branch>.json` (plan, checks with their input digests, the passing tree, the pull request and
pushed head, the owner's approval, land's last step), `plans/<topic>.json` (the plan's approval and the branches that started under it, kept after land or gc forgets
their records), `reviews/<pr>.json`
and `reviews/<pr>/round<N>/` (every review round; `shipped` is the first ship's time, for `stats`),
`engine/<version>.json` (the owner's words for an engine update), `releases/<version>.json` (the owner's words, the
pull request, the update check's pass and the steps done), `preview/` (the page preview), `config.toml` (personal
settings). `RETRODEV_STATE_DIR` moves the folder (for a sandbox or a trial that must leave the checkout alone);
`status` and `doctor` print a warning naming it, so an override leaked into a shared shell is noticed. Set it per
command (`RETRODEV_STATE_DIR=<folder> python tools/retrodev ...`), never exported in a shell others use.

The rules everyone shares are in `policy.toml` beside this file: check inputs and triggers, budgets, generated files
and how to rebuild them, the template's sections, labels by area, what needs a restart. Personal settings override its
`[config]` defaults:

| Key | Default | What it is |
|---|---|---|
| `base` | `dev` | The branch pull requests go into and worktrees start from |
| `remote` | `origin` | The remote to fetch from and push to |
| `worktree_root` | empty: `<main checkout's parent>/<its name>-wt` | Where `start` puts worktrees (relative: beside the main checkout) |
| `github_account` | empty | When set, `doctor` checks gh is logged in as this account |
| `review_profile` | empty | The Hermes profile the reviewer runs from (personal; empty: land skips the reviews) |
| `review_provider`, `review_model`, `review_reasoning` | `openai-codex`, `gpt-6.1-sol`, `high` | The reviewer's provider, model and reasoning |
| `mac_host` | empty | The ssh host of a MacBook for `mac` and `doctor --all` (personal; empty: CI's macOS runners cover it) |
| `mac_repo` | `~/Projects/hermretro` | The clone on the mac (`~` is expanded there) |
