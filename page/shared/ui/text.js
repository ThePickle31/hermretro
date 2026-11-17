// Text blocks: lede, small print and fact lists.
import { jsx } from '#sdk'

export function Lede({ children }) {
  return jsx('p', { className: 'cs-lede', children })
}

export function Small({ children, tone }) {
  return jsx('p', { className: tone === 'warn' ? 'cs-small cs-warn' : 'cs-small', children })
}

export function Facts({ rows }) {
  return jsx('dl', {
    className: 'cs-facts',
    children: rows.flatMap(([term, text]) => [jsx('dt', { children: term }, `t-${term}`), jsx('dd', { children: text }, `d-${term}`)])
  })
}
