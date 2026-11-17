// Commands from the Studio page (`{ cs: 'cmd', type }`, see #shared/player/protocol.js).
import { CMD, FROM_FRAME, TO_FRAME } from '#shared/player/protocol.js'
import { frameImage } from './crop.js'
import { chooseFinish, gameCanvas, press } from './engine.js'
import { post } from './post.js'
import { setView } from './view.js'

/** GB Studio's player globals, read defensively: the frame may run before or without them. */
const holdGame = held => {
  const { vm, Audio: sound } = /** @type {any} */ (globalThis)

  try {
    if (held && vm && !vm.paused) {
      vm.paused = true
      window.__hrHeld = true
    } else if (!held && vm && window.__hrHeld) {
      vm.paused = false
      window.__hrHeld = false
    }

    sound?.ctx?.[held ? 'suspend' : 'resume']?.()
  } catch {
    // the game has not started yet
  }
}

const setTheme = css => {
  let style = document.getElementById('hermes-theme')

  if (!style) {
    style = document.createElement('style')
    style.id = 'hermes-theme'
    document.head.append(style)
  }

  style.textContent = typeof css === 'string' ? css : ''
}

export function listenForCommands(annotate) {
  const handlers = {
    // Dispatched on the body: the player's handlers call target.closest and ignore keys aimed at its
    // own buttons, and the event still bubbles up to window where the game reads it.
    [CMD.KEY]: ({ key, code, down }) =>
      (document.body || document.documentElement).dispatchEvent(new KeyboardEvent(down ? 'keydown' : 'keyup', { key, code, bubbles: true, cancelable: true })),
    [CMD.SNAP]: ({ id }) => post({ cs: FROM_FRAME.SNAP, id, url: frameImage(gameCanvas()) }),
    [CMD.HOLD]: () => holdGame(true),
    [CMD.RELEASE]: () => holdGame(false),
    [CMD.THEME]: ({ css }) => setTheme(css),
    [CMD.VIEW]: ({ view }) => setView(view),
    [CMD.PRESS]: ({ action }) => press(action),
    [CMD.FINISH]: ({ id }) => chooseFinish(id),
    // Entering goes through the player's own button, so the engine freezes the frame and tracks it.
    [CMD.ANNOTATE]: ({ on }) => (on ? !annotate.isActive() && press('annotate') : annotate.setActive(false)),
    [CMD.MARK_COLOR]: ({ id, index, value }) => annotate.setColor(id, index, value),
    [CMD.MARK_REMOVE]: ({ id }) => annotate.removeMark(id),
    [CMD.MARKS_TAKE]: ({ id }) => annotate.takeMarks(id)
  }

  addEventListener('message', event => {
    const data = event.data

    if (event.source === parent && data && data.cs === TO_FRAME) {
      handlers[data.type]?.(data)
    }
  })

  addEventListener('focus', () => post({ cs: FROM_FRAME.FOCUS, value: true }))
  addEventListener('blur', () => post({ cs: FROM_FRAME.FOCUS, value: false }))
}
