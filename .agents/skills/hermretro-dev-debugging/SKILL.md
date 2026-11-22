---
name: hermretro-dev-debugging
description: Finding out why hermretro misbehaves. Use when a build hangs, the broker seems stuck, the player stays black, a page action fails, tools are missing, or you need a log, trace or HERMRETRO_* variable.
---

# Debugging

[references/debugging.md](references/debugging.md): where each log and trace is, player captures, calling a page
RPC by hand, a hung build or stuck broker step by step, logging rules, common symptoms and their fixes, every
`HERMRETRO_*` variable, stopping the broker by hand.

Quick looks: `python tools/debug/broker_stats.py` (what the broker holds, read-only) and
`node tools/debug/gateway_rpc.mjs hermretro plugin.hermretro.status` (one page RPC).
