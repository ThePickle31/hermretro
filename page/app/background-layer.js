// The shell's background layer: behind the page area, it draws the background a page asked for (background.js).
// A background once shown stays mounted, hidden and paused while another (or none) is wanted, so going back to it
// carries on where it was instead of starting again.
import { jsx, useLayoutEffect, useRef, useState } from '#sdk'
import { BACKGROUNDS } from '#backgrounds/index.js'
import { onBackgroundChange, wantedBackground } from './background.js'

const byId = new Map(BACKGROUNDS.map(background => [background.id, background]))

/** The browser functions a background runs with (its window's); `isHidden()` is also true while its layer is not
 *  shown. */
function browserEnv(layer) {
  const win = layer.ownerDocument.defaultView

  return {
    raf: callback => win.requestAnimationFrame(callback),
    caf: id => win.cancelAnimationFrame(id),
    setTimer: (callback, ms) => win.setTimeout(callback, ms),
    clearTimer: id => win.clearTimeout(id),
    getStyle: el => win.getComputedStyle(el),
    isHidden: () => win.document.hidden || layer.hidden,
    motion: win.matchMedia?.('(prefers-reduced-motion: reduce)'),
    observe: (els, onChange) => {
      const watch = new win.ResizeObserver(onChange)
      for (const el of els) watch.observe(el)
      return () => watch.disconnect()
    }
  }
}

function BackgroundSlot({ background, shown }) {
  const ref = useRef(null)

  // started before the first paint, so its first frame is there with the page
  useLayoutEffect(() => {
    const layer = ref.current

    return background.start({ host: layer.parentElement, layer, env: browserEnv(layer) })
  }, [])

  return jsx('div', { 'aria-hidden': true, className: 'cs-bg', 'data-bg': background.id, hidden: !shown, ref })
}

export function BackgroundLayer() {
  const [wanted, setWanted] = useState(wantedBackground)
  const [started, setStarted] = useState([])

  useLayoutEffect(() => {
    const update = () => setWanted(wantedBackground())

    update()

    return onBackgroundChange(update)
  }, [])

  if (wanted && !byId.has(wanted)) {
    console.warn(`[hermretro] no background "${wanted}" (page/backgrounds/index.js lists them)`)
  }

  const live = wanted && byId.has(wanted) && !started.includes(wanted) ? [...started, wanted] : started

  useLayoutEffect(() => {
    if (live !== started) setStarted(live)
  })

  return live.map(id => jsx(BackgroundSlot, { background: byId.get(id), shown: id === wanted }, id))
}
