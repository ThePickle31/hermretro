# Hermes's install scanner

Every `hermes plugins install` and `update` scans every file the plugin ships. One finding rated **critical**
blocks the install for everyone and cannot be overridden; one rated **high** makes every install ask for
confirmation. `python tools/check.py scan` runs the same scanner on what a commit would ship and fails unless the
verdict is `safe`; CI runs it on every pull request, and nightly against the newest Hermes.

## What trips it

- A download piped straight into a shell (download to a file, then run it).
- A line in a guide or contributor doc that opens with a modify verb and names an agent configuration file
  (inside such a guide, say "this guide" or "this file" instead of its name).
- Running a command as the superuser, binding to every network address, or reading environment variables inside
  inline workflow scripts (put scripts in `tools/` and call them).
- Asking to switch on a model's developer mode, or to keep something from the user (phrased either way).
- A per-process path under the proc filesystem written out literally.
- Zero-width or other invisible characters.
- Binaries (compiled executables, wasm), symlinks that leave the repository, a `package.json` at the root
  (development tools live in `tools/npm/package.json`).

The scanner rules live in Hermes (`tools/skills_guard.py`, `tools/plugin_guard.py`). When `check.py scan` fails it
prints each high or critical finding with its file and line. Medium and low findings are notes and are fine.

## Writing about a trigger

Docs that warn about a trigger phrase trip the scanner if they quote it. Describe it instead, as this page does.
