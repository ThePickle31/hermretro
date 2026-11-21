// Artwork drawn as masks in the accent colour: the Hermes bust and the flying Chromatic.
import { jsx, jsxs } from '#sdk'

/** The Hermes bust on empty pages and in onboarding. The image itself is a CSS variable on the page. */
export function Art() {
  return jsx('div', { 'aria-hidden': true, className: 'cs-art' })
}

/** The flying Chromatic beside every Setup step. Kept mounted by the Setup page, so a status poll
 *  never restarts its animation. */
export function Flyer() {
  const wing = side => jsx('div', { className: `wing ${side}`, children: jsx('div', { className: 'ink' }) }, side)

  return jsxs('div', {
    'aria-hidden': true,
    className: 'cs-flyer',
    children: [
      jsx('div', {
        className: 'drift',
        children: jsx('div', {
          className: 'lift',
          children: jsxs('div', {
            className: 'tilt',
            children: [wing('l'), wing('r'), jsx('div', { className: 'body', children: jsx('div', { className: 'ink' }) }, 'body')]
          })
        })
      }),
      jsx('div', { className: 'shadow' })
    ]
  })
}
