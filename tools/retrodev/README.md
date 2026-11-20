# retrodev

`python tools/retrodev <command>` is hermretro's development CLI. It runs the working agreement between the owner
and the agents that build the plugin, and refuses to skip a step: no work before the owner approves the plan, no
push of a tree that did not pass the checks, no pull request with an empty template section. Standard-library
Python 3.11+, development only (it never runs inside Hermes). Tests: `tests/retrodev/`. Every command, `new` kind
by kind, what `land` does, releases and state: `tools/retrodev/REFERENCE.md`.

## Quick path

1. `python tools/retrodev plan new <topic>`, then fill in `notes/plans/<topic>.md` (its `Title:` line too: one plain sentence, at most 100 characters, no trailing period)
2. `python tools/retrodev plan approve <topic> --words "<the owner's exact words>"`
3. `RETRODEV_AGENT='<agent, model>' python tools/retrodev start <kind>/<topic>` (it fetches and branches from `origin/dev`, never your local `dev`; `RETRODEV_AGENT` so the body's `Made by` line names the agent from the start; it writes the pull request body `notes/pr/<topic>.md`, from the plan or, with `--no-plan`, the template), then `cd` into the worktree it prints: `<worktree_root>/<topic>`, by default a `<checkout>-wt` folder next to the checkout (`python tools/retrodev config list` shows it)
4. `python tools/retrodev new <kind> ...` for each piece (`--dry-run` lists its files first, also from `dev`), then edit; an RPC in a feature whose `rpcs.py` is near the size limit (over 350 lines: `tools/layout.toml` `[size]` `warn` less 50; library's today) takes `--module <name>_rpcs`, so its handler gets its own module; an RPC about one game takes `--game` (a `game` param, its library id, answered with `NO_GAME` unless the library has it)
   When chaining several scaffolds, add `--no-check` to intermediate `new` commands to avoid repeating their
   checks; run step 6 on the finished tree.
5. `python tools/check.py fix`, then `git add -A && git commit -m "..."`
6. `python tools/retrodev check`
7. fill in `notes/pr/<topic>.md` (check's last line names what is left; check What changed still matches the code; start copied it from the plan)
8. `python tools/retrodev ship --dry-run`, then `python tools/retrodev ship --title '<one plain sentence>'`

`RETRODEV_AGENT=<agent, model>` names the agent in the body's `Made by` line (default Hermes); set it per command
before `start` or `takeover`, which record it for the branch: a later `plan approve` or `ship` that writes the body
names that agent even without the variable (`takeover`'s printed `plan approve` step carries it too); or edit the
line; `start` says so when it is unset.

`notes/` is in the main checkout, shared by every worktree: the plan and the pull request body are never in the
worktree, and every next step names them by their full path.

### Add a plugin tool

```sh
python tools/retrodev new tool library probe --dry-run    # the files it would write, and its next steps (--json)
python tools/retrodev new tool library probe --step 'Probing the game' 'Probed the game'
```

`new` writes every registry line (`plugin.yaml`, the page's step words, the counts, the README line, the snapshot).
You edit three files, each named in its next steps:

1. the handler module, `backend/<feature>/tools.py` (or `backend/<feature>/<name>_tools.py`, here `probe_tools.py`,
   when `tools.py` is long; the first next step says which): the schema and the handler;
2. its test, `tests/backend/<feature>/test_tool_<name>.py` (here `test_tool_probe.py`): it pins the stub's answer,
   so change it with the real one;
3. the CONTRACT line: the next step quotes it as `docs/dev/CONTRACT.md:<line>`; replace `say what it does and when
   the agent calls it` after `chromatic_probe` with exactly that.

Then steps 5 to 8 of the Quick path.

### Rename or move a module

1. `git grep -n <old>` (the old module name and its path) across `backend/`, `tests/` (the `tests/retrodev` trial
   tests pin paths too), `tools/retrodev/` (the scaffolds' hint strings) and `docs/`; change every hit.
2. First rename any local variable the new module name would shadow (`games = ...` beside `from . import games`).
3. `git mv` the file, then `python tools/check.py fix` (import order, formatting), commit and `python tools/retrodev
   check`.

### Split a long module

1. Move the code to `<feature>/<new>.py`. Put shared dependencies (an error class, a lock) in that module or
   a small sibling helper: the new module must not import back from the old one. In the old module re-export
   each moved public name as `from .<new> import X as X`: ruff keeps that, but `fix` deletes a plain unused import.
2. Tests that use a moved private name (`_x`) import the new module and patch names there.
3. Search the old module name and path with `git grep -n` across `backend/`, `tests/`, `tools/retrodev/` and `docs/`.
   Check sibling docstrings and comments, the feature README and `tests/retrodev` (trial tests read file text).
   Keep references to the public API that still go through the old module.
4. Aim every resulting module under the 400-line warning, then `python tools/check.py fix`, commit and `python
   tools/retrodev check`.

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

Only when the owner says "make a release": `release run`, or step by step `release prepare`, `publish`, `verify`, `next`;
the steps and their gates: `tools/retrodev/REFERENCE.md`, "Releases".

## Exit codes

`0` ok, `1` failed (fix it and run again), `2` still waiting (run again later), `3` needs the owner (an approval,
or the owner's checkout). Every failure ends with a line starting `FIX:`. Every command takes `--json`.

## What it never does

Rewrite a remote branch, push to `main` (except `release publish`'s one fast-forward, only after its gates), run the
hardware tools, or restart Hermes; `tests/retrodev/test_rules.py` checks the source for the commands that would. It
never merges a pull request the owner did not approve, or one whose exact head has not passed CI.
