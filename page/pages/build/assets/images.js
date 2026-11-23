// Asset pictures in the conversation: thumbs, sprites, strips.
import { jsx, jsxs, useEffect, useLayoutEffect, useRef, useState } from '#sdk'
import { baseName } from '#app/paths.js'
import { useAsset, useAssetPreview } from './cache.js'
import { drawSpriteFrame, paintSheet, spriteFrameMs } from './sprite.js'

export function AssetThumb({ asset, onOpen, size = 'sm', fresh = false }) {
  const { state, asset: loaded } = useAssetPreview(asset.path, asset.version)

  if (state === 'none') {
    return null
  }

  if (state === 'loading') {
    return jsx('span', { 'aria-hidden': true, className: `cs-b-th ${size} loading` })
  }

  return jsx('button', {
    'aria-label': `Look closer at ${loaded.name}`,
    className: `cs-b-th ${size}${fresh ? ' fresh' : ''}`,
    onClick: event => {
      event.stopPropagation()
      onOpen?.(asset, event.currentTarget)
    },
    title: `${loaded.name} · ${loaded.width}×${loaded.height}`,
    type: 'button',
    children: jsx(SheetFrame, { animate: size === 'lg', loaded })
  })
}

/** A sprite as the game shows it: the frame it stands in (moving with `animate`), in the palette it is
 *  painted with, the transparency green cleared. Without the backend's tiles (an older backend) the
 *  sheet's first frame, still with the green cleared. */
function SpriteImage({ loaded, animate = false, className = 'cs-b-spr' }) {
  const ref = useRef(null)
  const image = useImage(loaded.dataUrl)
  const sprite = loaded.sprite
  const moving = sprite.moving?.frames?.length > 1 ? sprite.moving : null
  const frames = animate && moving ? moving.frames : null
  const [frame, setFrame] = useState(0)
  const frameMs = spriteFrameMs(sprite.animSpeed)

  useEffect(() => {
    if (!frames) {
      return undefined
    }

    const id = setInterval(() => setFrame(value => (value + 1) % frames.length), frameMs)

    return () => clearInterval(id)
  }, [frames?.length, frameMs])

  const tiles = frames ? frames[frame % frames.length] : sprite.standing?.tiles
  const flip = frames ? Boolean(moving.flip) : Boolean(sprite.standing?.flip)
  const width = sprite.canvasWidth ?? sprite.frameWidth ?? 16
  const height = sprite.canvasHeight ?? sprite.frameHeight ?? 16

  useLayoutEffect(() => {
    const canvas = ref.current
    const context = canvas?.getContext?.('2d')

    if (!context || !image) {
      return
    }

    const scale = 4

    canvas.width = width * scale
    canvas.height = height * scale
    context.imageSmoothingEnabled = false
    context.clearRect(0, 0, canvas.width, canvas.height)

    const sheet = paintSheet(image, sprite.palette ?? null)

    if (tiles?.length) {
      drawSpriteFrame(context, sheet, tiles, { flip, height, left: 0, scale, top: 0, width })
    } else {
      context.drawImage(sheet, 0, 0, sprite.frameWidth ?? width, sprite.frameHeight ?? height, 0, 0, width * scale, height * scale)
    }
  }, [image, tiles, flip, width, height, sprite.palette?.join(',')])

  return jsx('canvas', { 'aria-hidden': true, className, ref, style: { aspectRatio: `${width} / ${height}` } })
}

/** A sprite shows the frame the game stands it in, in its colours (`SpriteImage`); anything else whole. */
export function SheetFrame({ loaded, animate = false }) {
  return loaded.sprite ? jsx(SpriteImage, { animate, loaded }) : jsx('img', { alt: '', draggable: false, src: loaded.dataUrl })
}

/** An asset as a plain image (inside another control), or the fallback while it is not there. */
export function AssetImage({ asset, className, fallback = null }) {
  const { state, asset: loaded } = useAsset(asset.path, asset.version)

  if (state !== 'ok') {
    return fallback
  }

  return loaded.sprite ? jsx(SpriteImage, { className: className ? `cs-b-spr ${className}` : 'cs-b-spr', loaded }) : jsx('img', { alt: '', className, draggable: false, src: loaded.dataUrl })
}

/** The newest image of a live turn, large. Shown only once it loads: a card whose image the backend
 *  would not give (gone, outside the games, or an older backend without the asset call) has nothing to click. */
export function LatestAsset({ asset, onOpen }) {
  const { state } = useAsset(asset.path, asset.version)

  if (state === 'none') {
    return null
  }

  return jsxs('div', {
    className: 'cs-b-latest',
    children: [
      jsx(AssetThumb, { asset, fresh: true, onOpen, size: 'lg' }),
      jsxs('div', {
        className: 'cs-col',
        children: [
          jsx('span', { className: 'cs-eyebrow', children: 'Latest' }),
          jsx('b', { children: baseName(asset.path) }),
          jsx('span', { className: 'cs-faint', children: `${asset.kind} · ${asset.step}` }),
          jsx('span', { className: 'cs-faint', children: state === 'ok' ? 'Click it to look closer' : 'Loading…' })
        ]
      })
    ]
  })
}

export function AssetStrip({ assets, onOpen, size = 'sm', max = 6, freshFrom = null }) {
  if (!assets.length) {
    return null
  }

  const shown = assets.slice(-max)

  return jsxs('span', {
    className: 'cs-b-strip',
    children: [
      ...shown.map(asset => jsx(AssetThumb, { asset, fresh: freshFrom != null && asset.at != null && asset.at >= freshFrom, onOpen, size }, `${asset.path}#${asset.version}`)),
      assets.length > shown.length ? jsx('span', { className: 'cs-b-more', children: `+${assets.length - shown.length}` }) : null
    ]
  })
}

export function useImage(src) {
  const [image, setImage] = useState(null)

  useEffect(() => {
    if (!src) {
      setImage(null)

      return undefined
    }

    let live = true
    const element = document.createElement('img')

    element.onload = () => live && setImage(element)
    element.src = src

    return () => {
      live = false
    }
  }, [src])

  return image
}

export function FrameCanvas({ image, frame, scale, className }) {
  const ref = useRef(null)

  useLayoutEffect(() => {
    const canvas = ref.current

    if (!canvas || !image || !frame?.w || !frame?.h) {
      return
    }

    const context = canvas.getContext?.('2d')

    if (!context) {
      return
    }

    canvas.width = frame.w * scale
    canvas.height = frame.h * scale
    context.imageSmoothingEnabled = false
    context.clearRect(0, 0, canvas.width, canvas.height)
    context.drawImage(image, frame.x, frame.y, frame.w, frame.h, 0, 0, frame.w * scale, frame.h * scale)
  }, [image, frame?.x, frame?.y, frame?.w, frame?.h, scale])

  return jsx('canvas', { className, ref })
}

/** The colours an image uses, most used first (pixel art has a handful). */
export function imagePalette(image, max = 16) {
  try {
    const canvas = document.createElement('canvas')

    canvas.width = Math.min(image.naturalWidth, 512)
    canvas.height = Math.min(image.naturalHeight, 512)

    const context = canvas.getContext('2d')

    if (!context) {
      return []
    }

    context.drawImage(image, 0, 0)

    const { data } = context.getImageData(0, 0, canvas.width, canvas.height)
    const counts = new Map()

    for (let index = 0; index < data.length; index += 4) {
      if (data[index + 3] < 128) {
        continue
      }

      const key = `#${[data[index], data[index + 1], data[index + 2]].map(value => value.toString(16).padStart(2, '0')).join('')}`

      counts.set(key, (counts.get(key) ?? 0) + 1)

      if (counts.size > Math.max(64, max)) {
        break
      }
    }

    return [...counts].sort((a, b) => b[1] - a[1]).slice(0, max).map(([color]) => color)
  } catch {
    return []
  }
}
