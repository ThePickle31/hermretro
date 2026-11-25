# Test plan

Brief revision this plan follows: 1

Each check is observable. Keep the expected behaviour and the actual result
separate. Never reword a failing check to make it pass: fix the game, or
supersede the check through an approved DECISIONS entry and keep it listed
here as superseded.

Evidence kinds are not interchangeable: static analysis, PyBoy frames,
browser preview (user-observed), live stream to the device (host emulation),
physical capture, flashed cartridge (human-observed).

## Checks

| ID | Given | When | Then | Evidence kind | Status |
|---|---|---|---|---|---|
| T1 | Example: 2 of 3 seeds collected | the player walks into the gate | the locked dialogue appears and the gate stays closed | PyBoy frames | not run |
| F1 | power-on of the exact ROM the user gets | the game is played to its ending in one run, with no checkpoint restores, state loads or memory writes | the ending shows | PyBoy frames (one recording from a fresh boot, named as the report's finishRun) | not run |

Status: not run / passed / failed / needs review / blocked / superseded (by Dn)

ID: 1 to 4 letters, an optional hyphen, 1 to 3 digits and an optional letter
(T1, AUD2, GATE-1, T3b); case does not matter, so T3b and T3B are one check.
Each check is a row of this table (or a line `T1: Given ..., when ..., then ...`);
a row with any other ID is not read as a check.

Every build report gives each check not superseded its result on that build's
ROM: a check not played on that ROM is not run, even if it passed before.
Bind each check to the recording that passed it (`chromatic_playtest`, action
`bind`); `chromatic_playtest {}` replays every bound check on a new ROM.

## Difficulty

From the F1 run on the final ROM: time to finish, deaths or retries and where,
and what was tuned (speeds, timings, counts) and why.

-

## Results log

Append one entry per run; do not overwrite earlier failures.

| Date | Check | ROM SHA-256 / size | Inputs (held-button sets, frame counts) or user action | Observed | Result | Evidence path |
|---|---|---|---|---|---|---|
| | | | | | | |
