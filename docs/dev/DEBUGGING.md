# Debugging

## The development loop

`python tools/dev <command>` runs the plugin from a checkout in the Hermes on this machine, with no restarts:

| Command | What it does |
|---|---|
| `setup` | Makes the checkout ready: the pinned npm tools and ruff (only what is missing) |
| `status` | Which checkout each profile loads, and whether a gateway runs |
| `live [PATH\|main]` | Points every profile that links hermretro at this checkout (or PATH, or the main one), reloads it and updates Hermes Desktop's copy of the page. One checkout is live at a time: all linked profiles move together, since two backends would fight over the one broker |
| `reload` | Re-imports the plugin in the running gateway (its `reload-plugins` control verb, per profile): RPCs answer from the new code at once; tools and the prompt apply from the next chat. The broker replaces itself once idle. Run it after a backend change |
| `rpc METHOD [JSON]` | One gateway RPC (`tools/debug/gateway_rpc.mjs`); a bare name is `plugin.hermretro.<name>`, `--profile` picks the profile (default `hermretro`) |
| `watch` | Rebuilds the page on every save, keeps Hermes Desktop's copy current when this checkout is live, and serves the browser preview on a free loopback port (`--port`), printing its live address |

The live preview (`?live=<token>`, the address `watch` prints) draws the page with Desktop's stylesheet and answers
its `plugin.hermretro.*` RPCs and its events from the real gateway, in the `hermretro` profile, through
`tools/dev/preview_server.mjs`; it reloads itself after each rebuild and keeps the page it was on. Without `live` the same page shows the canned scenarios. Chats in it reach the
real gateway, but the app's own chat surface is not there: try Build chats in Hermes Desktop.

A gateway restart (`hermes gateway restart`) is needed only when a reload is not enough: a new Hermes dependency, or
routes Hermes reads at start.

## The sandbox

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

### Mockups

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

## Where to look

| What | Where |
|---|---|
| What the broker did (every dispatch, denial, start and stop) | `~/.hermes/hermretro/run/trace.jsonl` (rotates at 5 MB) |
| Why the broker crashed | `~/.hermes/hermretro/run/broker.stderr.log` |
| The last toolchain install | `~/.hermes/hermretro/.cache/toolchain/last-run.json` |
| Hardware operations (read only) | `~/.codex-gb-studio/chromatic/<id>/operation.json` (the engine's journal) |
| What a tool returned in a chat | the profile's `state.db`, table `messages` (open read-only) |
| What the broker holds now (lanes, worker pids and their processes, leases) | `python tools/debug/broker_stats.py` (read-only, never starts one; exits 2 when no broker runs, 3 when one does not answer) |
| A screenshot or recording from the player | `<project>/captures/` (the demo's: `~/.hermes/hermretro/library/captures/demo`), each with a `.json` sidecar: "Player captures" below |
| What the page's RPC answers | `node tools/debug/gateway_rpc.mjs <profile> plugin.hermretro.status` (never prints the attach ticket) |

When the user's home is long, the run folder may be the short fallback `/tmp/hermretro-<uid>` (socket paths are
capped at 104 bytes on macOS).

## Player captures

`save_capture` in `backend/player/server.py` writes each screenshot or recording as `<project>/captures/<stamp>-<kind>.<png|webm|mp4>`:
`<stamp>` is the UTC save time, `YYYY-MM-DDTHH-MM-SS-mmmZ` (`_stamp`), `<kind>` is `screenshot`, `video` or
`annotation` (a page-sent game screen), and a name already taken gets `-2`, `-3`… (`_free_name`). Beside it,
`<file>.json` holds `id`, `kind`, `media` (the file name), `mimeType`, `bytes`, `sha256`, `createdAt`, `game` (the game id),
`romSha256` and `sourceRevision` (the build it came from; player saves only) and `metadata` (what the engine sent, null
for an `annotation`). Which RPCs read and write them: [backend/library/README.md, "Captures"](../../backend/library/README.md#captures).

## Calling a page RPC by hand

`node tools/debug/gateway_rpc.mjs <profile|default> <method> [params-json]` calls one gateway JSON-RPC method the
way the page does (`hermes [-p <profile>] gateway attach --json`, then one request over its WebSocket), e.g.
`node tools/debug/gateway_rpc.mjs hermretro plugin.hermretro.games`. It needs Node 22 or newer and a running gateway
for that profile: `hermes -p <profile> gateway ensure` starts a local one without installing a service (`hermes
gateway start` only starts an installed systemd/launchd service). `params-json` defaults to `{}`. It prints one JSON
line, never the attach ticket: `{ profile, method, result, error }` cut to 1800 characters (all of it with
`GATEWAY_RPC_FULL=1`), exit 0; or exit 1 with `{ profile, error: "no gateway: <what hermes said>" }`,
`{ profile, error: "timeout" }` (no answer in 60 s), `{ profile, error: "socket error ..." }` or
`{ profile, closed, reason }`.

## A build hangs or the broker seems stuck

1. `python tools/debug/broker_stats.py` prints the broker's `stats` answer (each lane's `engine_pid`, `alive`,
   `inflight` calls, writer leases) and, for each live worker, the worker and every process descended from it,
   each with its pid, ppid, pgid, elapsed time and command line (`engine_processes`). They come from one
   `ps -A -o pid=,ppid=,pgid=,etime=,command=` snapshot (the same on Linux and macOS) by following parent pids,
   so the ROM and web compilers, which the engine starts in sessions of their own, show there too: a hung `make`
   or emulator shows with its own pgid. Add `--activity hermretro <chat id>` for the page's view of one chat (its
   current tool and recent events). It sends only read-only operations and waits at most `--timeout` seconds
   (default 5) for the connect, the handshake and each answer. Exit codes: 0 printed, 2 no broker runs (no
   socket, a stale one, or the handshake was refused), 3 a broker accepted the connection but did not answer in
   time or closed it.
2. The trace (`trace.jsonl` in the run folder, above) has one JSON record per line with `t` and
   `broker_generation`: `dispatch` when a call goes to a worker, `outcome_unknown` when it timed out,
   `denied`, `broker_error`, `worker_closed`, `broker_started`, `broker_stopped`, `broker_idle_exit` and others
   (`grep -o 'trace(event="[a-z_]*"' backend/broker/*.py` lists them all).
3. The broker's own stderr goes to `broker.stderr.log` in the same run folder (`backend/broker/client.py`
   `spawn_broker`; kept to 5 MB, the previous one as `broker.stderr.log.1`).
4. An engine worker's stderr is **not on disk**: the broker reads it into memory
   (`EngineProcess.stderr_tail` in `backend/broker/engine.py`, the last 400 lines) and only its last 20 lines
   reach an `EngineError` when the worker has died. To see more, run the engine by hand.
5. Timeouts: a tool call waits `DEFAULT_CALL_TIMEOUT` (900 s, `backend/broker/lane.py`) unless the request sets
   `timeout`; a worker's start waits 60 s for its `initialize` answer and other requests 60 s by default
   (`backend/broker/engine.py`). A timed-out call is reported as outcome unknown (the engine may still finish
   it), never as not done. The client side of the socket sets no timeout of its own (only `broker_stats.py` does).

## Logging

Each backend module logs through `logger = logging.getLogger(__name__)` and starts every message with
`hermretro:` (`logger.debug("hermretro: no chat project for the build snapshot", exc_info=True)`), so its lines
are found with `grep hermretro:`. Hermes loads the plugin as `hermes_plugins.<name>`, so a gateway records INFO
and above in the profile's `logs/gateway.log` and `logs/agent.log` (its `logging.level`, INFO by default), and
WARNING and above also in `logs/errors.log`; DEBUG is recorded nowhere by default. So: `debug` for an expected,
handled failure (a missing optional file), `info` for something the user did that is worth a line, `warning` for
something wrong that hermretro worked around, and never a token, ticket or file content. The broker writes its own
trace (above), not these logs.

## Common symptoms

- **Setup says "The hermretro broker did not start", and the trace shows `broker_started`/`broker_stopped` pairs
  about twice a second.** The gateway loaded an older backend than the one on disk and keeps retiring new brokers.
  Restart the gateway (`hermes gateway restart`, from a terminal outside Hermes). The toolchain is fine.
- **A page action fails with -32601.** The gateway has not loaded the new RPC yet: restart it (Python changes
  need a gateway restart; page changes need an app reload).
- **No `chromatic_*` tools in a chat.** They exist only in the `hermretro` profile (or everywhere with
  `HERMRETRO_EVERY_PROFILE=1` in the gateway's environment). `hermes plugins doctor` cannot show them: it
  registers the plugin in a temporary home. Use `hermes -p hermretro tools list`.
- **"hermretro is still running an older session for a game in a chat."** A broker from older code is kept
  alive by a live game; it retires when that chat's game closes. A forced restart kills open players.
- **The player stays black.** Open the app's developer console: errors inside the player frame arrive as
  `[Chromatic player] <text>` warnings (`page/shared/player/bridge.js`; the frame forwards its `console.error`,
  uncaught errors and rejections, `page/frame/sandbox.js`). The stage (`page/app/player/stage.js`) shows "Reading
  your games…" before the library answers, "Starting the player for <game>…" while the `player` RPC runs, "The
  player could not start" with Refresh above an empty stage when that RPC fails (with -32601: reload the plugin),
  and "The player could not start" with Build it in chat when the game has no web export. Then check the game's
  `webExport` and `web.sha256` in the `games` answer (`node tools/debug/gateway_rpc.mjs hermretro
  plugin.hermretro.games`) against the `romSha256` the `player` RPC returns: when they differ, the bar shows
  "Hermes rebuilt <game> · Load the new build" (`page/pages/emulator/emulator-bar.js`), which reloads the frame.
- **The emulator lease is stuck** (`recordingAccessFailure`). The broker clears it only when its owner is dead
  (`backend/broker/leases.py`); the trace says so.

## Environment variables

For development, tests and unusual setups; users need none of them.

| Variable | What it does |
|---|---|
| `HERMRETRO_HOME` | Moves the whole hermretro folder (default `~/.hermes/hermretro`) |
| `HERMRETRO_GAMES_DIR` | Moves only the games folder |
| `HERMRETRO_LIBRARY_DIR` | Moves only the library (the Games shelf) |
| `HERMRETRO_RUNTIME_DIR` | Moves the broker's run folder (socket, token, lock, trace) |
| `HERMRETRO_DEPS_ROOT` | Uses another downloaded-tools folder (`.cache`); "Remove downloaded tools" then refuses |
| `HERMRETRO_NODE` | The Node.js executable to use, tried first |
| `HERMRETRO_EVERY_PROFILE` | `1`: register the agent side in every profile, not only `hermretro` (development) |
| `HERMRETRO_BROKER_IDLE_SECONDS` | How long an idle broker stays (default 600) |
| `HERMRETRO_LANE_IDLE_SECONDS` | How long an idle chat's engine worker stays (default 1800) |
| `HERMRETRO_WRITER_HANDOFF_SECONDS` | How long a chat keeps a project's writer lease while idle (default 45) |

`tests/repo/test_lockstep.py` checks that every `HERMRETRO_*` variable the backend reads is in this table.

## Stopping the broker by hand

Send `{"op": "shutdown", "force": true}` through `backend.broker.client.ensure_broker()` (or stop the process). Workers
exit when the broker's pipe closes. Open emulator tabs stop working until the next start.
