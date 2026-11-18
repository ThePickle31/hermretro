# retrodev

`python tools/retrodev <command>` is hermretro's development CLI. It runs the working agreement between the owner
and the agents that build the plugin, and refuses to skip a step: no work before the owner approves the plan, no
push of a tree that did not pass the checks, no pull request with an empty template section. Standard-library
Python 3.11+, development only (it never runs inside Hermes). Tests: `tests/retrodev/`.

## The flow, from plan to merge

| Step | Who | Command |
|---|---|---|
| 1 discuss | owner and agent | |
| 2 plan | agent | `plan new <topic>` writes `notes/plans/<topic>.md` (git-ignored) from the template; `plan show` |
| 3 go | owner says start | `plan approve <topic> --words "<the owner's exact words>"` (the agent runs it) |
| 4 build | agent | `start feat/<topic>`, edit, `check` (or `check --watch`), commit, `ship --title ... --body <file>` |
| 5 report | agent | `report` gives the facts (PR, commits, files by area, checks, CI, what to restart); the agent adds the prose |
| 6 approve | owner says approve, merge or go ahead | `approve <pr> --words "<the owner's exact words>"` (the agent runs it), once per pull request |
| 7 land | agent | `land <pr>` in the background: up to 3 read-only review rounds, CI on the exact head, the squash merge; between rounds the agent fixes, checks, ships and `answer`s each finding, then runs `land` again |
| 8 summary | agent | `summary <pr>` gives Added / Changed / Fixed / Removed, the rounds, CI and what the owner restarts; the agent adds the prose |

At any time `status` names the one next step, `doctor` checks the machine, `sync` brings in `dev`, `gc` tidies up.
Beyond one change: `try <pr>` runs any pull request's full checks in a throwaway checkout, `mac` runs the checks on
a MacBook, `preview` builds the page's browser preview, and `release ...` makes a release when the owner asks
(below).

## Commands

| Command | What it does |
|---|---|
| `plan new <topic>` | Writes the plan template (Goal, What changes, Where files go, How it is tested, How the owner and users use it, Not in scope) unless the file exists |
| `plan show [topic]` | The plan and its approval; with no topic, the current branch's plan (else every plan) |
| `plan approve <topic> --words "..."` | Records the owner's go with the time, their exact words and the plan's hash (status notes a later change) |
| `plan link <topic>` | From a branch made by hand: record that it works under that plan |
| `start <kind>/<topic> [--plan <topic>] [--no-plan] [--no-setup]` | kind: feat, fix, docs, chore. `--plan` names the plan when one plan covers several branches (default: the branch's topic). Needs an approved plan (docs and chore may say `--no-plan`), the main checkout on `dev` and clean. Fetches, makes the worktree at `<worktree_root>/<topic>` on a new branch from `origin/dev` (no upstream: it can never push to `dev`), runs `npm ci --prefix tools/npm` and `python tools/py/setup.py` there, prints the path |
| `check [names...] [--again] [--full] [--watch]` | Runs `tools/check.py` for the checks whose inputs changed since their last pass on the branch (`ok (cached)` otherwise; a check's inputs, in `policy.toml` `[checks.inputs]`, include the tools it runs and their pins, `tools/check.py` and `policy.toml`); `--watch` runs again on every file change and on a commit or a clean/dirty change, so committing lets the waiting install checks run, and reads `policy.toml` again before each run (a trigger added while watching runs its check at once); `--watch --again` ignores earlier passes on its first run, later runs rerun only what changed; adds `acceptance` and the clean install (and the update check when files moved or were deleted) when the branch changed what they cover; prints times against budgets. The clean install and update check install the committed HEAD, so they run only on a committed, clean tree (otherwise: commit first). A pass of everything the branch needs records the tree's digest (contents and file modes) and which checks those were; ship accepts it only while they cover what the policy requires now; a failed rerun takes it back |
| `ship --title "..." --body <file> [--dry-run]` | Gates: a work branch, the owner approved its plan (the record's plan, else the branch's topic; docs and chore may go without one), a one-line title without a trailing period, every template section filled in and a line saying an agent made it, everything committed, `check` passed on this exact tree, commits beyond `dev`, the remote branch not moved (if it moved: `git fetch origin && git merge origin/<branch>`, then check and ship again). Then a plain `git push -u` and `gh pr create --draft --base dev` with area labels, or `gh pr edit` of the open one. An open pull request into another branch (one opened by hand into `main`) is refused with `FIX: gh pr edit <n> --base dev`; ship never retargets it |
| `report` | The factual half of the step-5 report (`--json` too), with the owner's approval and the review rounds |
| `approve <pr> --words "..."` | Records the owner's approval of that pull request (time, exact words, its number and head then) in its branch record (found by the pull request's head branch) and its review record; marks a draft ready (`gh pr ready`). The approval belongs to that number: review-fix pushes to it keep it; a replacement pull request from the same branch needs its own (`ship` moves the old one to the branch record's `approvals` history). Empty words: exit 3 |
| `land <pr> [--no-review] [--ci-timeout S] [--dry-run]` | Takes an approved pull request through the review loop, CI and the merge (below). Resumable: run it again after each stop, also after the merge (it finishes the steps after it, never merging again). `--no-review` skips the reviews (the owner's call; recorded). `--dry-run` prints the gates and the next step and changes nothing |
| `answer <pr> <round> <index> "<text>"` / `answer <pr> <round> --all "<text>"` | The answer to one finding (or every finding of a round): the fix's commit, or why it is wrong with proof. The next round's reviewer reads them |
| `summary <pr>` | The step-8 note's facts: files added, changed, moved, removed by area (from the squash commit; before the merge, the head against the base branch), the findings fixed with their answers, the rounds, CI, and whether the owner restarts the gateway (`backend/`, `__init__.py`, `plugin.yaml`, `skills/`, `profile/`) or reloads the app (`desktop/plugin.js`). Read-only |
| `status` | On a branch: plan, approval, checks on this tree, PR, pushed head, CI, and the next step. In the main checkout: every record and worktree |
| `sync` | `git fetch`, then merges `origin/dev` (never a rebase). Conflicts only in generated files: takes dev's side, rebuilds them, finishes the merge. Any other conflict: stops with the source files and leaves the merge open; resolve those (never the generated ones), `git add` them and run `sync` again: it rebuilds the generated files and makes the merge commit (no `git commit` by hand). A clean merge rebuilds the generated files too and commits them if they changed |
| `gc [--dry-run]` | Removes worktrees whose pushed branch is merged into `origin/dev`, whose pull request merged, or which the remote deleted, only when clean and holding no ignored file beyond the rebuildable caches in `policy.toml` `[gc] caches` (`node_modules/`, `.dev/`, `__pycache__/`, `*.pyc`, ...): a worktree with ignored `notes/`, `games/`, scratch or logs is kept with its branch, naming those paths and a `FIX:` (move them out, e.g. into the main checkout's `notes/`). Deletes those branches and their records. A worktree folder deleted by hand loses only git's note of it: its branch and record stay unless the branch passes the same checks, and every later gc judges that recorded branch again (removed once merged). Removes folders in the main checkout whose whole subtree is bytecode caches and empty folders (a hidden or skipped folder, a symlink or any other file keeps it). A dry run fetches nothing and changes nothing |
| `doctor [--all]` | git, gh and its account, git identity, Python, Node, the npm tools and ruff, Hermes and a hermes-agent source for the scan, the main checkout, the worktree root, a short temp folder; each problem with its fix. `--all` adds the reviewer (`review_profile` set, and a live probe of its provider) and the MacBook's reachability (optional, never a problem) |
| `config list` / `get <key>` / `set <key> <value>` | Personal settings; `set <key> ""` goes back to the default |
| `try <pr> [--keep] [--no-setup]` | Fetches the pull request's head (`<remote> refs/pull/<n>/head`, forks too) into a detached throwaway worktree in a short temp folder outside the repository, sets it up and runs `check --full` there; removes it afterwards (the folder, then `git worktree prune`), also on a failure, unless `--keep` (its path and the commands that remove it are printed). Nothing in any agent's worktree changes |
| `mac [--host H] [-- <check.py args>]` | Optional: the checks on a MacBook over ssh. The host is `--host` or the personal `mac_host` (no default: unset prints "no mac configured; CI's macOS runners cover it", exit 0). It must answer `ssh -o ConnectTimeout=3 -o BatchMode=yes <host> true` (else exit 2: unreachable, CI covers macOS). The commit must be on the remote; on the mac, in `mac_repo` (default `~/Projects/hermretro`, `~` expanded there), it fetches, adds a fresh detached worktree of the commit in a `/tmp/rd-mac.*` folder (the clone's `.dev` and `tools/npm/node_modules` linked in), runs `python3 tools/check.py [args]` there, streaming its output, and removes the worktree. The clone's own checkout is never switched or reset, so its local changes neither reach the result nor get lost. It never pushes from the mac |
| `preview [--serve] [--out DIR] [--desktop DIR]` | Builds the page's browser preview (`node tests/page/preview/build.mjs`, docs/dev/TESTING.md) into `<state>/preview` and prints its `index.html`. Needs a built Hermes Desktop source: `--desktop`, else `$HERMES_SOURCE/apps/desktop` (default `~/.hermes/hermes-agent`), symlinks resolved either way. `--serve` serves it on 127.0.0.1 on a free port (the standard library's http.server, loopback only, the Desktop's stylesheets included) until Ctrl+C |
| `release prepare [--rc] [--version X.Y.Z] --owner-words "..."` | Only when the owner asks for a release: without their words (naming a release) exit 3. Below |
| `release publish <version> [--dry-run]` | The gates, the update check, then main, the tag and the draft release. Below |
| `release verify <version> [--publish]` | Reads the draft and proves the update path; `--publish` publishes it. Below |

Every command takes `--json` (one JSON object: `command`, `ok`, `code`, `status`, the command's data, and `error`
with `message` and `fix` on a failure).

## What land does

Gates first, all reported at once: the owner's approval of this pull request (its number) is recorded (else 3); the pull request is open, into
`dev` (a draft is marked ready); the worktree's head is the pull request's head and pushed; the tree is clean and
`check` passed on it. Then, from the records (`records.next_action`):

| State | land |
|---|---|
| a round is due: none at this head yet, fewer than 3, earlier findings all answered | probes the reviewer once; unavailable, or no `review_profile`: reviews skipped with the reason recorded, on to CI. Else runs the round (minutes; CI runs meanwhile) |
| the round has findings | prints each (severity file:line problem, fix) and the steps: fix, `check`, commit, `ship`, `answer` each, `land` again. Exit 1 (`action: fix`) |
| findings not answered yet | names them. Exit 1 |
| every finding answered, nothing new pushed | the next round judges the answers |
| round 3 had findings, all answered | no 4th round: on to CI with this head, recorded as the one accepted (`accepted` in the review record) |
| 3 rounds ran and the head moved past round 3's clean head or the accepted head (a CI fix, say) | exit 3 (`action: reviews-exhausted`): nothing after it was reviewed; the owner decides: `land <n> --no-review`, or not |
| the round was void (the audit failed) twice, or gave no valid JSON twice | exit 3 with the audit's findings: the owner decides |
| clean on this head (a clean round counts only for the head it reviewed), or reviews skipped | waits for CI on the exact head, polling every 20 s up to `--ci-timeout` (default 1500 s) |
| CI failing | names the jobs and links, `gh run view <run> --log-failed`. Exit 1 (`action: fix CI`) |
| CI still running at the timeout | exit 2: run `land` again (nothing is reviewed twice) |
| CI green | the pull request rechecked (open, into `dev`, at the head), then `gh pr merge <n> --squash --delete-branch --match-head-commit <sha> --subject "<title> (#<n>)"`, `git pull --ff-only` in the main checkout when it is on `dev` and clean, `gc` of that branch only, then `summary <n>`. Exit 0. Each step after the merge is recorded (`landing` in the review record): when one fails (the pull cannot fast-forward), fix it and run `land <n>` again; it does the steps left, never merging again |

CI is green when every job passes or is skipped, except those in `policy.toml` `[land] ignore_jobs`, and the
`[land] required_jobs` ("All checks pass") are there. Every poll and the moment before the merge recheck the pull
request: a push (its head moved), a close, a merge by someone else or a retarget away from `dev` (the head unchanged,
so `--match-head-commit` would not catch it) stops land with the reason, and nothing is merged. GitHub
auto-merge stays off: land merges only itself, only through this path.

### The reviewer stays read-only

Hermes runs an agent's tools inside its gateway, so no sandbox around the command holds. Instead
(`review/`): the reviewer gets only the `file` toolset (no terminal, so no git, gh or network), reads a throwaway
`git archive` export of the head with no `.git` plus a `review/` folder of patches and the brief
(`review/brief.md`, filled in per round), in `<state>/reviews/<pr>/round<N>/`, outside every worktree's files.
After the round its session's tool calls are read from the reviewer profile's `state.db`: anything but
`read_file`/`search_files`, or a path outside the round folder, voids it. Snapshots before and after must match:
the pull request's own worktree (status, the changed files' bytes, HEAD), its branch on `origin`, and the
export's digest. Other worktrees are not watched (agents at work there change them). A void round is discarded
and run once more from a fresh export; a second void stops for the owner. Every round, its raw output and audit
are in `<state>/reviews/<pr>.json`, readable in the main checkout's `notes/reviews/pr<N>.md`.

## Releases (only when the owner says "make a release")

The rules are in the agent guide's "Releases"; these commands carry them out. The version lives only in
`plugin.yaml` and moves one patch at a time unless the owner names another (`--version`).

1. `release prepare --owner-words "<the owner's exact words>"`: refuses (exit 3) without words that ask for a
   release. Fetches; the version is the patch after `plugin.yaml` on `dev` (or `dev`'s own version when it is not
   tagged yet: an earlier candidate bumped it, and no pull request is needed). Records the words in
   `<state>/releases/<version>.json` (asked again, it forgets the commit an earlier publish chose), then `start
   chore/release-X.Y.Z --no-plan` (a worktree left from an earlier run is reused only when it is on that branch,
   clean, and differs from `origin/dev` by the `version:` line alone; otherwise it refuses with the FIX), changes
   only the `version:` line, stages only `plugin.yaml`, commits `Release X.Y.Z`, runs `check` and `ship`s the pull request "Release X.Y.Z". Then it lands like any pull
   request: `approve <n> --words "..."`, `land <n>`.
2. `release publish <version> --dry-run`, then without `--dry-run`. Gates, all reported: the owner's words are
   recorded for this version; the version pull request is merged (its merge commit is the release commit; without
   one, `origin/dev`'s head when publish first runs, kept in the release record so a retry after `dev` moves releases
   the same commit, its gates checked again); that
   commit is on `origin/dev` and its `plugin.yaml` says the version; "All checks pass" is green on that exact
   commit (`gh api repos/{owner}/{repo}/commits/<sha>/check-runs`; still running: exit 2); `origin/main` is an
   ancestor of it (main only fast-forwards; otherwise exit 3); the tag is free or already at that commit. Then
   `tools/ci/clean_install_check.py --update-from` runs on that commit in a throwaway checkout (its pass is kept for
   the commit). Then, each step skipped when done already, so a stopped publish resumes:
   `git push origin <sha>` onto `main` (a plain fast-forward push, with `HERMES_RELEASE=1` in that one push's
   environment for the local guard hooks), `git tag -a v<version> <sha>`, `git push origin refs/tags/v<version>`,
   `gh release create v<version> --verify-tag --generate-notes --notes-start-tag v<previous stable> --draft`. It
   prints the draft's address and the next step. Before the steps it records that commit as approved (all gates
   passed) in the release record. `--dry-run` fetches nothing, runs nothing and changes nothing: it
   prints the gates and every command.
3. Read the draft (add a short summary on top, and whether the real-machine checklist ran), then
   `release verify <version>`: the release exists and its notes are not empty; the tag points at `main`'s head and
   `plugin.yaml` there says the version; `clean_install_check.py --update-from v<previous stable>` passes on it.
   `release verify <version> --publish` does the same, and also needs the owner's words recorded for the version,
   the tag at exactly the commit `release publish` approved, and "All checks pass" green on it (so a draft made by
   hand or a tag moved since is refused, exit 3); when all is well, it says that a published release is immutable
   and runs `gh release edit v<version> --draft=false`.

A release candidate: `release prepare --rc ...` names `X.Y.Z-rc.M` (the next M); `release publish X.Y.Z-rc.M` tags
the `dev` commit and adds `--prerelease`; `main` does not move; `release verify` checks it is a prerelease on `dev`.

## Exit codes

`0` ok, `1` failed (fix it and run again), `2` still waiting (run again later), `3` needs the owner (an approval,
or the owner's checkout). Every failure ends with a line starting `FIX:`.

## State and settings

Records live in `<git common dir>/retrodev/` (the main checkout's `.git/retrodev/`, shared by every worktree,
never committed): `branches/<branch>.json` (plan, checks with their input digests, the passing tree, the pull
request and pushed head, the owner's approval, land's last step), `plans/<topic>.json` (the plan's approval),
`reviews/<pr>.json` and `reviews/<pr>/round<N>/` (every review round), `releases/<version>.json` (the owner's
words, the pull request, the update check's pass and the steps done), `preview/` (the page preview),
`config.toml` (personal settings).
`RETRODEV_STATE_DIR` moves the folder (for a sandbox or a trial that must leave the checkout alone).

The rules everyone shares are in `policy.toml` beside this file: check inputs and triggers, budgets, generated
files and how to rebuild them, the template's sections, labels by area, what needs a restart. Personal settings
override its `[config]` defaults:

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

## What it never does

Rewrite a remote branch, push to `main` (except `release publish`'s one fast-forward, only after its gates), run the
hardware tools, or restart Hermes; `tests/retrodev/test_rules.py` checks the source for the commands that would. It never merges a pull request the owner did not approve, or one
whose exact head has not passed CI.
