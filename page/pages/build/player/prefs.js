// The inline player's remembered choices: bare screen or Chromatic, scale, device skin (one of the `player`
// RPC's `skins`, from player/skins/), and whether the play-test panel starts open. Kept in the page's storage, the same for every game.
import { useCallback, useState } from '#sdk'
import { SCALES } from './scale.js'

const KEY = 'inlinePlayer'

const DEFAULTS = { view: 'screen', scale: 'fit', finish: '', panel: true }

function clean(saved) {
  const value = { ...DEFAULTS, ...(saved && typeof saved === 'object' ? saved : {}) }

  return {
    view: value.view === 'device' ? 'device' : 'screen',
    scale: SCALES.includes(value.scale) ? value.scale : 'fit',
    finish: /^[a-z0-9-]{1,40}$/.test(String(value.finish)) ? value.finish : DEFAULTS.finish,
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
