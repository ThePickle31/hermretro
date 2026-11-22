---
name: hermretro-dev-testing
description: hermretro's tests, checks and CI, and Hermes's install scanner. Use when writing, moving or running tests, reading a CI failure, or when python tools/check.py scan does not say safe.
---

# Testing

`python tools/check.py` runs the fast checks; every failure ends with a `FIX:` line. Read CI with
`gh pr checks <n>` and `gh run view <run> --log-failed`.

- [references/testing.md](references/testing.md): every check and what it proves, CI tiers, the Hermes names check,
  the clean install and update checks, where tests live, adding, moving and splitting tests, the rules for tests,
  looking at the page.
- [references/install-scanner.md](references/install-scanner.md): what trips the scanner every install runs, and how
  to write about a trigger without quoting it.
