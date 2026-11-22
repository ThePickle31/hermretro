# The sandbox

`python tools/dev studio up` runs the real plugin in a private Hermes and shows its page in a headless browser: the
way to look at the page as users see it, with real games, real turns and real builds, without touching the real
Hermes home and without opening a window. Everything is in `.dev/sandbox/` of the checkout:

- `hermes/` is the sandbox's Hermes home (`HERMES_HOME`): its default profile and a `hermretro` profile made by the
  plugin's own setup (`studio_profile.finish`), both loading this checkout through a link. The toolchain is the real
  Hermes home's, read through a link (`hermes/hermretro/.cache/toolchain`); no sign-in or key is copied, and `up`
  refuses to start while Hermes's source checkout has a `.env` (Hermes would load it whatever `HERMES_HOME` says).
- The model is `tools/dev/script_model.py`, an OpenAI-compatible endpoint that plays the scripts in
  `tools/dev/scripts/` (format in its docstring): each names the words that start it and the steps it plays, with
  real tool calls, so the page sees real turns, real projects and real builds for free.
- The gateway (`hermes gateway run`) serves Hermes's Webapp on its own port; `tools/dev/studio_browser.mjs` signs a
  headless Chromium in with `hermes webapp --no-open`, switches the page on and opens HermRetro from the sidebar,
  in dark mode at 1440×900.
- The processes get only `PATH`, `HOME`, the locale and the runtime folder from the caller's environment: no keys,
  and no display, so nothing they start can open a window. Each is stopped only while its pid, start time and command
  line are still the ones recorded (`processes.json`); the plugin's broker is the one whose command line names the
  sandbox's broker folder, and its engine workers exit with it.
- It stays on current code. Every `up` (and so every `load`, `scenario` and `mockup`) fetches `origin/dev` and
  fast-forwards this checkout when it is the `dev` branch with nothing of its own (a feature branch behind dev gets a
  `FIX: git rebase origin/dev` line instead), rebuilds Hermes's Webapp when Hermes changed (a second when it did
  not), and restarts the gateway when the backend or Hermes changed since it started. The snapshots record what made
  them (`snapshots/seed.json`: the backend, Hermes and `tools/dev/scripts/`); a `load` from older code seeds again
  first. Page changes need none of this: the page reloads.

| `studio` verb | What it does |
|---|---|
| `up` | Creates the sandbox the first time (and builds Hermes's Webapp once), then starts what is not running |
| `down` / `reset` | Stops everything / stops it and removes `.dev/sandbox/` |
| `status` | What runs, the saved snapshots and the scenarios |
| `reload` | After a backend change: re-imports the plugin in the sandbox's gateway and reopens the page (page changes load by themselves once `node tools/bundle/bundle.mjs` or `watch` rebuilt them) |
| `seed` | A fresh sandbox, then the seed messages through the real page and engine, saving snapshots as it goes |
| `save NAME` / `load NAME` | Packs or restores the Hermes home and the browser's storage (`snapshots/NAME.tar.gz`) |
| `scenario NAME` | Loads a state: `new-game`, `first-build`, `builds` (an art edit and a failed build), `working` (a turn held open until `studio release`), `question` (a question card) |

`python tools/dev ui VERB` drives the page and prints what it made: `shot [NAME] [--full] [--of TARGET]` (a PNG in
`.dev/sandbox/shots/`), `text [TARGET]` (the accessibility outline), `go build|setup|games|emulator`,
`click TARGET`, `type TEXT [--into TARGET] [--submit]` (default: the message box), `say TEXT [--no-wait]` (sends from the Build page's box and
waits for the turn), `wait [TEXT] [--ms N]`, `idle`, `eval JS`, `resize W [H]`, `theme dark|light`, `reload`,
`errors` (the page's console errors since the last call) and `url`. A TARGET is a CSS selector, a button's name or
text on the page. Logs: `.dev/sandbox/logs/`, and `.dev/sandbox/model.jsonl` (every scripted reply and the tools Hermes offered).

## Mockups

`python tools/dev mockup <round folder>` shoots a round of mockups inside the sandbox, so they show the real Hermes
shell, real games and real conversations, at real widths. A round folder (outside this repository, for example
`~/projects/chromatic-studio-mockups/<round>/`) holds:

- `round.json`: `replaces` (the page module the mockups stand in for, such as `page/pages/build/build-page.js`),
  `exports` (its components, such as `["BuildPage"]`), and the defaults for `states` (sandbox scenarios), `widths`
  and `themes`.
- `mockups/<id>.jsx`: each exports `title` and the same components. It may import anything of the page through
  `#sdk`, `#app/`, `#pages/` and `#shared/`, and today's version of the module it replaces as `#original` (to wrap
  it or reuse it). The id's part before the first dash is its label (`b2-dock.jsx` is B2).

`tools/dev/mockup_build.mjs` builds the whole page with that module replaced by a switch (plugin storage key `mockup`,
changed live by a `hermretro-mockup` window event). Hermes copies a linked plugin's page again whenever it differs
from the source, so the command serves it from an overlay (`.dev/sandbox/mockup-plugin/`: links to this checkout,
except `desktop/plugin.js`) that the sandbox's default profile links to while it runs; the checkout's own files are
never changed. Then for each state, mockup (and today's page, `Now`), theme and width it writes
`<round>/shots/<id>.<state>.<width>.<theme>.png`
and finally `<round>/gallery.html` (one file with every picture: filters, and a viewer that pages with the arrow
keys, zooms with the wheel and pans by dragging). The sandbox's real page is put back at the end. `--states`,
`--widths`, `--themes` and `--only` narrow a run.
