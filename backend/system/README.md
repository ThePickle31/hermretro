# backend/system

The machine, shared by every feature and the broker: locations (`paths.py`), every Linux/macOS difference and
the supported-system check (`host.py`), events between features (`events.py`), the Hermes home handed over
by the Hermes layer (`hermes_home.py`), and which feature flags are on (`flags.py`; `page/app/flags.js` lists
them). Standard library only; it imports nothing of ours outside itself (not even `backend.hermes`).

## What it adds

No RPCs, tools, hooks or events of its own. `events.py` is how features connect: `emit(name, **payload)` in the
owner, `@on(name)` in another feature's `backend/<feature>/listeners.py`; listener errors are logged and never reach the emitter.

## Front door

A shared layer: features import its modules directly (`from ..system import paths`).

## Tests

`tests/backend/system/`.

## Adding here

Only what every feature and the broker need, standard library only. A value only Hermes knows is handed in by
the Hermes layer (as `hermes_home.provide` is), never imported.
