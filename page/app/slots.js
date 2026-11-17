// UI slots: a place in one page that other pages can fill, without either importing the other.
// The host page declares the slot in its index.js (`slots: { 'games.cardMenu': 'what goes there and the
// props it gets' }`) and renders `jsx(Slot, { name: 'games.cardMenu', props: { ... } })` where the
// contributions belong. A page contributes from its own index.js
// (`contributes: { 'games.cardMenu': [MyItem] }`); app/registry.js wires both at startup.
// An empty slot renders nothing, so declaring one changes nothing on screen. An undeclared name throws.
import { jsx } from '#sdk'

/** A table of declared slots and what fills them. The page has one (below); tests make their own. */
export function createSlots() {
  const declared = new Map()
  const filled = new Map()

  const known = name => {
    if (!declared.has(name)) {
      throw new Error(`unknown UI slot "${name}": declare it in the host page's index.js (slots: { '${name}': '...' })`)
    }
  }

  return {
    declare(name, owner, doc) {
      if (declared.has(name)) {
        throw new Error(`UI slot "${name}" is declared by both ${declared.get(name).owner} and ${owner}: one page hosts each slot`)
      }

      declared.set(name, { owner, doc })
      filled.set(name, [])
    },
    declared: () => new Map(declared),
    fill(name, Component, from) {
      known(name)

      if (typeof Component !== 'function') {
        throw new Error(`${from} contributes something that is not a component to the UI slot "${name}"`)
      }

      filled.get(name).push(Component)
    },
    contributions(name) {
      known(name)

      return filled.get(name)
    }
  }
}

export const PAGE_SLOTS = createSlots()

/** Renders what other pages contributed to a declared slot, in page order, each with `props`. */
export function Slot({ name, props = {}, slots = PAGE_SLOTS }) {
  const list = slots.contributions(name)

  return list.length ? list.map((Component, index) => jsx(Component, { ...props }, `${name}:${index}`)) : null
}
