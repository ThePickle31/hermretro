// Text blocks: heading, lede, small print and fact lists.
import { jsx } from '#sdk'

export function Heading({ children }) {
  return jsx('h2', { className: 'cs-word cs-title', children })
}

export function Lede({ children }) {
  return jsx('p', { className: 'cs-lede', children })
}

// Small print. `tone` takes only 'warn' (the warning colour); leave it out for plain small print. Any other value
// renders as plain small print, so tests/page/small-tone.test.mjs refuses one written in page/.
export function Small({ children, tone }) {
  return jsx('p', { className: tone === 'warn' ? 'cs-small cs-warn' : 'cs-small', children })
}

export function Facts({ rows }) {
  return jsx('dl', {
    className: 'cs-facts',
    children: rows.flatMap(([term, text]) => [jsx('dt', { children: term }, `t-${term}`), jsx('dd', { children: text }, `d-${term}`)])
  })
}
