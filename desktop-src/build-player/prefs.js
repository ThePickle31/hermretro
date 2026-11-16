// The inline player's remembered choices: bare screen or Chromatic, scale, device finish, and whether
// the play-test panel starts open. Kept in the page's storage, the same for every game.
import { useCallback, useState } from '../sdk.js'
import { SCALES } from './scale.js'

const KEY = 'inlinePlayer'

/** The Hermes Edition finishes (adapter/player_server.py HERMES_COLORS), Midnight first. */
export const FINISHES = Object.freeze([
  { id: 'hermes-midnight', name: 'Midnight', swatch: '#15171c' },
  { id: 'hermes-blue', name: 'Nous Blue', swatch: '#0053fd' },
  { id: 'hermes-white', name: 'White', swatch: '#f2f5fc' },
  { id: 'hermes-clear', name: 'Clear Blue', swatch: '#cfdcff' }
])

const DEFAULTS = { view: 'screen', scale: 'fit', finish: FINISHES[0].id, panel: true }

function clean(saved) {
  const value = { ...DEFAULTS, ...(saved && typeof saved === 'object' ? saved : {}) }

  return {
    view: value.view === 'device' ? 'device' : 'screen',
    scale: SCALES.includes(value.scale) ? value.scale : 'fit',
    finish: FINISHES.some(finish => finish.id === value.finish) ? value.finish : DEFAULTS.finish,
    panel: value.panel !== false
  }
}

/** [prefs, update(partial)]. */
export function usePlayerPrefs(ctx) {
  const [prefs, setPrefs] = useState(() => clean(ctx.storage.get(KEY, null)))

  const update = useCallback(
    partial =>
      setPrefs(current => {
        const next = clean({ ...current, ...partial })

        ctx.storage.set(KEY, next)

        return next
      }),
    []
  )

  return [prefs, update]
}
