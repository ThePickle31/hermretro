// A game's title screen (or cover) as a small Game Boy screen.
import { jsx } from '#sdk'

/** A game's title screen, or a plain stand-in until the player has saved one. */
export function Screen({ game, className = 'cs-screen' }) {
  return game?.thumb
    ? jsx('img', { alt: `${game.title} title screen`, className, src: game.thumb })
    : jsx('span', { 'aria-hidden': true, className: `${className} ph`, children: game?.title ?? '' })
}
