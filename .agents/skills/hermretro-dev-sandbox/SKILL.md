---
name: hermretro-dev-sandbox
description: Seeing hermretro's page as users do, in a private headless Hermes. Use to look at, screenshot or drive the page, load a saved state, or shoot mockups.
---

# The sandbox

`python tools/dev studio up`, then `python tools/dev ui shot NAME`. It runs this checkout in its own Hermes home
under `.dev/sandbox/`, with a scripted model and a headless browser: it never touches the real Hermes home and never
opens a window. `studio scenario NAME` loads a saved state; `ui go|click|say|text` drive the page; `mockup FOLDER`
shoots a round of mockups and its gallery.

Everything: [references/sandbox.md](references/sandbox.md).
