// The @ picker: the game's assets, mentioned in a message.
import { jsx, jsxs, useEffect, useState } from '#sdk'
import { useAsset } from '#pages/build/assets/cache.js'
import { SheetFrame } from '#pages/build/assets/images.js'
import { callStudioOnly } from '#app/backend.js'
import { AGENT } from '#app/ids.js'
import { RPC_ASSETS } from '#app/rpc.js'

export const MENTION_AT = /(^|\s)@([^\s@]{0,40})$/
export const later = fn => (typeof requestAnimationFrame === 'function' ? requestAnimationFrame(fn) : fn())
const MENTION_KIND = { cover: 'Game cover', sprite: 'Sprite', background: 'Background', ui: 'Interface', image: 'Image' }

/** The @ list: the game's pictures matching what was typed after @ (name or file name). */
export function MentionPicker({ items, query, index, onPick, onHover }) {
  return jsxs('div', {
    className: 'cs-b-mention',
    role: 'listbox',
    children: [
      jsxs('div', { className: 'cs-b-mention-head', children: [jsx('span', { className: 'cs-eyebrow', children: 'Assets' }), jsx('span', { className: 'cs-faint', children: items === null ? 'Loading…' : query ? `matching \u201c${query}\u201d` : `${items.length} in this game` })] }),
      items && items.length
        ? items.map((item, position) =>
            jsxs(
              'button',
              {
                'aria-selected': position === index,
                className: 'cs-b-mention-row',
                onClick: () => onPick(item),
                onMouseDown: event => event.preventDefault(),
                onMouseEnter: () => onHover(position),
                role: 'option',
                type: 'button',
                children: [jsx(AssetTile, { asset: { path: item.path, version: `list:${item.modifiedAt}` } }), jsx('b', { children: item.name }), jsx('span', { className: 'cs-faint', children: MENTION_KIND[item.kind] ?? 'Image' })]
              },
              item.path
            )
          )
        : items
          ? jsx('p', { className: 'cs-small cs-faint', children: query ? 'No asset matches that.' : `No pictures yet. They show up here as ${AGENT} draws them.` })
          : null
    ]
  })
}

/** The game's pictures from the backend, fetched again when `refresh` changes. `null` while loading,
 *  `false` when the backend cannot list them (an older one, or a game not in the library yet). */
export function useProjectAssets(gameId, refresh) {
  const [list, setList] = useState(null)

  useEffect(() => {
    if (!gameId) {
      setList(false)

      return undefined
    }

    let live = true

    callStudioOnly(RPC_ASSETS, { game: gameId }, 20_000)
      .then(answer => live && setList(answer?.ok && Array.isArray(answer.assets) ? answer.assets : false))
      .catch(() => live && setList(false))

    return () => {
      live = false
    }
  }, [gameId, refresh])

  return list
}

/** A picture as a tile (not a button: it sits inside one). */
function AssetTile({ asset, size = 'sm', animate = false }) {
  const { state, asset: loaded } = useAsset(asset.path, asset.version)

  return jsx('span', {
    'aria-hidden': true,
    className: `cs-b-th ${size}${state === 'loading' ? ' loading' : ''}`,
    children: state === 'ok' ? jsx(SheetFrame, { animate, loaded }) : null
  })
}
