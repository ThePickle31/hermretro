// Step through the game frames that this turn actually captured.
import { Codicon, jsx, jsxs, useEffect, useState } from '#sdk'
import { AssetThumb } from '#pages/build/assets/images.js'

export function FrameReplay({ frames, onOpen }) {
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const current = Math.min(index, frames.length - 1)

  useEffect(() => {
    if (!playing) {
      return undefined
    }

    const timer = setTimeout(() => {
      if (current + 1 < frames.length) {
        setIndex(current + 1)
      } else {
        setPlaying(false)
      }
    }, 350)

    return () => clearTimeout(timer)
  }, [playing, current, frames.length])

  return jsxs('div', {
    className: 'cs-b-replay',
    children: [
      jsx(AssetThumb, { asset: frames[current], onOpen, size: 'lg' }),
      jsxs('div', {
        className: 'cs-col',
        children: [
          jsx('b', { children: 'Playtest' }),
          frames.length > 1 ? jsxs('div', {
            className: 'cs-col',
            children: [
              jsx('span', { className: 'cs-faint cs-small', children: `Frame ${current + 1} of ${frames.length}` }),
              jsx('input', {
                'aria-label': 'Playtest frame',
                max: frames.length,
                min: 1,
                onChange: event => {
                  setPlaying(false)
                  setIndex(Number(event.target.value) - 1)
                },
                type: 'range',
                value: current + 1
              }),
              jsxs('button', {
                className: 'cs-b-link',
                onClick: () => {
                  if (!playing) {
                    setIndex(0)
                  }
                  setPlaying(!playing)
                },
                type: 'button',
                children: [jsx(Codicon, { name: playing ? 'debug-pause' : 'play', size: 12 }), playing ? 'Pause' : 'Replay frames']
              })
            ]
          }) : null
        ]
      })
    ]
  })
}
