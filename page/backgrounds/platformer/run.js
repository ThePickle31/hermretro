// Running the platformer in the page area (`host`): building the world for the area's size, the fixed 60 Hz loop,
// following the theme and rebuilding when the area changes size (the same size keeps the world going, so a page
// switch or a return to the page does not restart it). The page in front plays no part in the level; the one thing
// read from it is where the ground must stay flat (`data-at-flat`: the New Game shelf), and the level tells the page
// where its ground is (`--cs-at-ground`, px from the bottom) and its colour (`--cs-at-bg`). Plain DOM code with the
// browser functions passed in (`env`), so tests drive it with a fake world and a fake clock.

import { backgroundOf } from '#shared/ui/background.js'

export const SCALE = 2 // screen pixels per game pixel
const STEP = 1000 / 60 // the game runs at a fixed 60 steps a second
const LOOK_EVERY = 30 // animation frames between theme checks

export const skyFor = ([r, g, b]) => (0.2126 * r + 0.7152 * g + 0.0722 * b > 140 ? 'day' : 'night')

/** The horizontal spans of the elements in `root` marked `data-at-flat`, in game pixels from the canvas's left. */
export function flatSpans(root, canvasEl) {
  const origin = canvasEl.getBoundingClientRect(), out = []
  for (const el of root.querySelectorAll('[data-at-flat]')) {
    const r = el.getBoundingClientRect()
    if (r.width >= 4) out.push([Math.floor((r.left - origin.left) / SCALE), Math.ceil((r.right - origin.left) / SCALE)])
  }
  return out
}

/** Start the level in `host` (the positioned New Game area) on `canvasEl`.
 *  `makeWorld(seed)` returns a world (build, attach, setPalette, step, render). Returns a stop function. */
export function runAttract({ host, canvasEl, makeWorld, env, seed }) {
  const { raf, caf, setTimer, clearTimer, getStyle, observe, motion, isHidden } = env
  let world = null, flat = '[]', sky = '', bgCss = '', frameId = 0, timer = 0, last = 0, acc = 0, ticks = 0, alive = true
  const still = () => !!motion?.matches

  // the theme: the palette and `--cs-at-bg` (the frosted glass) follow the page background; true when either changed
  const look = () => {
    const bg = backgroundOf(host, getStyle), name = skyFor(bg.rgb), changed = name !== sky || bg.css !== bgCss
    // on the area, so the layer and the form in front both inherit it
    host.style.setProperty('--cs-at-bg', bg.css)
    if (world && name !== sky) world.setPalette(name)
    sky = name; bgCss = bg.css
    return changed
  }
  const build = () => {
    timer = 0
    if (!alive) return
    const area = host.getBoundingClientRect()
    if (area.width < 40 || area.height < 40) return
    const W = Math.ceil(area.width / SCALE), H = Math.ceil(area.height / SCALE)
    canvasEl.style.width = `${W * SCALE}px`
    canvasEl.style.height = `${H * SCALE}px`
    const spans = flatSpans(host, canvasEl)
    // the same area and the same flat ground: the level she is playing still fits
    if (world && world.W === W && world.H === H && JSON.stringify(spans) === flat) return
    const keep = world ? { score: world.score, coinsGot: world.coinsGot } : null
    look()
    flat = JSON.stringify(spans)
    world = makeWorld(seed)
    world.build(W, H, { flat: spans })
    // where the ground's top is, for the page: the shelf's cartridges stand on it
    if (world.L) host.style.setProperty('--cs-at-ground', `${(H - world.L.groundY) * SCALE}px`)
    if (keep) Object.assign(world, keep)
    world.attach(canvasEl, sky)
    // reduce motion: one still frame, a moment into the game so everything has settled
    if (still()) for (let i = 0; i < 90; i++) world.step()
    world.render()
  }
  const later = () => { if (!timer) timer = setTimer(build, 150) }

  const frame = now => {
    frameId = raf(frame)
    if (!world || isHidden()) { last = now; return }
    // the theme is checked in both modes, so a still frame repaints in the new colours too
    // and whether the flat ground moved (the shelf appeared, or gained or lost a cartridge)
    if (++ticks % LOOK_EVERY === 0) {
      if (look() && still()) world.render()
      if (JSON.stringify(flatSpans(host, canvasEl)) !== flat) later()
    }
    if (still()) { last = now; return }
    acc += Math.min(100, now - (last || now)); last = now
    let n = 0
    while (acc >= STEP && n < 4) { world.step(); acc -= STEP; n++ }
    if (n) world.render()
  }

  const unobserve = observe([host], later)
  motion?.addEventListener?.('change', later)
  build()
  frameId = raf(frame)

  return () => {
    alive = false
    caf(frameId)
    clearTimer(timer)
    unobserve()
    host.style.removeProperty('--cs-at-bg')
    host.style.removeProperty('--cs-at-ground')
    motion?.removeEventListener?.('change', later)
  }
}
