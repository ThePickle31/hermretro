---
name: hermretro-dev-release
description: Releasing hermretro. Use only when the owner asks for a release, and only as the maintainer.
---

# Releasing

`python tools/release.py`, run again after each step it stops at (exit 2 means waiting): the version pull request
when `dev` still says the last released version, CI on `dev`'s head, `main` fast-forwarded to it, the tag and a
draft release with generated notes. Read the draft, then `python tools/release.py --publish vX.Y.Z` (published
releases cannot change). `--rc` makes a release candidate and leaves `main` alone. Versions are patch-only (`0.0.N`);
the version lives only in `plugin.yaml`.

Before publishing, run [references/release-checklist.md](references/release-checklist.md) on a real machine (a
MacBook at least) and put its result in the draft's notes, or say there that it was not run.
