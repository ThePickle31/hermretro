// Running the attract level inside the New Game area: measuring the form's `data-plat` boxes, building the world
// around them, the fixed 60 Hz loop, following the theme and rebuilding when the area, a box or the form's scroll
// position changes. Plain DOM code with the browser functions passed in (`env`), so tests drive it with a fake
// world and a fake clock.

export const SCALE = 2 // screen pixels per game pixel
const STEP = 1000 / 60 // the game runs at a fixed 60 steps a second
const LOOK_EVERY = 30 // animation frames between theme checks

/** The page's own background under `el` (the first ancestor that paints one): { css, rgb: [r, g, b] 0-255 }.
 *  Browsers report it as rgb()/rgba() or, for a color-mix() theme, as color(srgb r g b) with 0-1 channels. */
export function backgroundOf(el, getStyle) {
  for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
    const css = getStyle(node).backgroundColor, nums = (css.match(/[\d.]+/g) || []).map(Number)
    const unit = css.startsWith('color(') ? 255 : 1
    if (nums.length >= 3 && (nums.length < 4 || nums[3] > 0.5)) return { css, rgb: nums.slice(0, 3).map(v => v * unit) }
  }
  return { css: 'rgb(16 18 24)', rgb: [16, 18, 24] }
}
export const skyFor = ([r, g, b]) => (0.2126 * r + 0.7152 * g + 0.0722 * b > 140 ? 'day' : 'night')

/** The boxes inside `root` marked `data-plat`, in game pixels measured from the canvas's top-left corner. */
export function platforms(root, canvasEl) {
  const origin = canvasEl.getBoundingClientRect(), out = []
  for (const el of root.querySelectorAll('[data-plat]')) {
    const r = el.getBoundingClientRect()
    if (r.width < 4) continue
    const x = Math.floor((r.left - origin.left) / SCALE), y = Math.round((r.top - origin.top) / SCALE)
    const w = Math.ceil((r.right - origin.left) / SCALE) - x, h = Math.ceil((r.bottom - origin.top) / SCALE) - y
    if (y + h < 0 || y > origin.height / SCALE) continue
    out.push({ x, y, w, h, kind: el.dataset.plat })
  }
  return out
}

/** Start the level in `host` (the positioned New Game area) on `canvasEl`, with the overlay `layer`.
 *  `makeWorld(seed)` returns a world (build, attach, setPalette, step, render, typingCoin). Returns a stop function. */
export function runAttract({ host, layer, canvasEl, makeWorld, env, seed }) {
  const { raf, caf, setTimer, clearTimer, getStyle, observe, motion, isHidden } = env
  let world = null, sky = '', bgCss = '', frameId = 0, timer = 0, last = 0, acc = 0, typed = 0, ticks = 0, alive = true
  const still = () => !!motion?.matches

  // the theme: the palette and the spotlight colour follow the page background; true when either changed
  const look = () => {
    const bg = backgroundOf(host, getStyle), name = skyFor(bg.rgb), changed = name !== sky || bg.css !== bgCss
    layer.style.setProperty('--cs-at-bg', bg.css)
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
    const keep = world ? { score: world.score, coinsGot: world.coinsGot } : null
    look()
    world = makeWorld(seed)
    world.build(W, H, platforms(host, canvasEl))
    if (keep) Object.assign(world, keep)
    world.attach(canvasEl, sky)
    const composer = host.querySelector('[data-plat="composer"]')?.getBoundingClientRect()
    if (composer) {
      layer.style.setProperty('--cs-at-sx', `${Math.round(composer.left + composer.width / 2 - area.left)}px`)
      layer.style.setProperty('--cs-at-sy', `${Math.round(composer.top + composer.height / 2 - area.top)}px`)
    }
    // reduce motion: one still frame, a moment into the game so everything has settled
    if (still()) for (let i = 0; i < 90; i++) world.step()
    world.render()
  }
  const later = () => { if (!timer) timer = setTimer(build, 150) }

  const frame = now => {
    frameId = raf(frame)
    if (!world || isHidden()) { last = now; return }
    // the theme is checked in both modes, so a still frame repaints in the new colours too
    if (++ticks % LOOK_EVERY === 0 && look() && still()) world.render()
    if (still()) { last = now; return }
    acc += Math.min(100, now - (last || now)); last = now
    let n = 0
    while (acc >= STEP && n < 4) { world.step(); acc -= STEP; n++ }
    if (n) world.render()
  }

  const unobserve = observe([host, ...host.querySelectorAll('[data-plat]')], later)
  // the form scrolls inside the area (short windows, a tall idea): its boxes move without changing size
  const onScroll = () => later()
  const onInput = event => { if (event.target?.tagName === 'TEXTAREA' && world && ++typed % 4 === 0) world.typingCoin() }
  host.addEventListener('scroll', onScroll, true)
  host.addEventListener('input', onInput)
  motion?.addEventListener?.('change', later)
  build()
  frameId = raf(frame)

  return () => {
    alive = false
    caf(frameId)
    clearTimer(timer)
    unobserve()
    host.removeEventListener('scroll', onScroll, true)
    host.removeEventListener('input', onInput)
    motion?.removeEventListener?.('change', later)
  }
}
