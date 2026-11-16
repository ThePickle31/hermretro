// A frame from the player, shrunk to a thumbnail.
/** Draw a frame at the Game Boy's own size, so a title screen stays small (the RPC takes ≤ 64 KB). */
export function shrinkFrame(dataUrl) {
  return new Promise(resolve => {
    try {
      const image = new Image()

      image.onload = () => {
        try {
          const canvas = document.createElement('canvas')

          canvas.width = 160
          canvas.height = 144

          const g = canvas.getContext('2d')

          g.imageSmoothingEnabled = false
          g.drawImage(image, 0, 0, 160, 144)

          // A blank (single-colour) frame is not a title screen yet.
          const pixels = g.getImageData(0, 0, 160, 144).data
          let varied = false

          for (let i = 4; i < pixels.length && !varied; i += 4) {
            varied = pixels[i] !== pixels[0] || pixels[i + 1] !== pixels[1] || pixels[i + 2] !== pixels[2]
          }

          resolve(varied ? canvas.toDataURL('image/png') : '')
        } catch {
          resolve('')
        }
      }

      image.onerror = () => resolve('')
      image.src = dataUrl
    } catch {
      resolve('')
    }
  })
}
