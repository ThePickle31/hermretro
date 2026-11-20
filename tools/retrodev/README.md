# retrodev

`python tools/retrodev <command>` is hermretro's development CLI. It runs the working agreement between the owner
and the agents that build the plugin, and refuses to skip a step: no work before the owner approves the plan, no
push of a tree that did not pass the checks, no pull request with an empty template section. Standard-library
Python 3.11+, development only (it never runs inside Hermes). Tests: `tests/retrodev/`. Every command, `new` kind
by kind, what `land` does, releases and state: `tools/retrodev/REFERENCE.md`.

## Quick path

1. `python tools/retrodev plan new <topic>`, then fill in `notes/plans/<topic>.md` (its `Title:` line too: one plain sentence, at most 100 characters, no trailing period)
2. `python tools/retrodev plan approve <topic> --words "<the owner's exact words>"`
3. `python tools/retrodev start <kind>/<topic>`, then `cd` into the worktree it prints: `<worktree_root>/<topic>`, by default a `<checkout>-wt` folder next to the checkout (`python tools/retrodev config list` shows it)
4. `python tools/retrodev new <kind> ...` for each piece (`--dry-run` lists its files first, also from `dev`), then edit
5. `python tools/check.py fix`, then `git add -A && git commit -m "..."`
6. `python tools/retrodev check`
7. fill in `notes/pr/<topic>.md` (check's last line names what is left; check What changed still matches the code; start copied it from the plan)
8. `python tools/retrodev ship --dry-run`, then `python tools/retrodev ship --title '<one plain sentence>'`

`RETRODEV_AGENT=<agent, model>` names the agent in the body's `Made by` line (default Hermes); set it per command
before `start` writes the body, or edit the line.

`notes/` is in the main checkout, shared by every worktree: the plan and the pull request body are never in the
worktree, and every next step names them by their full path.

## The flow, from plan to merge

| Step | Who | Command |
|---|---|---|
| 1 discuss | owner and agent | |
| 2 plan | agent | `plan new <topic>` writes `notes/plans/<topic>.md` (git-ignored) from the template; the agent fills it in |
| 3 go | owner says start | `plan approve <topic> --words "<the owner's exact words>"` (the agent runs it) |
| 4 build | agent | `start <kind>/<topic>` (feat, fix, docs, or chore for refactors that change no behaviour), `new ...`, edit, `check` (or `check --watch`), commit, `ship --title ...` (the body `notes/pr/<topic>.md` is written early: `start`, or `plan approve` inside the linked branch, writes it from the plan, and the agent fills it in while building; `ship` writes it only when it is missing, then stops for it to be filled in; later ones need only `ship`) |
| 5 report | agent | `report` gives the facts (PR, commits, files by area, checks, CI, what to restart); the agent adds the prose |
| 6 approve | owner says approve, merge or go ahead | `approve <pr> --words "<the owner's exact words>"`, once per pull request |
| 7 land | agent | `cd <main checkout> && python tools/retrodev land <pr>` in the background: up to 3 read-only review rounds, CI on the exact head, the squash merge; between rounds the agent fixes, checks, ships and `answer`s each finding |
| 8 summary | agent | `summary <pr>` gives Added / Changed / Fixed / Removed, the rounds, CI and what the owner restarts |

At any time `status` names the one next step. `takeover <branch>` takes over a teammate's pushed branch, `sync`
merges `dev` in, `doctor` checks the machine, `gc` tidies merged worktrees, `stats` shows how the flow is going.

## Commands

Each in full: `tools/retrodev/REFERENCE.md`, "Commands".

- `plan new|show|approve|link`: the plan in `notes/plans/<topic>.md` and the owner's go (approve refuses the
  untouched template and a `Title:` line ship would refuse)
- `start <kind>/<topic>`, `takeover <branch>`: a worktree on a new or a teammate's branch, set up
- `new feature|rpc|tool|event|listener|page|tab|slot|contribution ...`: a piece with every registry line it needs
  (`tools/retrodev/REFERENCE.md`, "new")
- `check`, `ship`, `report`, `approve <pr>`, `land <pr>`, `answer <pr> ...`, `summary <pr>`: build to merge
- `status`, `sync`, `gc`, `doctor`, `config`, `stats`: any time
- `try <pr>`, `mac`, `preview`: beyond one change; `engine update <version>` and `release ...`: only with the
  owner's words

## Releases

Only when the owner says "make a release": `release prepare`, `release publish`, `release verify`; the steps and
their gates: `tools/retrodev/REFERENCE.md`, "Releases".

## Exit codes

`0` ok, `1` failed (fix it and run again), `2` still waiting (run again later), `3` needs the owner (an approval,
or the owner's checkout). Every failure ends with a line starting `FIX:`. Every command takes `--json`.

## What it never does

Rewrite a remote branch, push to `main` (except `release publish`'s one fast-forward, only after its gates), run the
hardware tools, or restart Hermes; `tests/retrodev/test_rules.py` checks the source for the commands that would. It
never merges a pull request the owner did not approve, or one whose exact head has not passed CI.
