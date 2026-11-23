// The image viewport, its pan gesture and the controls drawn over it.
import { Codicon, jsx, jsxs, useRef } from '#sdk'
import { AGENT } from '#app/ids.js'
import { stepWords } from '#pages/build/transcript/step-words.js'
import { SpriteFrameCanvas } from './sprite-canvas.js'

export function StageViewport({ area, children, kind, picking, running, shownView, stageRef, working, playback, scenePicker }) {
  const pan = useRef(null)
  const { animation, animations, colors, frame, frames, image, onion, playing, setAnimationIndex, setFrame, setOnion, setPlaying, sprite } = playback
  const { scene, scenes, setSceneIndex } = scenePicker
  const chips = []

  if (shownView === 'Animation' && animations.length) {
    chips.push(
      jsx('div', {
        className: 'cs-v-float tl',
        children: animations.map((entry, position) =>
          jsx('button', { 'aria-pressed': entry === animation, className: `cs-v-chip${entry === animation ? ' on' : ''}`, onClick: () => setAnimationIndex(position), type: 'button', children: entry.name }, entry.slot)
        )
      }, 'anims'),
      jsxs('div', {
        className: 'cs-v-float tr',
        children: [
          jsx('button', { 'aria-label': playing ? 'Pause' : 'Play', className: 'cs-v-chip', onClick: () => setPlaying(value => !value), type: 'button', children: jsx(Codicon, { name: playing ? 'debug-pause' : 'play', size: 12 }) }),
          jsx('span', { className: 'cs-v-chip quiet', title: 'The speed the game plays it at', children: sprite?.animSpeed != null && Number(sprite.animSpeed) < 255 ? `${Math.round((60 / (Number(sprite.animSpeed) + 1)) * 10) / 10} fps` : 'Not animated in game' }),
          jsx('button', { 'aria-pressed': onion, className: `cs-v-chip${onion ? ' on' : ''}`, onClick: () => setOnion(value => !value), type: 'button', children: 'Onion skin' })
        ]
      }, 'play'),
      frames.length > 1
        ? jsx('div', {
            className: 'cs-v-float bottom',
            children: frames.map((tiles, position) =>
              jsx('button', {
                'aria-label': `Frame ${position + 1}`,
                'aria-pressed': position === frame,
                className: `cs-v-frame${position === frame ? ' on' : ''}`,
                onClick: () => {
                  setPlaying(false)
                  setFrame(position)
                },
                type: 'button',
                children: jsx(SpriteFrameCanvas, { colors, flip: animation.flip, image, scale: Math.max(1, Math.floor(36 / Math.max(sprite.canvasWidth, sprite.canvasHeight))), sprite, tiles })
              }, position)
            )
          }, 'frames')
        : null
    )
  }

  if (shownView === 'In game' && kind !== 'cover' && scenes.length) {
    chips.push(
      jsxs('div', {
        className: 'cs-v-float tl',
        children: [
          ...scenes.map((entry, position) =>
            jsx('button', { 'aria-pressed': entry === scene, className: `cs-v-chip${entry === scene ? ' on' : ''}`, onClick: () => setSceneIndex(position), type: 'button', children: entry.name }, entry.id ?? position)
          )
        ]
      }, 'scenes'),
      jsx('span', { className: 'cs-v-float br cs-v-chip quiet', children: 'As the scene starts, from the project files' }, 'note')
    )
  }

  if (picking && !area) {
    chips.push(jsx('span', { className: 'cs-v-float bottom cs-v-chip quiet', children: 'Drag on the picture to mark the area to change' }, 'hint'))
  }

  if (working) {
    chips.push(
      jsxs('div', {
        className: 'cs-v-working',
        children: [jsx('span', { className: 'cs-b-spin' }), jsx('span', { children: running ? `${AGENT}: ${stepWords(running)[0]}` : `${AGENT} is working on it` })]
      }, 'working')
    )
  }

  return jsxs('div', {
    className: `cs-v-stage${kind === 'sprite' && shownView !== 'In game' ? ' checker' : ''}`,
    children: [
      jsx('div', {
        className: `cs-v-scroll${picking ? '' : ' pannable'}`,
        onPointerDown: event => {
          const element = stageRef.current

          if (picking || event.button !== 0 || !element || (element.scrollWidth <= element.clientWidth && element.scrollHeight <= element.clientHeight)) {
            return
          }

          pan.current = { x: event.clientX, y: event.clientY, left: element.scrollLeft, top: element.scrollTop }
          element.setPointerCapture?.(event.pointerId)
        },
        onPointerMove: event => {
          const element = stageRef.current

          if (pan.current && element) {
            element.scrollLeft = pan.current.left - (event.clientX - pan.current.x)
            element.scrollTop = pan.current.top - (event.clientY - pan.current.y)
          }
        },
        onPointerUp: () => {
          pan.current = null
        },
        ref: stageRef,
        children: jsx('div', { className: 'cs-v-stage-in', children })
      }),
      ...chips
    ]
  })
}
