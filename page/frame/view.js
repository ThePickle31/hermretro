// Which UI the frame shows: ModRetro's whole player (`full`) or the inline player's bare `screen` or
// `device`, chosen by `?view=` when the frame loads and switched later without reloading the game.
import { VIEWS } from '#shared/player/protocol.js'
import { FRAME_CSS } from './view.css.js'

const html = document.documentElement

/** Add the frame's styles once the document has a head. */
export function installStyles() {
  const add = () => {
    const style = document.createElement('style')

    style.id = 'hr-frame'
    style.textContent = FRAME_CSS
    document.head.append(style)
  }

  if (document.head) {
    add()
  } else {
    addEventListener('DOMContentLoaded', add, { once: true })
  }
}

/** Show one of VIEWS. `full` drops the inline UI; the others turn it on. */
export function setView(view) {
  if (!VIEWS.includes(view)) {
    return
  }

  if (view === 'full') {
    delete html.dataset.hrUi
    delete html.dataset.hrView
  } else {
    html.dataset.hrUi = 'inline'
    html.dataset.hrView = view
  }

  dispatchEvent(new Event('resize'))
}

export const inlineUi = () => html.dataset.hrUi === 'inline'
