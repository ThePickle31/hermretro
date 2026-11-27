// The parts of ModRetro's player view (engine src/web-annotations/view.js) the frame reads and
// drives: its root element, its own buttons (by `data-action`) and the state it shows on the root.
import { FROM_FRAME, PRESSABLE } from '#shared/player/protocol.js'
import { post } from './post.js'

const ROOT = '.codex-game-view'

const playerRoot = () => document.querySelector(ROOT)

/** The game's canvas, once GB Studio's player has created it. */
export const gameCanvas = () => document.querySelector('#mainCanvas')

/** Press one of the player's own buttons, as the user would. */
export function press(action) {
  if (!PRESSABLE.includes(action)) {
    return false
  }

  const button = playerRoot()?.querySelector(`[data-action="${action}"]`)

  if (!button || button.disabled) {
    return false
  }

  button.click()

  return true
}

/** Show the handheld in finish `id` through the player's own colour rail (hidden in the inline UI). */
export function chooseFinish(id) {
  const swatch = /^[a-z0-9-]{1,40}$/.test(String(id)) ? playerRoot()?.querySelector(`[data-device-color="${id}"]`) : null

  swatch?.click()

  return Boolean(swatch)
}

function readState(root) {
  const indicator = root.querySelector('.cgv-record-indicator')

  return {
    ready: true,
    paused: root.dataset.paused === 'true',
    muted: root.dataset.muted === 'true',
    annotating: root.dataset.annotating === 'true',
    recording: Boolean(indicator && !indicator.hidden)
  }
}

/** Report the player's state to the page now and whenever it changes. The view is created after the
 *  game boots, so this waits for its root first. */
export function watchState() {
  let last = ''

  const report = root => {
    const state = readState(root)
    const key = JSON.stringify(state)

    if (key !== last) {
      last = key
      post({ cs: FROM_FRAME.STATE, ...state })
    }
  }

  const watch = root => {
    const observer = new MutationObserver(() => report(root))

    // One call: observing the same node twice replaces the first options. `hidden` is the record badge.
    observer.observe(root, { subtree: true, attributes: true, attributeFilter: ['data-paused', 'data-muted', 'data-annotating', 'hidden'] })
    report(root)
  }

  const existing = playerRoot()

  if (existing) {
    watch(existing)

    return
  }

  const waiting = new MutationObserver(() => {
    const root = playerRoot()

    if (root) {
      waiting.disconnect()
      watch(root)
    }
  })

  waiting.observe(document.documentElement, { childList: true, subtree: true })
}
