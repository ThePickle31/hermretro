// Build conversations as the page holds them, and the requests that reach their sessions.
import { atom, host, randomUuid } from '../sdk.js'
import { describeRequestError } from '../core/backend.js'
import { routeProfile, routing } from '../core/routing.js'

// The game the Build page is showing (its pane plays presentations), or null.
export const BUILD_VIEWING = atom(null)
// Stored session id → { seq, text } to add to that Build conversation's composer (not sent).
export const BUILD_INJECT = atom({})

export function injectBuildDraft(stored, text) {
  const all = BUILD_INJECT.get()

  BUILD_INJECT.set({ ...all, [stored]: { seq: (all[stored]?.seq ?? 0) + 1, text } })
}

// The Build page drives an ordinary Hermes session itself: `session.create` / `session.resume`,
// `prompt.submit`, and the gateway's event stream (`host.onEvent`, filtered by session). The
// session is hidden from the Hermes sidebar; the game switcher is the way in, and "Open in full chat"
// shows the same session in the app's own thread. Stop editing un-hides it.
// The game ↔ session binding is the backend's (`build` RPC, `games[].session`, `pending`).

// Stored session id → the conversation as the Build page renders it.
export const BUILD_CHATS = atom({})
// Runtime session id (what events carry) → stored session id.
export const buildRuntime = new Map()
// Profile routes retained for Build sessions: a pooled socket that closes between calls takes
// the sessions it opened with it.
const buildRetained = new Map()

export const BUILD_EVENTS = [
  'message.start', 'message.delta', 'message.interim', 'message.complete', 'reasoning.delta', 'thinking.delta',
  'status.update', 'tool.generating', 'tool.start', 'tool.progress', 'tool.complete',
  'approval.request', 'clarify.request', 'approval.settled', 'clarify.settled', 'error', 'session.replay_gap', 'session.info'
]

export const newId = () => (typeof randomUuid === 'function' ? randomUuid() : globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`)

function chatRoute() {
  return routing.route ?? null
}

export async function retainChatRoute() {
  const route = chatRoute()

  if (!route || typeof host.retainProfile !== 'function') {
    return
  }

  const key = routeProfile(route) ?? 'default'

  if (buildRetained.has(key)) {
    return
  }

  try {
    buildRetained.set(key, await host.retainProfile(route, { spawnPriority: 'foreground' }))
  } catch (error) {
    console.warn('[hermretro] could not keep the studio profile connection open:', describeRequestError(error).message)
  }
}

/** A gateway call for Build sessions, on the profile the studio talks to. */
export async function chatRequest(method, params = {}, timeoutMs) {
  const route = chatRoute()

  return route
    ? host.requestProfile(route, method, params, timeoutMs, { spawnPriority: 'foreground' })
    : host.request(method, params, timeoutMs)
}

export function patchChat(stored, change) {
  const all = BUILD_CHATS.get()
  const current = all[stored] ?? { stored, items: [], busy: false, segments: {} }
  const next = change(current)

  if (next !== current) {
    BUILD_CHATS.set({ ...all, [stored]: next })
  }
}
