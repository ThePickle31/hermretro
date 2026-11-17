// Annotate in the inline player. The frame does the engine work and reports the marked objects; this
// hook keeps the user's note per mark and turns "Add to message" into composer attachments: one chip
// per object with its close-up, and the hardware details sent with the message.
import { host, useCallback, useEffect, useState } from '#sdk'
import { attachToBuild } from '#pages/build/composer/composer.js'
import { saveCapture } from '#app/player/capture.js'
import { CMD } from '#shared/player/protocol.js'
import { targetKind, targetLabel, targetRect } from '#shared/player/targets.js'

export function useAnnotate(bridge) {
  const [notes, setNotes] = useState({})
  const active = bridge.frame.annotating

  useEffect(() => {
    if (!active) {
      setNotes({})
    }
  }, [active])

  return {
    active,
    marks: active ? bridge.marks : [],
    notes,
    setNote: useCallback((id, text) => setNotes(current => ({ ...current, [id]: text })), []),
    start: () => bridge.send(CMD.ANNOTATE, { on: true }),
    cancel: () => bridge.send(CMD.ANNOTATE, { on: false }),
    setColor: (id, index, value) => bridge.send(CMD.MARK_COLOR, { id, index, value }),
    remove: id => bridge.send(CMD.MARK_REMOVE, { id })
  }
}

/** "at 84, 36 · 16 × 16" on the 160 × 144 screen. */
export function markPosition(metadata) {
  const rect = targetRect(metadata)

  return rect ? `at ${rect.x}, ${rect.y} \u00b7 ${rect.w} \u00d7 ${rect.h}` : ''
}

/** What HermRetro is told about one mark, besides the user's note. */
function markDetail(mark, framePath, build) {
  const changed = (mark.colors ?? []).some((color, index) => color !== mark.original?.[index])
  const parts = [
    `Marked ${mark.n}: ${mark.name} (${targetKind(mark.role)})${framePath ? ` on the frame ${framePath}` : ''}${build ? `, build #${build}` : ''}.`,
    mark.metadata?.Hardware ? `Hardware: ${mark.metadata.Hardware}.` : null,
    mark.metadata?.Build ? `${mark.metadata.Build}.` : null,
    changed ? `The user previewed new colours for it: ${mark.original.join(' ')} \u2192 ${mark.colors.join(' ')}.` : null
  ]

  return parts.filter(Boolean).join(' ')
}

/** Done: take the marks from the frame, save the frame, and put chips and numbered notes in the composer. */
export async function sendMarks({ bridge, game, stored, build, notes }) {
  const taken = await bridge.takeMarks()

  if (!taken) {
    host.notify({ kind: 'warning', message: 'The game did not hand over the marks in time. Mark them again, then Add to message.' })

    return
  }

  if (!taken.marks.length) {
    return
  }

  const { path, failure } = await saveCapture(game, taken.image)
  // The saved frame's path is unique per take; without one, the time is.
  const take = path || String(Date.now())
  const attachments = taken.marks.map(mark => ({
    key: `mark:${take}:${mark.n}`,
    path: path ?? '',
    name: `${mark.n} \u00b7 ${targetLabel(mark.name, mark.role)}`,
    image: mark.image,
    detail: markDetail(mark, path, build)
  }))
  const text = taken.marks.map(mark => `${mark.n}. ${(notes[mark.id] ?? '').trim()}`).join('\n')

  attachToBuild(stored, attachments, text)

  if (failure) {
    host.notify({ kind: 'warning', message: `The frame was not saved: ${failure}` })
  }
}
