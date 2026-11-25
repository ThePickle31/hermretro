---
name: game-planning
description: "Use when planning a new GB game. Write brief and tests."
version: 0.1.0
license: MIT
metadata:
  hermes:
    tags: [chromatic, modretro, game-boy, planning, game-design]
    related_skills: [hermretro:authoring, hermretro:pixel-art, hermretro:rom-debugging]
---

# Plan a Chromatic game before building it

Use for Plan first or when the user asks to plan a change to an existing game.
The output is a small set of versioned planning documents inside the project,
approved by the user, that the build and test work follows.

## Rules

- **Plans never replace native sources.** The `.gbsproj` / `.gbsres` project
  stays the source of truth for the game. Planning documents describe intent
  and acceptance; they are not game data.
- **Approve before building.** Do not create scenes, actors, assets or scripts
  for the plan until the user has approved the brief. Record the approval
  (who, when, brief revision) in the brief.
- **Write scope changes down.** Any change to scope, controls, core loop, or an
  acceptance check is written into `DECISIONS.md` and the brief's revision is
  bumped; build work follows it only after the user approves. A change made
  while building (a feature cut or added, other controls, another win
  condition, fewer rooms) is a scope change too: write its entry, status
  proposed, before the build report, and name it in the report's notes. The
  brief and the game card (`chromatic_game_info`) describe the game as it
  ships, never as first planned.
- **Never redefine a failing check to make it pass.** If a check in
  `TEST-PLAN.md` fails, keep the original wording and the failing evidence.
  Fix the game, or propose a written, approved scope change that supersedes the
  check (and keep the old one marked superseded, not edited away).
- **The first build is the whole brief.** Its in-scope list is what the first
  build delivers, complete and playable, so keep it to what the user asked for
  and fits a Game Boy game. Ideas beyond it go in the backlog.
- **Finishable is the bar.** A game is finishable when one run from power-on
  reaches the ending on the exact ROM the user gets, with no checkpoint
  restores, save-state loads, memory writes or debug shortcuts. Every test plan
  has this check with the ID F1, as in the template (the build report ties F1 to
  the run's recording); a route pieced together from checkpoints does not pass
  it, and a build whose ROM changed (another SHA-256) needs it played again.
- **Label assumptions.** Hardware budgets in the brief are assumptions until
  graphics analysis, a real build and emulator runs confirm them. Hardware
  qualification needs a human observing the flashed cartridge.

## Workflow

1. **Interview briefly.** Ask only what you cannot reasonably default, in one
   short message: the pitch, who plays it, core loop, controls, mono or color,
   tone/art references, rough size, and anything explicitly out of scope.
   Offer sensible defaults rather than a long questionnaire.
2. **Find the project folder.** Planning docs live in the game's project folder
   under `docs/game/`. If the project does not exist yet, create it first (load
   `hermretro:authoring`; without `destinationPath`,
   `chromatic_project_create` puts it in the Studio's games folder). A
   Hermes conversation stays bound to one project root, so plan in the same
   chat you will build in. These files are outside `project/` and `assets/`,
   so writing them does not change the engine's project revision.
3. **Write the documents** from the [templates](#templates), filling what you
   know and marking unknowns as open questions:
   - `docs/game/GAME-BRIEF.md`: concept, controls, core loop, world/rooms,
     characters, art direction and palette intent, audio intent, scope and
     explicit out-of-scope, hardware budget assumptions, milestones, approval.
   - `docs/game/BACKLOG.md`: small ordered items, each linked to brief sections
     and test IDs; first-build items first.
   - `docs/game/TEST-PLAN.md`: observable acceptance checks in
     Given/When/Then form with the evidence each needs. Example: "Given 2 of 3
     seeds collected, when the player walks into the gate, then the locked
     dialogue appears and the gate stays closed." Name the evidence kind:
     static analysis, PyBoy frames, browser (user-observed), live stream, or
     physical cartridge (human-observed).
   - `docs/game/DECISIONS.md`: dated, numbered entries for decisions and scope
     changes, with status (proposed / approved / superseded).

   Before review, go through the [solvability checklist](#solvability-checklist)
   for every room and every placed hazard, and write what it finds into the
   brief's Solvability table and the test plan.
4. **Review with the user.** Summarize the brief in a few lines, list open
   questions, and ask for approval. Do not author scenes, art or scripts, or
   build, on silence: until approval the project holds only its starter and
   these documents.
5. **Hand off.** Once approved, load `hermretro:authoring` and build every
   in-scope item in one go: a build along the way is a checkpoint, not a
   hand-off. Run `TEST-PLAN.md` checks with `hermretro:rom-debugging` and
   record results against the exact ROM SHA-256; bind each check to the
   recording that passed it (`chromatic_playtest` with action `bind`) and run
   `chromatic_playtest {}` after every rebuild to replay them all; use `hermretro:pixel-art` for
   art and palettes. Present the game only when all of it is in.
6. **Report against the plan.** Every `chromatic_build_report` for a game with
   a test plan gives each open check its result on that build's ROM (`checks`;
   a bound check's result agrees with the last `chromatic_playtest` run on it)
   and a `difficulty` statement from your own finishable run; the tool refuses
   the report without them. When F1 is `passed` or `failed`, `finishRun` names
   that run's recording, which must be of this ROM with no checkpoint restores. A check you did not play on this ROM is `not run`,
   even if it passed on an earlier build, and the card lists it as untested.
   Update the plan's Status column and Results log in the same turn. When
   there is no finishable run on this ROM, the report says what is true:
   - **The ending was unreachable** (a bug, a hazard with no way through): F1
     is `failed`, and `difficulty` says where the run stopped and why.
   - **The run was skipped** on this build: F1 is `not run`, and `difficulty`
     says so and names the last ROM finished in one run, if any.
   - **The design has no ending** (a toy, a sandbox, an endless game): while
     planning, write F1 as one run from power-on through every room and
     mechanic with no dead end; `difficulty` says how a run goes and where a
     player fails or gets stuck.

## Solvability checklist

Check each item on paper while planning, then on the built ROM:

- **Every goal is reachable.** Each required item, switch and exit can be
  reached from the start; a gate never needs more items than the game holds.
- **One row per placed hazard.** The Solvability table has a row for each
  hazard and gate where it is placed (scene and cell), not one per kind: three
  sparks are three rows. Hazards close together are checked together: the
  space between them must hold the player, with a way out on the far side.
- **Hazard lanes leave a way through.** For each moving hazard, write its lane
  (cells it covers), its period and the player's time to cross the lane at
  their move speed. The safe window must be longer than the crossing, with
  margin for a human; a required item or exit inside a lane needs a window to
  reach it and to leave.
- **Jumps fit the player's jump.** In a platformer, check every gap, ledge
  and hazard the player must jump against the jump's height and length.
  GB Studio's defaults (a held jump rises 66 px and carries about 80 px at
  walking speed) are in the authoring skill's
  [scene types](../authoring/references/scene-types.md#platformer); if the
  project changes the jump's engine fields, measure it once on a build and
  write the numbers in the brief. Leave a human margin: a required jump
  should not need the longest jump at full speed. A landing higher than the
  take-off shortens the jump, since the player lands on it on the way down: a
  ledge near the top of the jump is reached only from close in.
- **Respawn is safe.** Start and respawn points sit outside every lane and
  hazard, and a respawn mid-move lands on a whole cell.
- **No dead ends.** No item is used up where another goal still needs it, no
  door locks behind the player without a way back, and a timer is longer than
  the shortest route with room to spare.
- **Failure returns to a winnable state.** Losing restores the counts, items and
  positions the run needs to continue or restart.
- **The tuning is written down.** Speeds, timings and counts that set the
  difficulty are in the brief, and the build report's difficulty says how they
  played.

## Hardware budget pointers

Write budgets as assumptions with a source. Useful references:
[hardware and imports](../pixel-art/references/hardware-and-imports.md)
(palettes, sprites, tiles), [cartridge and hardware limits](../rom-debugging/references/hardware-and-cartridge.md),
and the [operating contract](../authoring/references/operating-contract.md) for the kinds of
evidence each tool establishes. Do not copy a presumed cartridge capacity or
mapper from a brand name; leave unknowns unknown.

## Templates

Copy and fill these; keep their revision and status fields.

- [GAME-BRIEF.md](templates/GAME-BRIEF.md)
- [BACKLOG.md](templates/BACKLOG.md)
- [TEST-PLAN.md](templates/TEST-PLAN.md)
- [DECISIONS.md](templates/DECISIONS.md)

Open them with
`skill_view("hermretro:game-planning", file_path="templates/<file>")`.

Next: load `hermretro:authoring` to build the approved first build.
