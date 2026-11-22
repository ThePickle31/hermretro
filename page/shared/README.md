# shared: what every page and the shell use

**Holds:** `ui/` (small components: page head, buttons, text, links, glyphs, time and elapsed timers, the app background behind an element),
`styles/` (the design tokens, the base and narrow-pane rules; `app/style.js` composes the stylesheet), `art/`
(the PNGs, embedded as data URLs; `art/providers/` the official provider logos the model picker shows, PNG and SVG) and `player/` (the frame layer every player surface uses: the bridge, the
protocol with the frame, values from the frame checked before use, the live-player lock).

**Tabs, events, slots:** none. shared/ is the bottom layer: it imports only `#sdk` and `#shared/`, never
`#app/` or `#pages/` (`tools/bundle/lint-rules.mjs`). Code that needs the backend or a chat belongs in
`app/` (page-wide) or in the page that uses it.

**Tests:** `tests/page/build-player.test.mjs` (frame values, protocol, targets); the page tests cover the rest
through the bundle.

## Adding a tab

Tabs belong to a page: see "Adding a tab here" in that page's README.md.
