// What the sandboxed frame lacks and the player expects: Web Storage, same-origin fetches and a way
// to report its errors. The frame's origin is opaque (sandbox allow-scripts), so storage lives in
// memory for this session and same-origin requests go out as CORS requests to the player server,
// which answers them with Access-Control-Allow-Origin.
import { FROM_FRAME } from '#shared/player/protocol.js'
import { post } from './post.js'

const describe = value => {
  if (value instanceof Error) {
    return value.stack || value.message
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }

  return String(value)
}

/** Forward warnings and errors to the page, which logs them where the developer looks. */
export function forwardLogs() {
  const send = (level, values) => post({ cs: FROM_FRAME.LOG, level, text: values.map(describe).join(' ').slice(0, 2000) })

  for (const level of ['warn', 'error']) {
    const original = console[level].bind(console)

    console[level] = (...values) => {
      send(level, values)
      original(...values)
    }
  }

  addEventListener('error', event => send('error', [`${event.message} @${event.lineno}`]))
  addEventListener('unhandledrejection', event => send('error', ['unhandled: ', event.reason]))
}

function memoryStorage(seed = {}) {
  const items = new Map(Object.entries(seed))

  return {
    getItem: key => (items.has(String(key)) ? items.get(String(key)) : null),
    setItem: (key, value) => {
      items.set(String(key), String(value))
    },
    removeItem: key => {
      items.delete(String(key))
    },
    clear: () => items.clear(),
    key: index => [...items.keys()][index] ?? null,
    get length() {
      return items.size
    }
  }
}

/** In-memory storage, seeded with the device finish the page asked for (`?color=`). */
export function installStorage(params, defaultColor, colorKey) {
  const asked = params.get('color') || ''
  const color = /^[a-z0-9-]{1,40}$/.test(asked) ? asked : defaultColor

  Object.defineProperty(window, 'localStorage', { value: memoryStorage({ [colorKey]: color }), configurable: true })
  Object.defineProperty(window, 'sessionStorage', { value: memoryStorage(), configurable: true })
}

/** Same-origin requests can never succeed from an opaque origin: send them as CORS requests. */
export function installFetch() {
  const realFetch = window.fetch.bind(window)

  window.fetch = (input, init) => {
    if (init && init.mode === 'same-origin') {
      init = { ...init, mode: 'cors', credentials: 'omit' }
    }

    if (input instanceof Request && input.mode === 'same-origin') {
      input = new Request(input, { mode: 'cors', credentials: 'omit' })
    }

    return realFetch(input, init)
  }
}
