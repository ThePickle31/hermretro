// The host side of the engine's annotate feature (`document.oai.annotation`, which the engine's
// dist/web-annotations/native.js looks for). The engine does the work: it freezes the frame, reads
// every sprite and tile from the emulator (hit test), names them, and previews colour changes on the
// frozen frame. This file is only the host: pointer handling, our overlay, the marks, and messages
// to the page.
//
// Two ways to finish, chosen by the page's UI:
//  - inline (the Build page's player): any number of marks; the page lists them with their colours
//    and asks for them with MARKS_TAKE when the user is done;
//  - full (Emulator page, the tab beside the chat): one pick and an in-frame note card, sent as NOTE.
import { FROM_FRAME } from '../player/protocol.js'
import { closeUp, frameImage } from './crop.js'
import { openNoteCard } from './note-card.js'
import { boxIn, createOverlay } from './overlay.js'
import { post } from './post.js'
import { inlineUi } from './view.js'

const SURFACE_ID = 'hermretro'
const clone = value => {
  try {
    return JSON.parse(JSON.stringify(value ?? null))
  } catch {
    return null
  }
}

export function installAnnotateHost() {
  let surface = null
  let active = false
  let overlay = null
  let hovered = null
  let marks = []
  let selectedId = null

  const announce = on => document.dispatchEvent(new CustomEvent('oaiannotationmodechange', { detail: { active: on } }))

  /** The marks as the page shows them, each with a close-up of the frozen frame (colour preview included). */
  const describeMarks = () =>
    marks.map(({ n, id, name, role, metadata, colors, original, box }) => ({ n, id, name, role, metadata, colors, original, image: closeUp(surface?.element, box) }))

  const publish = () => post({ cs: FROM_FRAME.MARKS, marks: describeMarks() })

  const draw = () => overlay?.draw({ hovered, marks, selectedId })

  /** Make `id` the engine's selected target: it answers with that target's colours (onControls). */
  const select = id => {
    selectedId = id

    try {
      surface?.renderSelection?.({ selectedId: id, hoveredId: null })
    } catch {
      // a detached surface draws nothing
    }

    draw()
  }

  const hit = event => {
    try {
      const target = surface?.hitTest({ clientX: event.clientX, clientY: event.clientY })

      return target?.rect ? { ...target, box: boxIn(target.rect, overlay.bounds()) } : null
    } catch {
      return null
    }
  }

  const finishWithNote = (target, note) => {
    post({
      cs: FROM_FRAME.NOTE,
      target: { name: target.name, role: target.role, metadata: clone(target.metadata) },
      note,
      image: frameImage(surface?.element)
    })
    setActive(false)
  }

  const onDown = event => {
    const target = hit(event)

    if (!target) {
      return
    }

    hovered = null

    if (!inlineUi()) {
      const cancel = () => {
        marks = []
        select(null)
      }

      marks = [{ ...target, n: 1, colors: null, original: null }]
      select(target.id)
      openNoteCard(overlay, target, { onAsk: note => finishWithNote(target, note), onCancel: cancel })

      return
    }

    if (!marks.some(mark => mark.id === target.id)) {
      marks = [...marks, { ...target, n: marks.length + 1, metadata: clone(target.metadata), colors: null, original: null }]
    }

    select(target.id)
    publish()
  }

  const onMove = event => {
    const next = hit(event)

    if (next?.id !== hovered?.id) {
      hovered = next
      draw()
    }
  }

  function setActive(on) {
    if (active === on || (on && !surface)) {
      return
    }

    active = on
    hovered = null
    marks = []
    selectedId = null
    overlay?.remove()
    overlay = on ? createOverlay(surface.element, { tip: inlineUi() ? null : 'Click a thing in the game \u00b7 Esc to finish', onDown, onMove }) : null
    draw()

    if (inlineUi()) {
      publish()
    }

    announce(on)
  }

  /** The engine reports the selected target's colours (and again after each preview). */
  const onControls = controls => {
    const mark = marks.find(entry => entry.id === selectedId)

    if (!mark || !Array.isArray(controls)) {
      return
    }

    mark.colors = controls.map(control => control.currentValue)
    mark.original ??= [...mark.colors]
    publish()
  }

  /** Preview a colour on a mark (value null puts its original colour back). */
  const setColor = (id, index, value) => {
    const mark = marks.find(entry => entry.id === id)
    const original = mark?.original?.[index]

    if (!mark || !original || !surface?.element) {
      return
    }

    select(id)
    surface.element.dispatchEvent(
      new CustomEvent('oaiannotationcontrolchange', {
        detail: {
          action: value ? 'preview' : 'reset',
          callback: `palette-${index}`,
          value: value || original,
          virtualTarget: { surfaceId: SURFACE_ID, targetId: id }
        }
      })
    )
  }

  const removeMark = id => {
    marks = marks.filter(mark => mark.id !== id).map((mark, index) => ({ ...mark, n: index + 1 }))
    select(marks.at(-1)?.id ?? null)
    publish()
  }

  /** Hand the marks to the page with close-ups and the whole frame, then let the game run again. */
  const takeMarks = id => {
    post({ cs: FROM_FRAME.TAKEN, id, image: frameImage(surface?.element), marks: describeMarks() })
    setActive(false)
  }

  addEventListener(
    'keydown',
    event => {
      if (active && event.key === 'Escape') {
        event.stopPropagation()
        setActive(false)
      }
    },
    true
  )

  document.oai = Object.assign(document.oai || {}, {
    annotation: {
      registerSurface(options) {
        surface = options

        return {
          dispose() {
            if (surface === options) {
              setActive(false)
              surface = null
            }
          },
          invalidate() {
            overlay?.place()
            draw()
          }
        }
      },
      registerControls() {
        return { update: state => onControls(state?.controls), dispose() {} }
      },
      isActive: () => active,
      toggle(on) {
        if (!surface) {
          return { accepted: false }
        }

        setTimeout(() => setActive(Boolean(on)))

        return { accepted: true }
      },
      request() {
        if (!surface) {
          return { accepted: false }
        }

        setTimeout(() => setActive(true))

        return { accepted: true }
      }
    }
  })

  return { setActive, setColor, removeMark, takeMarks, isActive: () => active }
}
