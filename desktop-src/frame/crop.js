// Pictures the frame hands to the page: the whole frozen frame (with any colour preview the engine
// painted on it) and a close-up of one marked object.

/** The canvas as a PNG data URL, or '' when it cannot be read. */
export function frameImage(canvas) {
  try {
    return canvas ? canvas.toDataURL('image/png') : ''
  } catch {
    return ''
  }
}

/** A close-up of `box` (fractions of the canvas: x, y, w, h in 0..1) with a little room around it,
 *  enlarged by whole steps so the pixels stay sharp. '' when the canvas cannot be read. */
export function closeUp(canvas, box, { pad = 3, size = 96 } = {}) {
  if (!canvas || !box) {
    return ''
  }

  const unitX = canvas.width / 160
  const unitY = canvas.height / 144
  const left = Math.max(0, Math.floor(box.x * canvas.width - pad * unitX))
  const top = Math.max(0, Math.floor(box.y * canvas.height - pad * unitY))
  const width = Math.min(canvas.width - left, Math.ceil(box.w * canvas.width + 2 * pad * unitX))
  const height = Math.min(canvas.height - top, Math.ceil(box.h * canvas.height + 2 * pad * unitY))

  if (width <= 0 || height <= 0) {
    return ''
  }

  const zoom = Math.max(1, Math.floor(size / Math.max(width, height)))
  const out = document.createElement('canvas')

  out.width = width * zoom
  out.height = height * zoom

  const context = out.getContext('2d')

  context.imageSmoothingEnabled = false
  context.drawImage(canvas, left, top, width, height, 0, 0, out.width, out.height)

  try {
    return out.toDataURL('image/png')
  } catch {
    return ''
  }
}
