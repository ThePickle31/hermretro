# retrodev

`python tools/retrodev <command>` is hermretro's development CLI. It runs the working agreement between the owner
and the agents that build the plugin, and refuses to skip a step: no work before the owner approves the plan, no
push of a tree that did not pass the checks, no pull request with an empty template section. Standard-library
Python 3.11+, development only (it never runs inside Hermes). Tests: `tests/retrodev/`. Every command, `new` kind
by kind, what `land` does, releases and state: `tools/retrodev/REFERENCE.md`.

## Quick path

1. `python tools/retrodev plan new <topic>`, then fill in `notes/plans/<topic>.md` (its `Title:` line too: one plain sentence, at most 100 characters, no trailing period)
2. `python tools/retrodev plan approve <topic> --words "<the owner's exact words>"`
3. `RETRODEV_AGENT='<agent, model>' python tools/retrodev start <kind>/<topic>` (it fetches and branches from `origin/dev`), then enter its printed worktree: by default a `<checkout>-wt` folder next to the checkout (`python tools/retrodev config list` shows it). `docs/` and `chore/` may skip steps 1-2: `start <kind>/<topic> --no-plan`.
4. `python tools/retrodev new <kind> ...` (`--dry-run` previews it, even on `dev`); use `--no-check` on intermediate scaffolds and run step 6 on the finished tree. An RPC in an `rpcs.py` over 350 lines takes `--module <name>_rpcs`; an RPC about one game takes `--game` (a `game` param with the library id; `NO_GAME` if unknown).
5. `python tools/check.py fix`, then `git add -A && git commit -m "..."`
6. `python tools/retrodev check`
7. fill in `notes/pr/<topic>.md` (check's last line names what is left; check What changed still matches the code; start copied it from the plan)
8. `python tools/retrodev ship --dry-run`, then `python tools/retrodev ship --title '<one plain sentence>'`

`RETRODEV_AGENT=<agent, model>` names the agent in the body's `Made by` line (default Hermes; `start` says when it
is unset). Set it before `start` or `takeover`, which record it for the branch, so a later `plan approve` or `ship`
that writes the body names that agent; or edit the line.

`notes/` is in the main checkout, shared by every worktree. `start` writes the pull request body from the plan or,
with `--no-plan`, the template.

### Add a plugin tool

```sh
python tools/retrodev new tool library probe --dry-run    # the files it would write, and its next steps (--json)
python tools/retrodev new tool library probe --step 'Probing the game' 'Probed the game'
```

`new` writes every registry line (`plugin.yaml`, the page's step words, the counts, the README line, the snapshot).
You edit three files, each named in its next steps:

1. the handler module, `backend/<feature>/tools.py` (or `probe_tools.py` beside it when `tools.py` is long; the
   first next step says which): the schema and the handler;
2. its test, `tests/backend/<feature>/test_tool_<name>.py` (here `test_tool_probe.py`): it pins the stub's answer,
   so change it with the real one;
3. the CONTRACT line the next step quotes as `docs/dev/CONTRACT.md:<line>`: replace `say what it does and when the
   agent calls it` after `chromatic_probe`.

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
   each moved public name as `from .<new> import X as X`: ruff keeps that, but `fix` deletes a plain unused import
   (so does an import it kept only for importers, once its last use moves out).
2. Moved tools keep their `TOOLS` positions (the registration snapshot pins the order): import them into the
   module that lists `TOOLS`, at the same places.
3. Tests that use a moved private name (`_x`) import the new module and patch there, as for each dependency
   the moved code imports: `mock.patch.object(<new module>, "dep")`, not the old module.
4. Search as in step 1 of the rename above; check sibling docstrings and comments, the feature README and
   `tests/retrodev` (trial tests read file text); keep references to the public API that goes through the old
   module.
5. Aim every resulting module under the 400-line warning (above 400 warns, above 600 fails), then `python
   tools/check.py fix`, commit and `python tools/retrodev check`.

## The flow, from plan to merge

| Step | Who | Command |
|---|---|---|
| 1 discuss | owner and agent | |
| 2 plan | agent | `plan new <topic>` writes `notes/plans/<topic>.md` (git-ignored) from the template; the agent fills it in |
| 3 go | owner says start | `plan approve <topic> --words "<the owner's exact words>"` (the agent runs it) |
| 4 build | agent | `start <kind>/<topic>` (feat, fix, docs, or chore for refactors that change no behaviour), `new ...`, edit, `check` (or `check --watch`), commit, `ship --title ...` (the body `notes/pr/<topic>.md` is written early: `start`, or `plan approve` inside the linked branch, writes it from the plan for the agent to fill in; `ship` writes it only when it is missing, then stops; later ones need only `ship`) |
| 5 report | agent | `report` gives the facts (PR, commits, files, checks, CI, restarts); the agent adds the prose |
| 6 approve | owner says approve, merge or go ahead | `approve <pr> --words "<the owner's exact words>"`, once per pull request |
| 7 land | agent | `cd <main checkout> && python tools/retrodev land <pr>` in the background: 1 to 3 read-only review rounds, CI on the exact head, the squash merge; between rounds the agent fixes, checks, ships and `answer`s each finding |
| 8 summary | agent | `summary <pr>` gives Added / Changed / Fixed / Removed, the rounds, CI and what the owner restarts |

At any time `status` names the one next step. `takeover <branch>` takes over a teammate's pushed branch, `sync`
merges `dev` in.

## Commands

Each in full: `tools/retrodev/REFERENCE.md`, "Commands".

- `plan new|show|approve|link`: the plan in `notes/plans/<topic>.md` and the owner's go (approve refuses the
  untouched template and a `Title:` line ship would refuse)
- `start <kind>/<topic>`, `takeover <branch>`: a worktree on a new or a teammate's branch, set up
- `new feature|rpc|tool|event|listener|page|tab|slot|contribution ...`: a piece with every registry line it needs
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
