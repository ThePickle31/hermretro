// The game as it rests in the conversation: a frame with its screen at twice its size, under the newest build.
// Play opens the real player in its place.
import { Codicon, jsx, jsxs } from '#sdk'
import { AssetImage } from '#pages/build/assets/images.js'
import { AGENT } from '#app/ids.js'
import { Screen } from '#shared/ui/screen.js'

/** Whether the copy the player loads was made by ``build`` (its time is in seconds, the build's in milliseconds):
 *  a compile that only made a ROM leaves the player on an earlier build's copy. */
export function playsBuild(game, build) {
  const madeAt = (game?.web ?? game?.rom)?.builtAt
  return Boolean(build?.startAt && madeAt && madeAt * 1000 >= build.startAt - 2000)
}

export function PlayCard({ game, frame, state, note, build = null, onPlay }) {
  const ready = state === 'ready'
  const picture = frame
    ? jsx(AssetImage, { asset: frame, className: 'cs-b-pc-img', fallback: jsx(Screen, { className: 'cs-b-pc-img', game }) })
    : jsx(Screen, { className: 'cs-b-pc-img', game })

  return jsxs('div', {
    className: `cs-b-pc ${state}`,
    children: [
      jsxs('div', {
        className: 'cs-b-pc-stage',
        children: [
          jsx('button', {
            'aria-label': ready ? `Play ${game?.title ?? 'the game'}` : undefined,
            className: 'cs-b-pc-screen',
            disabled: !ready,
            onClick: onPlay,
            tabIndex: -1,
            type: 'button',
            children: picture
          }),
          ready
            ? jsxs('button', {
                className: 'cs-b-pc-go',
                onClick: onPlay,
                type: 'button',
                children: [jsx(Codicon, { name: 'play', size: 13 }), build ? `Play build #${build}` : 'Play']
              })
            : jsx('span', {
                className: 'cs-b-pc-wait',
                children: state === 'busy' ? `Playable again when ${AGENT} finishes` : 'The playable copy is not ready yet'
              })
        ]
      }),
      note && ready ? jsx('p', { className: 'cs-b-pc-note', children: note }) : null
    ]
  })
}
