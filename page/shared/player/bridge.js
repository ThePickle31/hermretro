// The page's side of the player frame protocol (messages in ./protocol.js, contract in
// docs/dev/STUDIO-PAGES.md "Page ↔ frame messages"). In: focus, snaps, the player's state, marks while
// annotating, notes from the in-frame note card, logs. Out: keys, snap requests, hold/release, the app's
// colours, and the inline player's commands. Everything the frame sends is checked (./frame-values.js) before use.
import { useCallback, useEffect, useRef, useState } from '#sdk'
import { backgroundOf } from '#shared/ui/background.js'
import { cleanImage, cleanMarks, cleanNote } from './frame-values.js'
import { CMD, FROM_FRAME, TO_FRAME } from './protocol.js'

// Keys typed on the page (not inside the frame) still reach the game.
const GAME_KEYS = new Set(['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'z', 'Z', 'x', 'X', 'Enter', 'Shift', 'p', 'P'])
// Where a key keeps its own meaning: typing; Enter on any control (it presses it); arrows in tabs,
// radio groups and menus (they move between the choices).
const TYPING = 'input, textarea, select, [contenteditable]'
const CONTROL = 'button, a[href], [role=button], [role=tab], [role=radio], [role=menuitem], [role=menuitemradio]'
const ARROW_GROUP = '[role=tab], [role=radio], [role=menuitem], [role=menuitemradio]'

const IDLE = Object.freeze({ ready: false, paused: false, muted: false, annotating: false, recording: false })
const REPLY_MS = 2500

/** The app's colours where the frame sits: the background behind it (so the player's page looks part of the
 *  app, whatever finish the handheld is in), the text colour and the accent. */
function appColours(frame) {
  const style = getComputedStyle(frame)

  return { accent: style.getPropertyValue('--ui-accent').trim() || '#3d7bff', background: backgroundOf(frame.parentElement, getComputedStyle).css, ink: style.color }
}

/** The frame's theme: the accent for our overlay, and the app's background and text in place of the
 *  finish's own (the engine sets those on the body inline, so these need `!important`). */
function themeCss({ accent, background, ink }) {
  return `:root{--hr-accent:${accent}}body.codex-game-view-mounted{--cgv-background:${background}!important;--cgv-ink:${ink}!important}`
}

function keepsKey(event) {
  const target = event.target

  if (typeof target?.closest !== 'function') {
    return false
  }

  if (target.closest(TYPING)) {
    return true
  }

  return event.key === 'Enter' ? Boolean(target.closest(CONTROL)) : event.key.startsWith('Arrow') && Boolean(target.closest(ARROW_GROUP))
}

/**
 * `scopeRef`: when set (the page is shared with the chat), keys reach the game only after the user last
 * clicked inside that element, so arrows and Enter in the chat stay the chat's.
 * `frameKey`: changes whenever a new frame loads (or the frame goes away); the player's state starts over.
 * Returns { focused, frame, marks, snap, send, press, takeMarks }; `frame` is the player's state with
 * `press` attached, for the bar.
 */
export function usePlayerBridge({ ctx, frameRef, visible, onAnnotate = null, scopeRef = null, frameKey = null }) {
  const [focused, setFocused] = useState(false)
  const [state, setState] = useState(IDLE)
  const [marks, setMarks] = useState([])
  const replies = useRef(new Map())
  const sequence = useRef(0)
  const latest = useRef({})
  const armed = useRef(!scopeRef)
  // Keys sent down to the game, by key: their keyup always follows, so no key stays held in the game.
  const held = useRef(new Map())

  latest.current = { onAnnotate }

  const post = useCallback(message => {
    try {
      frameRef.current?.contentWindow?.postMessage(message, '*')
    } catch {
      // the frame is gone or still loading
    }
  }, [])

  const send = useCallback((type, payload = {}) => post({ cs: TO_FRAME, ...payload, type }), [])

  // The app's colours. Sent with every report of the player's state, so a frame that just loaded (its
  // first report) gets them too.
  const paint = useCallback(() => frameRef.current && send(CMD.THEME, { css: themeCss(appColours(frameRef.current)) }), [])

  const releaseKeys = useCallback(() => {
    for (const [key, code] of held.current) {
      send(CMD.KEY, { key, code, down: false })
    }

    held.current.clear()
  }, [])

  useEffect(() => {
    setState(IDLE)
    setMarks([])
    held.current.clear()
  }, [frameKey])

  useEffect(() => {
    if (!scopeRef) {
      return undefined
    }

    const arm = event => {
      armed.current = Boolean(scopeRef.current && event.target && scopeRef.current.contains(event.target))

      if (!armed.current) {
        releaseKeys()
      }
    }

    window.addEventListener('pointerdown', arm, true)
    window.addEventListener('focusin', arm, true)

    return () => {
      window.removeEventListener('pointerdown', arm, true)
      window.removeEventListener('focusin', arm, true)
    }
  }, [])

  /** Send `type` with a fresh id and resolve with the frame's reply, or `fallback` after `wait` ms. */
  const ask = useCallback(
    (type, fallback, wait = REPLY_MS) =>
      new Promise(resolve => {
        const id = ++sequence.current

        replies.current.set(id, resolve)
        send(type, { id })
        ctx.setTimeout(() => {
          if (replies.current.has(id)) {
            replies.current.delete(id)
            resolve(fallback)
          }
        }, wait)
      }),
    []
  )

  useEffect(() => {
    const answer = (id, value) => {
      const resolve = replies.current.get(id)

      if (resolve) {
        replies.current.delete(id)
        resolve(value)
      }
    }

    const handlers = {
      [FROM_FRAME.FOCUS]: data => setFocused(Boolean(data.value)),
      [FROM_FRAME.SNAP]: data => answer(data.id, cleanImage(data.url)),
      [FROM_FRAME.STATE]: data => {
        paint()
        setState({ ready: true, paused: Boolean(data.paused), muted: Boolean(data.muted), annotating: Boolean(data.annotating), recording: Boolean(data.recording) })
      },
      [FROM_FRAME.MARKS]: data => setMarks(cleanMarks(data.marks)),
      [FROM_FRAME.TAKEN]: data => answer(data.id, { image: cleanImage(data.image), marks: cleanMarks(data.marks) }),
      [FROM_FRAME.NOTE]: data => void latest.current.onAnnotate?.(cleanNote(data)),
      [FROM_FRAME.LOG]: data => data.level === 'error' && console.warn('[Chromatic player]', String(data.text ?? '').slice(0, 500))
    }

    const onMessage = event => {
      const frame = frameRef.current
      const data = event.data

      if (frame && event.source === frame.contentWindow && data && typeof data === 'object') {
        handlers[data.cs]?.(data)
      }
    }

    window.addEventListener('message', onMessage)

    return () => window.removeEventListener('message', onMessage)
  }, [])

  useEffect(() => {
    if (!visible) {
      return undefined
    }

    const forward = event => {
      const down = event.type === 'keydown'

      // A key that went down in the game comes up in the game, wherever focus is now.
      if (!down && held.current.has(event.key)) {
        held.current.delete(event.key)
        send(CMD.KEY, { key: event.key, code: event.code, down: false })

        return
      }

      if (!GAME_KEYS.has(event.key) || event.metaKey || event.ctrlKey || event.altKey || !frameRef.current || !armed.current || keepsKey(event)) {
        return
      }

      event.preventDefault()

      if (!event.repeat) {
        if (down) {
          held.current.set(event.key, event.code)
        }

        send(CMD.KEY, { key: event.key, code: event.code, down })
      }
    }

    window.addEventListener('keydown', forward)
    window.addEventListener('keyup', forward)
    window.addEventListener('blur', releaseKeys)

    return () => {
      window.removeEventListener('keydown', forward)
      window.removeEventListener('keyup', forward)
      window.removeEventListener('blur', releaseKeys)
      releaseKeys()
    }
  }, [visible])

  // The app's colours whenever the app's theme changes (Hermes marks it on the root element).
  useEffect(() => {
    if (typeof MutationObserver !== 'function') {
      return undefined
    }

    const observer = new MutationObserver(paint)

    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] })

    return () => observer.disconnect()
  }, [])

  // Leaving the page pauses the game and its sound; coming back resumes it (the frame stays loaded).
  const shown = useRef(visible)

  useEffect(() => {
    if (shown.current !== visible) {
      shown.current = visible
      send(visible ? CMD.RELEASE : CMD.HOLD)
    }
  }, [visible])

  const press = useCallback(action => send(CMD.PRESS, { action }), [])
  const snap = useCallback(() => ask(CMD.SNAP, ''), [])
  // Close-ups of every mark take longer than one snap.
  const takeMarks = useCallback(() => ask(CMD.MARKS_TAKE, null, 10_000), [])

  return { focused, frame: { ...state, press }, marks, snap, send, press, takeMarks }
}
