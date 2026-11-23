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
  bumped; build work follows it only after the user approves.
- **Never redefine a failing check to make it pass.** If a check in
  `TEST-PLAN.md` fails, keep the original wording and the failing evidence.
  Fix the game, or propose a written, approved scope change that supersedes the
  check (and keep the old one marked superseded, not edited away).
- **The first build is the whole brief.** Its in-scope list is what the first
  build delivers, complete and playable, so keep it to what the user asked for
  and fits a Game Boy game. Ideas beyond it go in the backlog.
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
4. **Review with the user.** Summarize the brief in a few lines, list open
   questions, and ask for approval. Do not author scenes, art or scripts, or
   build, on silence: until approval the project holds only its starter and
   these documents.
5. **Hand off.** Once approved, load `hermretro:authoring` and build every
   in-scope item in one go: a build along the way is a checkpoint, not a
   hand-off. Run `TEST-PLAN.md` checks with `hermretro:rom-debugging` and
   record results against the exact ROM SHA-256; use `hermretro:pixel-art` for
   art and palettes. Present the game only when all of it is in.

## Hardware budget pointers

Write budgets as assumptions with a source. Useful references:
[hardware and imports](../pixel-art/references/hardware-and-imports.md)
(palettes, sprites, tiles), [cartridge and hardware limits](../rom-debugging/references/hardware-and-cartridge.md),
and the [agent guide](../authoring/references/agent-guide.md) for the kinds of
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
