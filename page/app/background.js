// Backgrounds behind pages. A page (or one state of it) shows one by rendering `jsx(Background, { id })` anywhere in
// its tree; the shell's layer (background-layer.js) draws it behind the page area. The newest one asked for is
// shown; a page switch that asks for the same id keeps it running instead of starting it again. The backgrounds
// themselves are folders in page/backgrounds/, listed in page/backgrounds/index.js.
import { useLayoutEffect } from '#sdk'

const asked = []
const listeners = new Set()

const changed = () => {
  for (const listener of listeners) listener()
}

/** The id of the background to show now, or null. */
export function wantedBackground() {
  return asked.length ? asked[asked.length - 1].id : null
}

/** Call `listener` whenever the wanted background may have changed; returns the unsubscribe. */
export function onBackgroundChange(listener) {
  listeners.add(listener)

  return () => listeners.delete(listener)
}

/** Shows background `id` behind the page while this is rendered. Asked before the page paints, so it never comes in late. */
export function Background({ id }) {
  useLayoutEffect(() => {
    const entry = { id }

    asked.push(entry)
    changed()

    return () => {
      asked.splice(asked.indexOf(entry), 1)
      changed()
    }
  }, [id])

  return null
}
