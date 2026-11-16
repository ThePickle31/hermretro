// One sprite frame on a canvas.
import { jsx, useLayoutEffect, useRef } from '../sdk.js'
import { drawSpriteFrame, paintSheet } from '../build-assets/sprite.js'

/** One sprite frame, big, painted with the game's palette (and the previous frame faintly under it). */
export function SpriteFrameCanvas({ image, sprite, tiles, flip, scale, colors, under = null }) {
  const ref = useRef(null)
  const width = sprite?.canvasWidth ?? 16
  const height = sprite?.canvasHeight ?? 16

  useLayoutEffect(() => {
    const canvas = ref.current
    const context = canvas?.getContext?.('2d')

    if (!context || !image) {
      return
    }

    canvas.width = width * scale
    canvas.height = height * scale
    context.imageSmoothingEnabled = false
    context.clearRect(0, 0, canvas.width, canvas.height)

    const sheet = paintSheet(image, colors)

    if (under) {
      context.globalAlpha = 0.28
      drawSpriteFrame(context, sheet, under, { flip, height, left: 0, scale, top: 0, width })
      context.globalAlpha = 1
    }

    drawSpriteFrame(context, sheet, tiles, { flip, height, left: 0, scale, top: 0, width })
  }, [image, tiles, under, flip, scale, colors?.join(','), width, height])

  return jsx('canvas', { className: 'cs-v-px', ref })
}
