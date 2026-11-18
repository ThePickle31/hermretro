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
| 6 approve | owner | (the review and landing commands come in the next version) |
| 7 land | | CI, the review loop and the merge (next version) |
| 8 summary | agent | (next version) |

At any time `status` names the one next step, `doctor` checks the machine, `sync` brings in `dev`, `gc` tidies up.

## Commands

| Command | What it does |
|---|---|
| `plan new <topic>` | Writes the plan template (Goal, What changes, Where files go, How it is tested, How the owner and users use it, Not in scope) unless the file exists |
| `plan show [topic]` | The plan and its approval; with no topic, the current branch's plan (else every plan) |
| `plan approve <topic> --words "..."` | Records the owner's go with the time, their exact words and the plan's hash (status notes a later change) |
| `plan link <topic>` | From a branch made by hand: record that it works under that plan |
| `start <kind>/<topic> [--plan <topic>] [--no-plan] [--no-setup]` | kind: feat, fix, docs, chore. `--plan` names the plan when one plan covers several branches (default: the branch's topic). Needs an approved plan (docs and chore may say `--no-plan`), the main checkout on `dev` and clean. Fetches, makes the worktree at `<worktree_root>/<topic>` on a new branch from `origin/dev` (no upstream: it can never push to `dev`), runs `npm ci --prefix tools/npm` and `python tools/py/setup.py` there, prints the path |
| `check [names...] [--again] [--full] [--watch]` | Runs `tools/check.py` for the checks whose inputs changed since their last pass on the branch (`ok (cached)` otherwise; a check's inputs, in `policy.toml` `[checks.inputs]`, include the tools it runs and their pins, `tools/check.py` and `policy.toml`); `--watch` runs again on every file change and on a commit or a clean/dirty change, so committing lets the waiting install checks run; adds `acceptance` and the clean install (and the update check when files moved or were deleted) when the branch changed what they cover; prints times against budgets. The clean install and update check install the committed HEAD, so they run only on a committed, clean tree (otherwise: commit first). A pass of everything the branch needs records the tree's digest (contents and file modes); a failed rerun takes it back |
| `ship --title "..." --body <file> [--dry-run]` | Gates: a work branch, the owner approved its plan (the record's plan, else the branch's topic; docs and chore may go without one), a one-line title without a trailing period, every template section filled in and a line saying an agent made it, everything committed, `check` passed on this exact tree, commits beyond `dev`, the remote branch not moved (if it moved: `git fetch origin && git merge origin/<branch>`, then check and ship again). Then a plain `git push -u` and `gh pr create --draft --base dev` with area labels, or `gh pr edit` of the open one |
| `report` | The factual half of the step-5 report (`--json` too) |
| `status` | On a branch: plan, approval, checks on this tree, PR, pushed head, CI, and the next step. In the main checkout: every record and worktree |
| `sync` | `git fetch`, then merges `origin/dev` (never a rebase). Conflicts only in generated files: takes dev's side, rebuilds them, finishes the merge. Any other conflict: stops with the files. A clean merge rebuilds the generated files too and commits them if they changed |
| `gc [--dry-run]` | Removes worktrees whose pushed branch is merged into `origin/dev`, whose pull request merged, or which the remote deleted, only when clean and holding no ignored file beyond the rebuildable caches in `policy.toml` `[gc] caches` (`node_modules/`, `.dev/`, `__pycache__/`, `*.pyc`, ...): a worktree with ignored `notes/`, `games/`, scratch or logs is kept with its branch, naming those paths and a `FIX:` (move them out, e.g. into the main checkout's `notes/`). Deletes those branches and their records. A worktree folder deleted by hand loses only git's note of it: its branch and record stay unless the branch passes the same checks, and every later gc judges that recorded branch again (removed once merged). Removes folders in the main checkout whose whole subtree is bytecode caches and empty folders (a hidden or skipped folder, a symlink or any other file keeps it). A dry run fetches nothing and changes nothing |
| `doctor [--all]` | git, gh and its account, git identity, Python, Node, the npm tools and ruff, Hermes and a hermes-agent source for the scan, the main checkout, the worktree root, a short temp folder; each problem with its fix |
| `config list` / `get <key>` / `set <key> <value>` | Personal settings; `set <key> ""` goes back to the default |

Every command takes `--json` (one JSON object: `command`, `ok`, `code`, `status`, the command's data, and `error`
with `message` and `fix` on a failure).

## Exit codes

`0` ok, `1` failed (fix it and run again), `2` still waiting (run again later), `3` needs the owner (an approval,
or the owner's checkout). Every failure ends with a line starting `FIX:`.

## State and settings

Records live in `<git common dir>/retrodev/` (the main checkout's `.git/retrodev/`, shared by every worktree,
never committed): `branches/<branch>.json` (plan, checks with their input digests, the passing tree, the pull
request and pushed head), `plans/<topic>.json` (the approval), `config.toml` (personal settings).
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

## What it never does

Rewrite a remote branch, push to `main`, run the hardware tools, or restart Hermes; `tests/retrodev/test_rules.py`
checks the source for the commands that would.
