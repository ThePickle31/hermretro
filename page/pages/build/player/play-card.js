// The game as a resting card in the conversation.
import { Button, Codicon, jsx, jsxs } from '#sdk'
import { AssetImage } from '#pages/build/assets/images.js'
import { AGENT } from '#app/ids.js'
import { ago } from '#app/time.js'
import { Screen } from '#shared/ui/screen.js'

export function PlayCard({ game, frame, state, note, onPlay, onOpenAsset }) {
  const ready = state === 'ready'
  const builtAt = game?.web?.builtAt ?? game?.rom?.builtAt ?? null

  return jsxs('div', {
    className: `cs-b-pc ${state}`,
    children: [
      jsxs('button', {
        'aria-label': ready ? `Play ${game?.title ?? 'the game'}` : undefined,
        className: 'cs-b-pc-screen',
        disabled: !ready,
        onClick: onPlay,
        type: 'button',
        children: [
          frame ? jsx(AssetImage, { asset: frame, className: 'cs-b-pc-img', fallback: jsx(Screen, { className: 'cs-b-pc-img', game }) }) : jsx(Screen, { className: 'cs-b-pc-img', game }),
          ready ? jsx('span', { 'aria-hidden': true, className: 'cs-b-pc-go', children: jsx(Codicon, { name: 'play', size: 18 }) }) : null
        ]
      }),
      jsxs('div', {
        className: 'cs-b-pc-info',
        children: [
          jsx('b', { children: game?.title ?? 'Your game' }),
          jsx('small', {
            children:
              state === 'busy'
                ? `Playable again when ${AGENT} finishes`
                : state === 'unplayable'
                  ? 'The playable copy is not ready yet'
                  : builtAt
                    ? `Built ${ago(builtAt, Date.now())}`
                    : 'Ready to play'
          }),
          note && ready ? jsx('span', { className: 'cs-b-pc-note', children: note }) : null
        ]
      }),
      jsxs(Button, { disabled: !ready, onClick: onPlay, size: 'sm', children: [jsx(Codicon, { name: 'play', size: 13 }), 'Play'] })
    ]
  })
}
