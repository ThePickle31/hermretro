// Hardware checks on a piece of art.
/** Hardware checks the page can make from the pixels. */
export function artChecks(image, kind, info) {
  if (!image) {
    return []
  }

  const width = image.naturalWidth
  const height = image.naturalHeight
  const checks = []

  try {
    const canvas = document.createElement('canvas')

    canvas.width = width
    canvas.height = height

    const context = canvas.getContext('2d')

    context.drawImage(image, 0, 0)

    const { data } = context.getImageData(0, 0, width, height)
    const colour = (x, y) => {
      const index = (y * width + x) * 4

      return data[index + 3] < 128 ? -1 : (data[index] << 16) | (data[index + 1] << 8) | data[index + 2]
    }
    const tileColours = (tileWidth, tileHeight, skip) => {
      let worst = 0
      let over = 0
      const unique = new Set()

      for (let top = 0; top + tileHeight <= height; top += tileHeight) {
        for (let left = 0; left + tileWidth <= width; left += tileWidth) {
          const seen = new Set()
          let signature = ''

          for (let y = top; y < top + tileHeight; y += 1) {
            for (let x = left; x < left + tileWidth; x += 1) {
              const value = colour(x, y)

              signature += `${value},`

              if (!skip(value)) {
                seen.add(value)
              }
            }
          }

          unique.add(signature)
          worst = Math.max(worst, seen.size)
          over += seen.size > (skip === noSkip ? 4 : 3) ? 1 : 0
        }
      }

      return { worst, over, unique: unique.size }
    }
    const noSkip = () => false

    if (kind === 'sprite') {
      const result = tileColours(8, 16, value => value === -1 || value === 0x65ff00 || ((value >> 16) < 130 && ((value >> 8) & 255) > 215 && (value & 255) < 80))

      checks.push(result.over ? { ok: false, text: `${result.over} ${result.over === 1 ? 'tile uses' : 'tiles use'} more than 3 colours (the hardware shows 3 + transparent)` } : { ok: true, text: `At most ${result.worst} colours per 8×16 tile` })

      const sprite = info?.sprite

      if (sprite) {
        const fits = sprite.canvasWidth % 8 === 0 && sprite.canvasHeight % 16 === 0
        const objects = (sprite.canvasWidth / 8) * Math.max(1, sprite.canvasHeight / 16)

        checks.push(fits ? { ok: true, text: `${objects} hardware ${objects === 1 ? 'object' : 'objects'} per frame (8×16 mode)` } : { ok: false, text: `Frame is ${sprite.canvasWidth}×${sprite.canvasHeight}: not a multiple of 8×16` })

        if (sprite.numTiles != null) {
          checks.push({ ok: true, text: `${sprite.numTiles} tiles in video memory` })
        }
      }
    } else if (kind === 'background') {
      const result = tileColours(8, 8, noSkip)

      checks.push(result.over ? { ok: false, text: `${result.over} ${result.over === 1 ? 'tile uses' : 'tiles use'} more than 4 colours` } : { ok: true, text: `At most ${result.worst} colours per 8×8 tile` })
      checks.push(result.unique > 192 ? { ok: false, text: `${result.unique} unique tiles (keep it at 192 or fewer)` } : { ok: true, text: `${result.unique} unique tiles of 192` })
    } else if (kind === 'cover') {
      const colours = new Set()
      let transparent = false

      for (let y = 0; y < height; y += 1) {
        for (let x = 0; x < width; x += 1) {
          const value = colour(x, y)

          if (value === -1) {
            transparent = true
          } else {
            colours.add(value)
          }
        }
      }

      checks.push(width === 160 && height === 144 ? { ok: true, text: '160×144, the Chromatic screen size' } : { ok: false, text: `${width}×${height}: covers are 160×144` })
      checks.push(colours.size <= 32 ? { ok: true, text: `${colours.size} colours (32 at most)` } : { ok: false, text: `${colours.size} colours: covers use 32 at most` })
      checks.push(transparent ? { ok: false, text: 'Has transparent pixels: covers are opaque' } : { ok: true, text: 'Opaque' })
    }
  } catch {
    return []
  }

  return checks
}
