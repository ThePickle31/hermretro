// What the inline player shows while annotating: the bar (what is happening, Cancel, Add to message)
// and the panel listing each marked object with its close-up, its colours (change one to preview it
// on the frozen frame) and a note for HermRetro.
import { Codicon, jsx, jsxs, useRef } from '../sdk.js'
import { AGENT } from '../core/ids.js'
import { targetLabel } from '../player/targets.js'
import { markPosition } from './annotate.js'
import { BarButton } from './control-bar.js'

export function AnnotateBar({ title, count, busy, onCancel, onDone }) {
  return jsxs('div', {
    className: 'cs-ip-bar annotating',
    children: [
      jsx('span', { className: 'cs-ip-ann-ic', children: jsx(Codicon, { name: 'inspect', size: 14 }) }),
      jsx('b', { className: 'cs-ip-title', children: `Annotating ${title}` }),
      jsx('span', { className: count ? 'cs-ip-hint marked' : 'cs-faint cs-ip-hint', children: count ? `${count} marked` : 'click a sprite or tile \u00b7 Esc to finish' }),
      jsx('span', { className: 'cs-grow' }),
      jsx(BarButton, { icon: 'close', label: 'Cancel and let the game run', onClick: onCancel, text: 'Cancel' }),
      jsx(BarButton, { disabled: !count || busy, icon: 'arrow-right', label: 'Add the marks to your message', onClick: onDone, primary: true, text: 'Add to message' })
    ]
  })
}

/** Colour swatches; each opens the system colour picker and previews the pick on the frozen frame. */
function Colors({ mark, onColor }) {
  const pending = useRef(null)

  // Picker drags fire many events; send at most one per frame.
  const preview = (index, value) => {
    const first = pending.current === null

    pending.current = { index, value }

    if (first) {
      requestAnimationFrame(() => {
        const { index: at, value: color } = pending.current

        pending.current = null
        onColor(mark.id, at, color)
      })
    }
  }

  const changed = (mark.colors ?? []).some((color, index) => color !== mark.original?.[index])

  return jsxs('div', {
    className: 'cs-ip-colors',
    children: [
      ...(mark.colors ?? []).map((color, index) =>
        jsxs(
          'label',
          {
            className: color !== mark.original?.[index] ? 'cs-ip-swatch-in changed' : 'cs-ip-swatch-in',
            title: `Colour ${index + 1}: ${color}`,
            children: [jsx('i', { style: { background: color } }), jsx('input', { 'aria-label': `Colour ${index + 1}`, onChange: event => preview(index, event.target.value), type: 'color', value: color })]
          },
          index
        )
      ),
      changed
        ? jsx('button', {
            className: 'cs-b-link',
            onClick: () => mark.colors.forEach((color, index) => color !== mark.original[index] && onColor(mark.id, index, null)),
            type: 'button',
            children: 'Reset'
          })
        : null
    ]
  })
}

function MarkCard({ mark, note, onNote, onColor, onRemove }) {
  return jsxs('li', {
    className: 'cs-ip-mark',
    children: [
      jsxs('div', {
        className: 'cs-ip-mark-head',
        children: [
          jsx('span', { className: 'cs-ip-n', children: mark.n }),
          mark.image ? jsx('img', { alt: '', className: 'cs-ip-crop', src: mark.image }) : null,
          jsxs('div', { className: 'cs-ip-mark-name', children: [jsx('b', { children: targetLabel(mark.name, mark.role) }), jsx('span', { className: 'cs-faint', children: markPosition(mark.metadata) })] }),
          jsx('button', { 'aria-label': `Remove mark ${mark.n}`, className: 'cs-b-x', onClick: () => onRemove(mark.id), type: 'button', children: jsx(Codicon, { name: 'close', size: 12 }) })
        ]
      }),
      mark.colors?.length ? jsx(Colors, { mark, onColor }) : null,
      jsx('textarea', {
        'aria-label': `What should change about mark ${mark.n}`,
        className: 'cs-ip-mark-note',
        onChange: event => onNote(mark.id, event.target.value),
        // Keys typed here are the note's, not the game's.
        onKeyDown: event => event.stopPropagation(),
        placeholder: 'What should change here?',
        rows: 2,
        value: note ?? ''
      })
    ]
  })
}

export function AnnotatePanel({ layout, annotate }) {
  return jsxs('aside', {
    'aria-label': 'Marked in the game',
    className: layout === 'side' ? 'cs-ip-panel' : 'cs-ip-panel tabs',
    children: [
      jsx('div', { className: 'cs-ip-sh', children: jsx('span', { children: annotate.marks.length ? `Marked ${annotate.marks.length}` : 'Annotate' }) }),
      annotate.marks.length
        ? jsx('ol', {
            className: 'cs-ip-marks',
            children: annotate.marks.map(mark =>
              jsx(MarkCard, { mark, note: annotate.notes[mark.id], onColor: annotate.setColor, onNote: annotate.setNote, onRemove: annotate.remove }, mark.id)
            )
          })
        : jsx('p', { className: 'cs-ip-note', children: `The game is frozen. Click a sprite or a tile to mark it; each one gets a number and a note for ${AGENT}. Change its colours here to try them on the frozen frame.` })
    ]
  })
}
