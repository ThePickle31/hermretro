---
name: hermretro-dev-backgrounds
description: Making a background that hermretro's pages draw behind them (a game, a scene, an animation, anything), and choosing which page shows which. Use to add, change or remove a background in page/backgrounds/.
---

# Backgrounds

A background is one folder, `page/backgrounds/<id>/`, whose `index.js` exports its descriptor. It can be anything
drawn in a layer behind the page: the shipped `platformer/` is a small game, but a gradient, particles or a looping
scene work the same way.

## Make one

1. **The folder** `page/backgrounds/<id>/` (lower-case letters, digits and dashes). It imports only its own files and
   `#shared/` (no React, no pages, no app).
2. **`index.js`**, exporting one descriptor named after it:

```js
import { STARFIELD_CSS } from './starfield.css.js'

export const STARFIELD = {
  id: 'starfield',
  css: [STARFIELD_CSS],
  // Draw into `layer` (an empty div filling the page area). Return the function that undoes everything.
  start({ host, layer, env }) {
    const canvas = layer.ownerDocument.createElement('canvas')
    layer.append(canvas)
    let frame = 0
    const draw = time => {
      frame = env.raf(draw)
      if (env.isHidden()) return // its page is not shown (or the window is hidden): do nothing, keep the state
      // ...size the canvas to layer.clientWidth/clientHeight and paint...
    }
    draw(0) // the first frame now, before the page paints: it never fades in late
    return () => {
      env.caf(frame)
      canvas.remove()
    }
  }
}
```

   - `layer`: its own `div.cs-bg[data-bg=<id>]`, behind everything in the page area, without pointer events.
   - `host`: the page area (`.cs-pad`). Read the page from it (sizes, `data-*` marks) or set CSS variables on it
     for the page to use (the platformer sets `--cs-at-bg` and `--cs-at-ground`).
   - `env`: the browser functions (`raf`, `caf`, `setTimer`, `clearTimer`, `getStyle`, `observe(elements,
     onResize)`, `motion`, the reduced-motion query, and `isHidden()`). Use them instead of globals, so the
     background can be tested with fakes.
   - `start` runs once. When a page without this background is shown, the layer is hidden (`isHidden()` turns true)
     but the background keeps its state; when a page asks for it again it carries on. Stop work while hidden.
   - Under reduced motion (`env.motion.matches`), draw one still frame.
3. **Styles** in `<name>.css.js`, scoped to `.cs-bg[data-bg=<id>]`, listed in `css`. Colours come from the theme
   (`var(--ui-*)`, or the page colour read with `backgroundOf` from `#shared/ui/background.js`), so light and dark
   both work.
4. **One line** in `page/backgrounds/index.js`: import it and add it to `BACKGROUNDS`.

## Show it on a page

Render `jsx(Background, { id: '<id>' })` from `#app/background.js` anywhere in the page's tree (or only in the state
that wants it: Build renders it in New Game). Changing a page's background is changing that id. Pages that ask for
the same id share one running background; switching between them never restarts it. Content above it should be
transparent where the background should show.

## Check it

`node tools/bundle/bundle.mjs`, then `python tools/check.py` (the lint enforces the folder's imports;
`tests/page/background-layer.test.mjs` checks every descriptor). Add a test of your own for anything with logic,
driving `start` with a fake `env` as `tests/page/platformer-run.test.mjs` does. Then look at it in Hermes, in both
themes, with reduced motion on and off. `page/backgrounds/README.md` lists what is there.
