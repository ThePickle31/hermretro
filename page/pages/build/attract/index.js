// The New Game attract mode: a GBC-style platformer drawn behind the New Game form, where the Nous Girl plays one
// fixed level by herself and the form's boxes are platforms in it. Dimmed to half strength with a pool of the page's
// own colour behind the composer, so the game stays in the background ("Spotlight"). Purely decorative: no clicks,
// no keys, hidden from screen readers.
import { jsx, jsxs, useEffect, useRef } from '#sdk'
import { World } from './world.js'

const SCALE = 2 // screen pixels per game pixel
const STEP = 1000 / 60 // the game runs at a fixed 60 steps a second

/** Whether this browser can draw on a 2D canvas (the page tests' jsdom cannot). */
const canDraw = () => typeof CanvasRenderingContext2D === 'function'

/** The page's own background under `el` (the first ancestor that paints one): { css, rgb: [r, g, b] 0-255 }.
 *  Browsers report it as rgb()/rgba() or, for a color-mix() theme, as color(srgb r g b) with 0-1 channels. */
function backgroundOf(el) {
  for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
    const css = getComputedStyle(node).backgroundColor, nums = (css.match(/[\d.]+/g) || []).map(Number)
    const unit = css.startsWith('color(') ? 255 : 1
    if (nums.length >= 3 && (nums.length < 4 || nums[3] > 0.5)) return { css, rgb: nums.slice(0, 3).map(v => v * unit) }
  }
  return { css: 'rgb(16 18 24)', rgb: [16, 18, 24] }
}
const skyFor = ([r, g, b]) => (0.2126 * r + 0.7152 * g + 0.0722 * b > 140 ? 'day' : 'night')

/** The boxes inside `root` marked `data-plat`, in game pixels measured from the canvas's top-left corner. */
function platforms(root, canvasEl) {
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

/** The level, mounted inside the New Game area `host` (a positioned element that holds the form). */
export function AttractLevel() {
  const box = useRef(null), cv = useRef(null), spot = useRef(null)

  useEffect(() => {
    const layer = box.current, canvasEl = cv.current
    const host = layer?.parentElement
    if (!host || !canvasEl || !canDraw()) return undefined

    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    let world = null, sky = '', raf = 0, timer = 0, last = 0, acc = 0, typed = 0, alive = true
    const seed = 1 + Math.floor(Math.random() * 1e6)

    const paint = () => {
      if (!world) return
      world.render()
    }
    const look = () => {
      const bg = backgroundOf(host), name = skyFor(bg.rgb)
      layer.style.setProperty('--cs-at-bg', bg.css)
      if (world && name !== sky) world.setPalette(name)
      sky = name
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
      world = new World(seed)
      world.build(W, H, platforms(host, canvasEl))
      if (keep) Object.assign(world, keep)
      world.attach(canvasEl, sky)
      const composer = host.querySelector('[data-plat="composer"]')?.getBoundingClientRect()
      if (composer) {
        layer.style.setProperty('--cs-at-sx', `${Math.round(composer.left + composer.width / 2 - area.left)}px`)
        layer.style.setProperty('--cs-at-sy', `${Math.round(composer.top + composer.height / 2 - area.top)}px`)
      }
      if (still?.matches) {
        // reduce motion: one still frame, a moment into the game so everything has settled
        for (let i = 0; i < 90; i++) world.step()
      }
      paint()
    }
    const later = () => { if (!timer) timer = setTimeout(build, 150) }

    const frame = now => {
      raf = requestAnimationFrame(frame)
      if (!world || still?.matches || document.hidden) { last = now; return }
      acc += Math.min(100, now - (last || now)); last = now
      let n = 0
      while (acc >= STEP && n < 4) { world.step(); acc -= STEP; n++ }
      if (world.frame % 60 === 0) look()
      if (n) paint()
    }

    const resized = new ResizeObserver(later)
    resized.observe(host)
    for (const el of host.querySelectorAll('[data-plat]')) resized.observe(el)
    const onInput = event => { if (event.target?.tagName === 'TEXTAREA' && world && ++typed % 4 === 0) world.typingCoin() }
    host.addEventListener('input', onInput)
    still?.addEventListener?.('change', later)
    build()
    raf = requestAnimationFrame(frame)

    return () => {
      alive = false
      cancelAnimationFrame(raf)
      clearTimeout(timer)
      resized.disconnect()
      host.removeEventListener('input', onInput)
      still?.removeEventListener?.('change', later)
    }
  }, [])

  return jsxs('div', {
    'aria-hidden': true,
    className: 'cs-at',
    ref: box,
    children: [jsx('canvas', { ref: cv }, 'level'), jsx('div', { className: 'cs-at-spot', ref: spot }, 'spot')]
  })
}
