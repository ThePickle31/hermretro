// A small popover menu for the player bar (⋯ and the device finish): opens under its button with the
// first choice focused, arrows move between choices, and it closes on a pick, Escape, Tab or a click
// elsewhere (Escape and a pick hand focus back to the button).
import { Codicon, jsx, jsxs, useEffect, useRef, useState } from '../sdk.js'
import { moveFocus } from './arrow-keys.js'

const ITEM = '[role^=menuitem]'

/** `items`: [{ id, label, icon?, swatch?, checked?, disabled? }]; `onPick(id)`. */
export function BarMenu({ label, icon, text = null, items, onPick, disabled = false }) {
  const [open, setOpen] = useState(false)
  const root = useRef(null)
  const trigger = useRef(null)
  const close = (refocus = true) => {
    setOpen(false)

    if (refocus) {
      trigger.current?.focus()
    }
  }

  useEffect(() => {
    if (!open) {
      return undefined
    }

    const away = event => {
      if (!root.current?.contains(event.target)) {
        setOpen(false)
      }
    }
    const escape = event => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        close()
      }
    }

    root.current?.querySelector(ITEM)?.focus()
    window.addEventListener('pointerdown', away, true)
    window.addEventListener('keydown', escape, true)

    return () => {
      window.removeEventListener('pointerdown', away, true)
      window.removeEventListener('keydown', escape, true)
    }
  }, [open])

  return jsxs('span', {
    className: 'cs-ip-menu',
    ref: root,
    children: [
      jsxs('button', {
        'aria-expanded': open,
        'aria-haspopup': 'menu',
        'aria-label': label,
        className: 'cs-ip-btn',
        disabled,
        onClick: () => setOpen(!open),
        ref: trigger,
        title: label,
        type: 'button',
        children: [jsx(Codicon, { name: icon, size: 14 }), text ? jsx('span', { className: 'cs-ip-lbl', children: text }) : null]
      }),
      open
        ? jsx('div', {
            className: 'cs-ip-pop',
            onKeyDown: event => (event.key === 'Tab' ? close(false) : moveFocus(event, event.currentTarget, ITEM)),
            role: 'menu',
            children: items.map(item =>
              jsxs(
                'button',
                {
                  'aria-checked': item.checked ?? undefined,
                  className: 'cs-ip-pop-row',
                  disabled: item.disabled,
                  onClick: () => {
                    close()
                    onPick(item.id)
                  },
                  role: item.checked === undefined ? 'menuitem' : 'menuitemradio',
                  type: 'button',
                  children: [
                    item.swatch ? jsx('i', { className: 'cs-ip-swatch', style: { background: item.swatch } }) : item.icon ? jsx(Codicon, { name: item.icon, size: 13 }) : null,
                    jsx('span', { children: item.label }),
                    item.checked ? jsx(Codicon, { name: 'check', size: 12 }) : null
                  ]
                },
                item.id
              )
            )
          })
        : null
    ]
  })
}
