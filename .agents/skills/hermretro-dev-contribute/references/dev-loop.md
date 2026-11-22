# The development loop

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
