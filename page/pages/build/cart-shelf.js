// The New Game shelf: the games being worked on, standing as HermRetro cartridges on the floor of the attract level.
// A click opens that game's Build chat; the last tile lists the rest. The level takes no notice of the shelf (the
// Nous Girl walks behind it); it only keeps the ground under it flat (`data-at-flat`, read by attract/run.js).
import { jsx, jsxs, useEffect, useRef, useState } from '#sdk'
import { Cartridge } from '#pages/games/index.js'
import { statusMark } from './switcher.js'

const SLOT = 126 // one cartridge and its gap, in px
const MIN_HEIGHT = 560 // a shorter New Game area shows no shelf: the form needs the room

/** Newest work first: games waiting for an answer, then New Game chats still being set up (the latest started
 *  first: by `createdAt`, and one started this visit before the library knows it), then the rest in the library's
 *  own order (the games RPC lists the most recently changed game first). `entries` come from switcherEntries. */
export function shelfOrder(entries) {
  const rank = entry => (entry.state?.waiting ? 0 : entry.pending ? 1 : 2)
  const started = entry => (entry.pending ? (entry.pending.createdAt ?? Infinity) : 0)

  return entries
    .map((entry, index) => ({ entry, index }))
    .sort((a, b) => rank(a.entry) - rank(b.entry) || started(b.entry) - started(a.entry) || a.index - b.index)
    .map(item => item.entry)
}

/** The line under the name on a label with no picture, as on the Games shelf: why there is none yet. */
export function labelNote(game) {
  if (!game) {
    return 'Being set up'
  }

  return game.state === 'unbuilt' || game.state === 'failed' ? 'No build yet' : 'Title screen after first play'
}

/** How many cartridges fit `width` px, keeping one place for the All games tile when anything is left over. */
export function shelfFit(width, count, more) {
  const slots = Math.max(1, Math.floor((width + 26) / SLOT))

  return count + (more ? 1 : 0) <= slots ? count : Math.max(0, slots - 1)
}

/** `entries`: the games being worked on (switcherEntries); `others`: library games with no chat. */
export function CartShelf({ entries, others, onSelect, onAll }) {
  const box = useRef(null)
  const [room, setRoom] = useState({ width: 5 * SLOT, height: MIN_HEIGHT })

  useEffect(() => {
    const area = box.current?.parentElement

    if (!area || typeof ResizeObserver !== 'function') {
      return undefined
    }

    const measure = () => setRoom({ width: Math.min(area.clientWidth - 48, 8 * SLOT), height: area.clientHeight })
    const watch = new ResizeObserver(measure)

    watch.observe(area)
    measure()

    return () => watch.disconnect()
  }, [])

  const order = shelfOrder(entries)

  if (!order.length || room.height < MIN_HEIGHT) {
    return jsx('div', { 'aria-hidden': true, className: 'cs-b-shelf-probe', ref: box })
  }

  const shown = order.slice(0, shelfFit(room.width, order.length, others.length > 0))
  const left = order.length - shown.length + others.length

  return jsxs('nav', {
    'aria-label': 'Your games',
    className: 'cs-b-shelf',
    'data-at-flat': '',
    ref: box,
    children: [
      ...shown.map(entry =>
        jsxs(
          'div',
          {
            className: `cs-b-shelf-cart${entry.state?.waiting ? ' wait' : ''}`,
            children: [
              jsx(Cartridge, {
                game: entry.game,
                label: `${entry.title}, ${entry.sub}`,
                note: labelNote(entry.game),
                onClick: () => onSelect(entry.key),
                title: entry.title
              }),
              jsxs('span', { className: 'cap', children: [jsx('b', { title: entry.title, children: entry.title }), jsxs('small', { children: [statusMark(entry.state), entry.sub] })] })
            ]
          },
          entry.key
        )
      ),
      left
        ? jsxs(
            'div',
            {
              className: 'cs-b-shelf-cart all',
              children: [
                jsx('button', {
                  'aria-label': `All games: ${left} more`,
                  className: 'cs-b-shelf-more',
                  onClick: () => onAll(order.length > shown.length ? 'menu' : 'library'),
                  type: 'button',
                  children: `+${left}`
                }),
                jsxs('span', { className: 'cap', children: [jsx('b', { children: 'All games' }), jsx('small', { children: others.length ? 'With your library' : 'Being worked on' })] })
              ]
            },
            'all'
          )
        : null
    ]
  })
}
