// The HermRetro cartridge with a game's cover (or title screen) in its label: one button, used by the Games shelf
// and by Build's New Game shelf so the art and the label's fit stay one thing.
import { Codicon, jsx, jsxs } from '#sdk'

/** A cartridge button. `game` may be null (a game still being set up): the label then shows `title` and `note`.
 *  `play` adds the round play mark shown on hover; `label` is the button's accessible name. */
export function Cartridge({ game, title, note = null, label, disabled = false, play = false, onClick, className = '' }) {
  const thumb = game?.thumb ?? null

  return jsxs('button', {
    'aria-label': label ?? title,
    className: className ? `cs-cart ${className}` : 'cs-cart',
    disabled,
    onClick,
    type: 'button',
    children: [
      jsx(
        'span',
        {
          className: 'slot',
          children: thumb
            ? jsx('img', { alt: game.cover ? `${title} cover art` : `${title} title screen`, draggable: false, src: thumb })
            : jsxs('span', { className: 'ph', children: [title, note ? jsx('small', { children: note }, 'note') : null] })
        },
        'slot'
      ),
      thumb && !game.cover ? jsxs('span', { className: 'nocover', children: [jsx(Codicon, { name: 'sparkle', size: 9 }), 'No cover'] }, 'nocover') : null,
      play ? jsx('span', { className: 'hov', children: jsx('span', { children: jsx(Codicon, { name: 'play', size: 22 }) }) }, 'hov') : null
    ]
  })
}
