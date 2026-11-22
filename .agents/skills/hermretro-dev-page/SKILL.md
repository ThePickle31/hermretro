---
name: hermretro-dev-page
description: Working on the Hermes Desktop page (page/) and the player frame. Use when changing a page, tab, event, slot, the Build page, the emulator, or the page's build and boundaries.
---

# The page

`page/` is the source; `node tools/bundle/bundle.mjs` builds `desktop/plugin.js` and `player/frame-shim.js`, which
are committed and never edited by hand. Each page's own `README.md` (in `page/pages/<page>/`) says what it shows,
its events, slots and tests.

| Read | For |
|---|---|
| [references/source.md](references/source.md) | the folders, import aliases and boundaries, file and style rules, size limits, what to verify |
| [references/adding.md](references/adding.md) | adding a page, tab, event, slot or contribution, calling the backend |
| [references/pages.md](references/pages.md) | the pages and the approved designs: Setup, Games, Emulator |
| [references/build-page.md](references/build-page.md) | the Build page: one game, one conversation, its RPCs and its parts |
| [references/player.md](references/player.md) | the emulator beside the chat, the library and player RPCs, the player server, page and frame messages |
