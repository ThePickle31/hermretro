---
name: hermretro-dev-contribute
description: Making a change to hermretro, from branch to open pull request. Use for any code, page or docs change to this repository.
---

# Contributing a change

1. **Branch from `dev`.** A contributor forks, clones the fork and branches from `dev`; the maintainer makes a
   worktree beside the checkout: `git worktree add ../hermretro-wt/<topic> -b <type>/<topic> origin/dev`. Types:
   `feat`, `fix`, `docs`, `chore`. Then `python tools/dev setup` in it.
2. **Try it in Hermes.** `python tools/dev live` makes Hermes load this checkout; `reload` after a backend change;
   `watch` in the background for page work (it rebuilds on save and serves the live preview). Look at the result
   yourself: the sandbox (`hermretro-dev-sandbox`), the live preview or Hermes Desktop. `live main` when done.
   Everything about this loop: [references/dev-loop.md](references/dev-loop.md).
3. **Check.** `python tools/check.py fix`, commit, `python tools/check.py`. A change to `page/` also commits the
   generated files `node tools/bundle/bundle.mjs` rewrote.
4. **Open the pull request** into `dev`. Title: `type(scope): what it does`, at most 72 characters; it becomes the
   squash commit and the release-note line. Body: the template's sections. No agent co-author or "generated with"
   lines. One concern per pull request.

A contributor stops here: the maintainer reviews and merges (`hermretro-dev-maintain`). Answer review comments with
new commits on the same branch; first-time contributors' CI waits for the maintainer's approval.

`profile/` holds templates copied into the `hermretro` profile when setup makes it; an existing profile keeps its
files, so try a template change in a throwaway Hermes home (`HERMES_HOME=<temp folder>`).
