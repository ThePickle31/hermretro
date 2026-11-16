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

Status: not run / passed / failed / needs review / blocked / superseded (by Dn)

## Results log

Append one entry per run; do not overwrite earlier failures.

| Date | Check | ROM SHA-256 / size | Inputs (held-button sets, frame counts) or user action | Observed | Result | Evidence path |
|---|---|---|---|---|---|---|
| | | | | | | |
