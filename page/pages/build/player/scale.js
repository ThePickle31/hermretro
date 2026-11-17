// How big the inline player draws the game: always a whole-number multiple of the Game Boy screen,
// so every game pixel is the same number of screen pixels. Pure; no React.
import { DEVICE_RATIO, DEVICE_SCREEN_SHARE, SCREEN_H, SCREEN_W } from '#shared/player/protocol.js'

/** The scale choices in the bar. `fit` is the largest whole step that fits. */
export const SCALES = Object.freeze(['fit', 2, 3, 4])

/** Frame size for the bare screen at scale `step`. */
const screenAt = step => ({ width: SCREEN_W * step, height: SCREEN_H * step })

/** Frame size for the handheld whose screen is `step` × the Game Boy's. Not rounded: the handheld art
 *  scales with the frame's width, so only the exact width keeps its screen at 160 × `step` pixels. */
const deviceAt = step => {
  const width = (SCREEN_W * step) / DEVICE_SCREEN_SHARE

  return { width, height: width / DEVICE_RATIO }
}

/** The largest whole step whose size fits `box`; 1 when even that does not fit (the stage scrolls). */
function largestStep(sizeAt, box) {
  let step = 1

  while (step < 12) {
    const next = sizeAt(step + 1)

    if (next.width > box.width || next.height > box.height) {
      break
    }

    step += 1
  }

  return step
}

/**
 * The frame size and scale for `view` ('screen' | 'device') in `box` ({ width, height }).
 * `scale` is a SCALES entry; a fixed step larger than what fits falls back to the largest that does.
 * Returns { width, height, step, fits } where `fits` lists the fixed steps that fit (for the bar).
 */
export function playerSize(view, scale, box) {
  const sizeAt = view === 'device' ? deviceAt : screenAt
  const most = largestStep(sizeAt, box)
  const step = scale === 'fit' || view === 'device' ? most : Math.min(Number(scale) || most, most)

  return { ...sizeAt(step), step, fits: SCALES.filter(entry => entry === 'fit' || entry <= most) }
}
