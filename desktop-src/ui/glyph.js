// Status glyphs and chips.
import { jsx, jsxs } from '../sdk.js'
import { C } from '../styles/tokens.js'

export const INDICATOR = {
  done: { icon: 'pass-filled', color: C.good, label: 'Done' },
  todo: { icon: 'circle-large-outline', color: C.warn, label: 'To do' },
  optional: { icon: 'circle-large-outline', color: C.quaternary, label: 'Optional' },
  waiting: { icon: 'circle-large-outline', color: C.quaternary, label: 'Waiting' },
  checking: { icon: 'loading', color: C.tertiary, label: 'Checking', spinning: true },
  error: { icon: 'error', color: C.bad, label: 'Problem' },
  skipped: { icon: 'dash', color: C.quaternary, label: 'Skipped' },
  blocked: { icon: 'circle-slash', color: C.warn, label: 'Not available' }
}

/** A step's state as a small square: filled when done, dashed while checking. */
export function Glyph({ state }) {
  const label = (INDICATOR[state] ?? INDICATOR.waiting).label
  const ink = 'var(--background, var(--ui-bg-editor))'
  let shape

  if (state === 'done') {
    shape = [
      jsx('rect', { fill: C.good, height: 12, width: 12, x: 1, y: 1 }, 'box'),
      jsx('path', { d: 'M4 7.2l2 2 4-4.4', fill: 'none', stroke: ink, strokeWidth: 1.6 }, 'tick')
    ]
  } else if (state === 'error') {
    shape = [
      jsx('rect', { fill: C.bad, height: 12, width: 12, x: 1, y: 1 }, 'box'),
      jsx('path', { d: 'M7 4v4M7 9.6v.8', stroke: ink, strokeWidth: 1.6 }, 'mark')
    ]
  } else if (state === 'checking') {
    shape = jsx('rect', {
      className: 'cs-dash',
      fill: 'none',
      height: 11,
      stroke: 'var(--ui-accent)',
      strokeDasharray: '3 2',
      strokeWidth: 1.4,
      width: 11,
      x: 1.5,
      y: 1.5
    })
  } else if (state === 'skipped') {
    shape = jsx('path', { d: 'M3 7h8', stroke: C.quaternary, strokeWidth: 1.4 })
  } else {
    shape = [
      jsx('rect', {
        fill: 'none',
        height: 11,
        stroke: state === 'blocked' ? C.warn : state === 'todo' ? C.tertiary : C.quaternary,
        strokeWidth: 1.2,
        width: 11,
        x: 1.5,
        y: 1.5
      }, 'box'),
      state === 'blocked' ? jsx('path', { d: 'M4 10l6-6', stroke: C.warn, strokeWidth: 1.2 }, 'slash') : null
    ]
  }

  return jsx('svg', { 'aria-label': label, className: 'cs-glyph', height: 14, role: 'img', viewBox: '0 0 14 14', width: 14, children: shape })
}

export function Chip({ tone = '', children }) {
  return jsxs('span', { className: `cs-chip ${tone}`, children: [jsx('i', {}), children] })
}
