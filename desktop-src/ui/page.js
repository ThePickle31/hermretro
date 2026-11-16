// Pieces every page uses: head, footer and a button for async actions.
import { Button, Codicon, jsx, jsxs, Tip, useState } from '../sdk.js'
import { LINKS } from '../core/ids.js'
import { ExternalLink } from './links.js'
import { Lede } from './text.js'

export function Footer({ ctx }) {
  return jsxs('footer', {
    className: 'cs-foot',
    children: [
      jsxs('div', {
        className: 'cs-row',
        style: { gap: 16 },
        children: [
          jsx(ExternalLink, { ctx, href: LINKS.quickstart, children: 'ModRetro Chromatic quickstart' })
        ]
      }),
      jsx('p', {
        className: 'cs-faint',
        children:
          'For original, user-created ROMs only. Do not use it for piracy or commercial games. Developer Mode is at your own risk. hermretro is an independent plugin and is not made or endorsed by ModRetro.'
      })
    ]
  })
}

export function PageHead({ number, label, title, lede, children }) {
  return jsxs('div', {
    className: 'cs-page-head',
    children: [
      jsxs('div', {
        className: 'cs-col',
        children: [
          label ? jsxs('p', { className: 'cs-eyebrow', children: [jsx('span', { className: 'cs-accent', children: number }), label] }) : null,
          jsx('h2', { className: 'cs-word cs-title', children: title }),
          lede ? jsx(Lede, { children: lede }) : null
        ]
      }),
      children ? jsx('div', { className: 'cs-row', children }) : null
    ]
  })
}

/** A button that runs an async action once at a time. */
export function AsyncButton({ run, disabled, icon, title, variant = 'outline', children }) {
  const [pending, setPending] = useState(false)

  return jsx(Tip, {
    label: title ?? children,
    children: jsx('span', {
      style: { display: 'inline-flex' },
      children: jsxs(Button, {
        disabled: disabled || pending,
        onClick: async () => {
          setPending(true)

          try {
            await run()
          } finally {
            setPending(false)
          }
        },
        size: 'sm',
        variant,
        'aria-label': icon && typeof children === 'string' ? children : undefined,
        children: [icon ? jsx(Codicon, { name: pending ? 'loading' : icon, size: 14, spinning: pending }) : null, icon ? jsx('span', { className: 'cs-lbl', children }) : children]
      })
    })
  })
}
