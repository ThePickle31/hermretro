// The New Game attract mode: a GBC-style platformer drawn behind the New Game form, where the Nous Girl plays one
// fixed level by herself and the form's boxes are platforms in it. Dimmed to half strength with a pool of the page's
// own colour behind the composer, so the game stays in the background ("Spotlight"). Purely decorative: no clicks,
// no keys, hidden from screen readers. The running is in run.js.
import { jsx, jsxs, useEffect, useRef } from '#sdk'
import { World } from './world.js'
import { runAttract } from './run.js'

/** Whether this browser can draw on a 2D canvas (the page tests' jsdom cannot). */
const canDraw = () => typeof CanvasRenderingContext2D === 'function'

/** The browser functions run.js uses. */
function browserEnv() {
  return {
    raf: requestAnimationFrame,
    caf: cancelAnimationFrame,
    setTimer: setTimeout,
    clearTimer: clearTimeout,
    getStyle: getComputedStyle,
    isHidden: () => document.hidden,
    motion: window.matchMedia?.('(prefers-reduced-motion: reduce)'),
    observe: (els, onChange) => {
      const watch = new ResizeObserver(onChange)
      for (const el of els) watch.observe(el)
      return () => watch.disconnect()
    }
  }
}

/** The level, drawn behind everything else in its parent (the positioned New Game area). */
export function AttractLevel() {
  const box = useRef(null), cv = useRef(null)

  useEffect(() => {
    const layer = box.current, canvasEl = cv.current, host = layer?.parentElement
    if (!host || !canvasEl || !canDraw()) return undefined
    return runAttract({
      host,
      layer,
      canvasEl,
      makeWorld: seed => new World(seed),
      env: browserEnv(),
      seed: 1 + Math.floor(Math.random() * 1e6)
    })
  }, [])

  return jsxs('div', {
    'aria-hidden': true,
    className: 'cs-at',
    ref: box,
    children: [jsx('canvas', { ref: cv }, 'level'), jsx('div', { className: 'cs-at-spot' }, 'spot')]
  })
}
