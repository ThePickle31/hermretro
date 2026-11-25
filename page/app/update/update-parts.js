// The pieces the update card and the update dialog share: the heading, the footer and its Update button, the wait line.
import { Button, Codicon, jsx, jsxs } from '#sdk'

/** The heading every update surface uses: eyebrow, title (its last words in the accent colour) and the versions. */
export function UpdateHead({ title, accent = null, from = null, to = null, onClose = null }) {
  return jsxs('div', {
    className: 'cs-upd-head',
    children: [
      jsx('p', { className: 'cs-eyebrow', children: 'hermretro' }),
      jsxs('h2', { className: 'cs-word', children: [title, accent ? jsx('span', { children: ` ${accent}` }) : null] }),
      from && to
        ? jsxs('div', { className: 'cs-upd-ver', children: [from, jsx(Codicon, { name: 'arrow-right', size: 12 }), jsx('b', { children: to })] })
        : null,
      onClose ? jsx('button', { 'aria-label': 'Close', className: 'cs-upd-x', onClick: onClose, type: 'button', children: jsx(Codicon, { name: 'close', size: 16 }) }) : null
    ]
  })
}

export const UpdateFoot = ({ children }) => jsx('div', { className: 'cs-upd-foot', children })
export const Fill = () => jsx('span', { className: 'cs-upd-fill' })

export function WaitLine({ text }) {
  return text ? jsxs('p', { className: 'cs-upd-wait', role: 'status', children: [jsx(Codicon, { name: 'clock', size: 13 }), text] }) : null
}

/** The Update button and what it says: Update, or Waiting… once the user asked while a build runs. Refused only for
 *  what does not finish by itself (a failed toolchain install). */
export function UpdateButton({ update }) {
  return update.queued
    ? jsx(Button, { disabled: true, size: 'sm', variant: 'default', children: 'Waiting…' })
    : jsx(Button, { disabled: Boolean(update.blocked) && !update.queueable, onClick: update.start, size: 'sm', variant: 'default', children: 'Update' })
}
