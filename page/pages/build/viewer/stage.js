// The viewer's image stage: zoom, fit and the version strip.
import { jsx, jsxs, useLayoutEffect, useRef, useState } from '#sdk'
import { useAsset } from '#pages/build/assets/cache.js'
import { FrameCanvas, SheetFrame } from '#pages/build/assets/images.js'
import { timeOfDay } from '#shared/ui/time.js'

export const ZOOM_STEPS = [1, 2, 3, 4, 6, 8, 12, 16]

export function versionTime(entry) {
  return entry?.at ? timeOfDay(entry.at) : ''
}

/** A version's small picture in the strip. */
export function VersionThumb({ path, entry, number, selected, onPick }) {
  const { state, asset: loaded } = useAsset(path, `kept:${entry.id}`)

  return jsxs('button', {
    'aria-label': `Version ${number}${entry.current ? ', in the game now' : ''}`,
    'aria-pressed': selected,
    className: `cs-v-ver${selected ? ' on' : ''}`,
    onClick: () => onPick(entry.id),
    title: `v${number} · ${versionTime(entry)}${entry.current ? ' · in the game now' : ''}`,
    type: 'button',
    children: [
      state === 'ok' ? jsx(SheetFrame, { loaded }) : jsx('span', { className: 'cs-v-ver-ph' }),
      jsx('b', { children: `v${number}` }),
      entry.current ? jsx('i', { 'aria-hidden': true, className: 'cs-v-now' }) : null
    ]
  })
}

/** The stage's size, for Fit zoom. */
export function useBoxSize(ref) {
  const [size, setSize] = useState({ width: 0, height: 0 })

  useLayoutEffect(() => {
    const element = ref.current

    if (!element) {
      return undefined
    }

    const measure = () => setSize({ width: element.clientWidth, height: element.clientHeight })

    measure()

    if (typeof ResizeObserver === 'undefined') {
      return undefined
    }

    const observer = new ResizeObserver(measure)

    observer.observe(element)

    return () => observer.disconnect()
  }, [])

  return size
}

export function fitScale(box, width, height, pad = 48) {
  if (!box.width || !box.height || !width || !height) {
    return 1
  }

  const fit = Math.min((box.width - pad) / width, (box.height - pad) / height)

  return fit >= 1 ? Math.min(16, Math.floor(fit)) : Math.max(0.1, fit)
}

/** A whole image, scaled, with an optional tile grid and a draggable area box (in image pixels). */
export function ImageStage({ image, scale, grid, gridSize = [8, 8], area, onArea, picking }) {
  const drag = useRef(null)
  const width = image ? image.naturalWidth : 0
  const height = image ? image.naturalHeight : 0
  const point = event => {
    const box = event.currentTarget.getBoundingClientRect()

    return {
      x: Math.max(0, Math.min(width, Math.round((event.clientX - box.left) / scale))),
      y: Math.max(0, Math.min(height, Math.round((event.clientY - box.top) / scale)))
    }
  }

  return jsxs('div', {
    className: `cs-v-canvas${picking ? ' picking' : ''}`,
    onPointerDown: picking
      ? event => {
          event.currentTarget.setPointerCapture?.(event.pointerId)
          drag.current = point(event)
          onArea({ x: drag.current.x, y: drag.current.y, w: 0, h: 0 })
        }
      : undefined,
    onPointerMove: picking
      ? event => {
          if (!drag.current) {
            return
          }

          const now = point(event)

          onArea({ x: Math.min(now.x, drag.current.x), y: Math.min(now.y, drag.current.y), w: Math.abs(now.x - drag.current.x), h: Math.abs(now.y - drag.current.y) })
        }
      : undefined,
    onPointerUp: picking
      ? () => {
          drag.current = null
          onArea(current => (current && current.w >= 2 && current.h >= 2 ? current : null))
        }
      : undefined,
    style: { height: `${height * scale}px`, width: `${width * scale}px` },
    children: [
      image ? jsx(FrameCanvas, { frame: { x: 0, y: 0, w: width, h: height }, image, scale }) : null,
      grid && scale >= 2 ? jsx('span', { 'aria-hidden': true, className: 'cs-v-grid', style: { backgroundSize: `${gridSize[0] * scale}px ${gridSize[1] * scale}px` } }) : null,
      area
        ? jsx('span', {
            'aria-hidden': true,
            className: 'cs-v-area',
            style: { height: `${area.h * scale}px`, left: `${area.x * scale}px`, top: `${area.y * scale}px`, width: `${area.w * scale}px` },
            children: jsx('em', { children: `${area.w}×${area.h} at ${area.x}, ${area.y}` })
          })
        : null
    ]
  })
}
