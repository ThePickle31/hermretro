// Drawing sprite sheets and their frames.
// GB Studio's sprite source shades, lightest first, as palette indices; #65ff00 is transparent.
const SPRITE_SHADES = new Map([[0xe0f8cf, 0], [0x86c06c, 1], [0x306850, 2], [0x071821, 3]])
const paintedSheets = new WeakMap()

/** A sprite sheet as the game paints it: the transparency marker cleared and, with a palette, the
 *  four source shades swapped for the palette's colours (anything else is left as drawn). */
export function paintSheet(image, colors) {
  const key = colors ? colors.join(',') : 'plain'
  let byPalette = paintedSheets.get(image)

  if (!byPalette) {
    byPalette = new Map()
    paintedSheets.set(image, byPalette)
  }

  if (byPalette.has(key)) {
    return byPalette.get(key)
  }

  const canvas = document.createElement('canvas')

  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight

  const context = canvas.getContext('2d')

  if (!context) {
    return image
  }

  context.drawImage(image, 0, 0)

  try {
    const data = context.getImageData(0, 0, canvas.width, canvas.height)
    const pixels = data.data
    const rgb = colors?.map(color => parseInt(String(color).replace('#', ''), 16))

    for (let index = 0; index < pixels.length; index += 4) {
      const value = (pixels[index] << 16) | (pixels[index + 1] << 8) | pixels[index + 2]

      if (value === 0x65ff00 || (pixels[index] < 130 && pixels[index + 1] > 215 && pixels[index + 2] < 80)) {
        pixels[index + 3] = 0
      } else if (rgb && SPRITE_SHADES.has(value)) {
        const to = rgb[SPRITE_SHADES.get(value)]

        pixels[index] = (to >> 16) & 255
        pixels[index + 1] = (to >> 8) & 255
        pixels[index + 2] = to & 255
      }
    }

    context.putImageData(data, 0, 0)
  } catch {
    // A tainted canvas cannot be read: the sheet is shown as it is.
  }

  byPalette.set(key, canvas)

  return canvas
}

/** Where GB Studio puts a tile's x = 0 in a sprite canvas `width` pixels wide: the left of its middle 16 pixels
 *  (a 32-pixel frame keeps its first column at x = -8). */
export function spriteOriginX(width) {
  return width < 16 ? 0 : width / 2 - 8
}

/** Draw one sprite frame (GB Studio metasprite tiles, 8×16 each) at (left, top), whole-canvas mirrored with `flip`. */
export function drawSpriteFrame(context, sheet, tiles, { width, height, left, top, scale, flip = false }) {
  const originX = spriteOriginX(width)

  for (const tile of tiles ?? []) {
    const x = originX + (Number(tile.x) || 0)
    const y = Number(tile.y) || 0
    const mirror = Boolean(tile.flipX) !== flip
    const tileLeft = flip ? width - x - 8 : x
    const tileTop = height - 16 - y

    context.save()
    context.translate(left + (tileLeft + (mirror ? 8 : 0)) * scale, top + (tileTop + (tile.flipY ? 16 : 0)) * scale)
    context.scale(mirror ? -1 : 1, tile.flipY ? -1 : 1)
    context.drawImage(sheet, Number(tile.sliceX) || 0, Number(tile.sliceY) || 0, 8, 16, 0, 0, 8 * scale, 16 * scale)
    context.restore()
  }
}

/** The animations a sprite shows, with a left slot GB Studio mirrors from the right one filled in. */
export function spriteAnimations(sprite) {
  const all = sprite?.animations ?? []
  const filled = frames => frames.some(tiles => tiles.length)

  return all
    .map(animation => {
      if (filled(animation.frames)) {
        return { ...animation, flip: false }
      }

      if (sprite.flipLeft && /left/i.test(animation.name)) {
        const right = all.find(other => other.name === animation.name.replace(/left/i, match => (match === 'Left' ? 'Right' : 'right')))

        if (right && filled(right.frames)) {
          return { ...animation, frames: right.frames, flip: true }
        }
      }

      return null
    })
    .filter(Boolean)
}

/** Game frames per animation frame from GB Studio's animSpeed (the frame advances every animSpeed + 1 ticks). */
export function spriteFrameMs(animSpeed) {
  const speed = Number(animSpeed)

  return Number.isFinite(speed) && speed >= 0 && speed < 255 ? ((speed + 1) * 1000) / 60 : 250
}

/** A painted canvas as something FrameCanvas can draw (it only needs drawImage and natural size). */
export function canvasImage(canvas, image) {
  return Object.assign(canvas, { naturalHeight: image.naturalHeight, naturalWidth: image.naturalWidth })
}
