// Arrow keys between the choices of one group (size picker, tabs, a menu), as screen readers and
// keyboard users expect: the arrows move, Home and End jump to the ends, and the group wraps.

const NEXT = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }

/** Focus the next enabled `selector` inside `container` for this key; returns it, or null when the key
 *  is not one of ours. */
export function moveFocus(event, container, selector) {
  const items = [...(container?.querySelectorAll(selector) ?? [])].filter(item => !item.disabled)
  const at = items.indexOf(event.target)
  const target =
    event.key === 'Home' ? items[0] : event.key === 'End' ? items.at(-1) : NEXT[event.key] && items.length ? items[(at + NEXT[event.key] + items.length) % items.length] : null

  if (!target) {
    return null
  }

  event.preventDefault()
  target.focus()

  return target
}
