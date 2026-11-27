# Reviewing a change

How a pull request to hermretro is reviewed: by reviewer agents, read-only, each with a brief made from
[brief.md](brief.md) (and [security.md](security.md) for a sensitive change), holding the change to
[rules.md](rules.md). The author answers every finding; the maintainer decides what merges.

## Tiers

A change's tier comes from the paths it changes, against `origin/dev`:

- **Light**: Markdown and tests alone. No review. Markdown an agent acts on is not light: the plugin's
  `skills/` and `profile/`, the development skills in `.agents/`, `AGENTS.md`, and this folder.
- **Sensitive**: a path where a missed bug costs a user most, or more than 1000 changed lines (lockfiles and
  generated files not counted). Sensitive comes first: a change with one sensitive path is sensitive whatever
  else it holds. A security review runs beside pass 1, and beside a later pass when it reads a sensitive path or
  follows the fix of a security finding; a change sensitive for its size alone has it at pass 1 only.
  - the broker and its handshake: `backend/broker/`, the code fingerprint in `backend/system/paths.py`;
  - the prepared engine copy, setup, removal and the factory reset: `backend/setup/`;
  - the hardware approvals: `backend/hermes/hooks.py`;
  - the player's loopback server: `backend/player/server.py`;
  - what runs on a user's machine from the engine: `engine/scripts/`;
  - the plugin's entry point and manifest: `__init__.py`, `plugin.yaml`;
  - CI and the update and install checks: `.github/workflows/`, `.github/actions/`, `tools/ci/`.
- **Standard**: everything else. One review per pass.

## Passes

1. **Pass 1** reads the whole change, pinned to its pushed head, in a checkout of that head: the author's
   worktree is free meanwhile.
2. The author answers every finding (below) and commits the fixes.
3. **Another pass** runs only when an Important finding was fixed, or commits came after the pass that no
   answer accounts for. It reads what changed since the last pass, and how it fits the rest of the change;
   commits of tests alone get a pass that reads the tests alone, and commits of Markdown nothing acts on
   (as for Light) none. A fixed Nit or a changed Question needs none.
4. **Three passes at most.** A fourth runs only when the maintainer asks for it.

Each pass's brief, findings and answers stay out of the repository, in `notes/reviews/<branch>/<pass>/`,
with what was approved in `notes/reviews/<branch>/decisions.md`. The pull request's Review section says
each pass's tier, models and outcome in a line.

## Findings and answers

A reviewer writes each finding as a heading, most important first, its evidence beneath it:

```
## Important: <path>:<line> <what is wrong>
## Nit: <path>:<line> <what would be better>
## Pre-existing: <path>:<line> <what is wrong>
## Question: <path>:<line> <a choice to justify>
## Out of scope: <path>:<line> <what>
```

or `No findings.` alone. Every finding gets one answer, checked against the code first:

| Finding | Answer |
|---|---|
| Important | `fixed`, or `wrong` or `intentional` and why |
| Nit (three at most) | `fixed`, or `declined` and why |
| Question | `changed`, or `kept` and why |
| Pre-existing, Out of scope | `noted`: for the maintainer after the merge, never fixed in this change |

A finding that would change what was approved is written under Out of scope and noted: the author carries it
into the merge report for the maintainer. A finding whose fix would weaken a test or a check is not fixed: the
author answers it `intentional` or `wrong` with why, and tells the maintainer. A finding seen before gets a
proposal for a rule here, a lint or a test that keeps it from coming back.
