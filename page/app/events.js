// Page events: how one page tells others that something happened, without importing them.
// The page that owns an event declares it in its index.js (`events: { 'games.coverRequested': 'what it
// means and its payload' }`); app/registry.js collects the declarations at startup. Anyone may then
// `emit(name, payload)` and `on(name, fn)`; a page that listens for its whole life (even while not shown)
// says so in its index.js (`listens: { 'emulator.presented': (payload, ctx) => ... }`).
// An undeclared name throws, so a typo fails the first test that reaches it. A listener that throws is
// logged and never stops the emitter or the other listeners.

/** A hub of declared events. The page has one (below); tests make their own. */
export function createEvents() {
  const declared = new Map()
  const listeners = new Map()

  const known = name => {
    if (!declared.has(name)) {
      throw new Error(`unknown page event "${name}": declare it in the owning page's index.js (events: { '${name}': '...' })`)
    }
  }

  return {
    declare(name, owner, doc) {
      if (declared.has(name)) {
        throw new Error(`page event "${name}" is declared by both ${declared.get(name).owner} and ${owner}: one page owns each event`)
      }

      declared.set(name, { owner, doc })
    },
    declared: () => new Map(declared),
    on(name, fn) {
      known(name)

      const set = listeners.get(name) ?? new Set()

      listeners.set(name, set)
      set.add(fn)

      return () => set.delete(fn)
    },
    emit(name, payload) {
      known(name)

      for (const fn of [...(listeners.get(name) ?? [])]) {
        try {
          fn(payload)
        } catch (error) {
          console.error(`[hermretro] a listener of "${name}" failed:`, error)
        }
      }
    }
  }
}

export const PAGE_EVENTS = createEvents()

/** Listen to a declared page event; returns the function that stops listening. */
export const on = (name, fn) => PAGE_EVENTS.on(name, fn)

/** Tell every listener of a declared page event. */
export const emit = (name, payload) => PAGE_EVENTS.emit(name, payload)
