---
name: hermretro-dev-architecture
description: How hermretro's backend fits together and where each piece goes. Use when adding or changing a backend feature, RPC, tool, hook, event or stored state, or when you need an RPC's exact shape.
---

# Architecture

- [references/architecture.md](references/architecture.md): the two halves and the broker, the full folder Map,
  each feature's declarations and front door, **"Adding things"** (every place an RPC, tool, hook, event, state or
  feature touches), splitting a module, where state lives, what runs where.
- [references/contract.md](references/contract.md): names, events between features, every RPC's params and result,
  hardware, the build card, build history, the game card and the game object. A new RPC or tool adds its section here.

Features reach each other only through front doors and events; `tests/repo/test_boundaries.py` enforces it.
Modules the broker imports stay standard library only.
