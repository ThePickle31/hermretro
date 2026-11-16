// The "working" line with its looping mark.
import { jsx, jsxs } from '../sdk.js'

const LEMNISCATE = 'M0 0C.35-.6 1.15-.6 1.15 0S.35.6 0 0-1.15-.6-1.15 0-.35.6 0 0Z'

/** The long-operation loader, after the app's own lemniscate. */
export function Working({ children, quiet = false }) {
  return jsxs('div', {
    className: quiet ? 'cs-watch quiet' : 'cs-watch',
    role: 'status',
    children: [
      jsxs('svg', {
        'aria-hidden': true,
        className: 'cs-lem',
        viewBox: '-1.25 -0.62 2.5 1.24',
        children: [
          jsx('path', { className: 'track', d: LEMNISCATE, pathLength: 100 }),
          jsx('path', { className: 'run', d: LEMNISCATE, pathLength: 100 })
        ]
      }),
      jsx('span', { children })
    ]
  })
}
