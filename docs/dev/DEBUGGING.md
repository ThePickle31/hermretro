# Debugging

## Where to look

| What | Where |
|---|---|
| What the broker did (every dispatch, denial, start and stop) | `~/.hermes/hermretro/run/trace.jsonl` (rotates at 5 MB) |
| Why the broker crashed | `~/.hermes/hermretro/run/broker.stderr.log` |
| The last toolchain install | `~/.hermes/hermretro/.cache/toolchain/last-run.json` |
| Hardware operations (read only) | `~/.codex-gb-studio/chromatic/<id>/operation.json` (the engine's journal) |
| What a tool returned in a chat | the profile's `state.db`, table `messages` (open read-only) |
| What the page's RPC answers | `node tools/debug/gateway_rpc.mjs <profile> plugin.hermretro.status` (never prints the attach ticket) |

When the user's home is long, the run folder may be the short fallback `/tmp/hermretro-<uid>` (socket paths are
capped at 104 bytes on macOS).

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
