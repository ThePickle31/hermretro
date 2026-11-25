// Art shown where the game uses it.
import { jsx, jsxs, useLayoutEffect, useRef } from '#sdk'
import { drawSpriteFrame, paintSheet, spriteOriginX } from '#pages/build/assets/sprite.js'
import { useImages } from './info.js'

/** A scene as the game draws it at the start: the background and each actor's standing frame. */
export function SceneCanvas({ scene, scale, highlight, refresh }) {
  const paths = [...new Set([scene.background, ...(scene.actors ?? []).map(actor => actor.sprite)].filter(Boolean))]
  const images = useImages(paths, `scene:${refresh}`)
  const ref = useRef(null)
  const width = (Number(scene.width) || 20) * 8
  const height = (Number(scene.height) || 18) * 8

  useLayoutEffect(() => {
    const canvas = ref.current
    const context = canvas?.getContext?.('2d')

    if (!context) {
      return
    }

    canvas.width = width * scale
    canvas.height = height * scale
    context.imageSmoothingEnabled = false
    context.fillStyle = '#111'
    context.fillRect(0, 0, canvas.width, canvas.height)

    const background = scene.background ? images[scene.background] : null

    if (background) {
      context.drawImage(background, 0, 0, background.naturalWidth * scale, background.naturalHeight * scale)
    }

    for (const actor of scene.actors ?? []) {
      const sheet = images[actor.sprite]

      if (!sheet) {
        continue
      }

      const left = (Number(actor.x) || 0) * 8 - spriteOriginX(actor.canvasWidth)
      const top = ((Number(actor.y) || 0) + 1) * 8 - actor.canvasHeight

      drawSpriteFrame(context, paintSheet(sheet, actor.palette?.colors), actor.tiles, {
        flip: actor.flip,
        height: actor.canvasHeight,
        left: left * scale,
        scale,
        top: top * scale,
        width: actor.canvasWidth
      })

      if (highlight && actor.spriteId === highlight) {
        context.save()
        context.strokeStyle = '#fbbf24'
        context.lineWidth = 2
        context.setLineDash([5, 4])
        context.strokeRect(left * scale - 3, top * scale - 3, actor.canvasWidth * scale + 6, actor.canvasHeight * scale + 6)
        context.restore()
      }
    }
  }, [scene, images, scale, highlight, refresh, width, height])

  return jsx('canvas', { className: 'cs-v-px', ref })
}

/** The cover where players see it: its Games page card and a Chromatic screen. */
export function CoverInGame({ image, game }) {
  const card = game?.card ?? null
  const title = card?.title || game?.title || 'Your game'
  const src = image?.src ?? null

  return jsxs('div', {
    className: 'cs-v-ingame',
    children: [
      jsxs('figure', {
        children: [
          jsxs('div', {
            className: 'cs-v-gcard',
            children: [
              src ? jsx('img', { alt: '', src }) : jsx('span', { className: 'cs-v-ver-ph' }),
              jsxs('div', {
                className: 'cs-col',
                style: { gap: 3, padding: '9px 11px' },
                children: [
                  jsx('b', { children: title }),
                  card?.tagline ? jsx('span', { className: 'cs-faint', children: card.tagline }) : null,
                  card?.genres?.length ? jsx('span', { className: 'cs-row', style: { gap: 5 }, children: card.genres.map(genre => jsx('span', { className: 'cs-tag', children: genre }, genre)) }) : null
                ]
              })
            ]
          }),
          jsx('figcaption', { children: 'Games page' })
        ]
      }),
      jsxs('figure', {
        children: [
          jsxs('div', {
            className: 'cs-v-device',
            children: [
              jsx('div', { className: 'cs-v-device-screen', children: src ? jsx('img', { alt: '', src }) : null }),
              jsx('span', { className: 'cs-v-device-name', children: 'CHROMATIC' }),
              jsxs('div', { 'aria-hidden': true, className: 'cs-v-device-pad', children: [jsx('i', { className: 'dpad' }), jsxs('span', { children: [jsx('i', {}), jsx('i', {})] })] })
            ]
          }),
          jsx('figcaption', { children: 'On a Chromatic' })
        ]
      })
    ]
  })
}
