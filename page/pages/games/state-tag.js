// A game's build state as a small tag.
import { jsx } from '#sdk'
import { GAME_STATES } from './model.js'

export function StateTag({ game }) {
  const [tone, label] = GAME_STATES[game.state] ?? GAME_STATES.unbuilt

  return jsx('span', { className: `cs-tag ${tone}`, children: label })
}
