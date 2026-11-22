// A look-alike of @hermes/plugin-sdk for previewing the page in a browser. The buttons use the
// app's own class names, and the preview page loads the app's built stylesheet, so they draw
// the way the real ones do. Data comes from window.preview.scenario, or, live (`?live=<token>`, served by
// tools/dev/preview_server.mjs), from the real gateway through that server.
import { useQuery as useLiveQuery, useQueryClient as useLiveQueryClient } from '@tanstack/react-query'
import { createElement, useEffect, useState, useSyncExternalStore } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const listeners = new Set()

/** The live preview's token, or null for the canned scenarios. */
export const liveToken = new URLSearchParams(location.search).get('live')

// The profile the live preview stands in for: the studio, where the page's chats and tools run.
const LIVE_PROFILE = 'hermretro'

async function bridge(profile, method, params = {}, timeoutMs) {
  const response = await fetch('/rpc', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-preview-token': liveToken },
    body: JSON.stringify({ profile, method, params, timeoutMs })
  })
  const answer = await response.json()

  if (answer.error) {
    throw Object.assign(new Error(answer.error.message ?? String(answer.error)), { code: answer.error.code, data: answer.error.data })
  }

  return answer.result
}

export const preview = {
  scenario: { status: { isPending: true }, doctor: { isPending: true } },
  storage: {},
  set(patch) {
    Object.assign(this.scenario, patch)
    listeners.forEach(fn => fn())
  }
}

window.preview = preview

const readable = value => ({ get: () => value })

const eventListeners = new Map()

// Feed a gateway event to the plugin (host.onEvent), e.g. a finished build.
preview.emit = event => {
  for (const type of [event.type, '*']) for (const fn of eventListeners.get(type) ?? []) fn(event)
}

export const host = {
  state: { gateway: readable('open'), focusedSessionId: readable(null), focusedStoredSessionId: readable(null), profile: readable('default') },
  // Answers from preview.scenario.rpc (method → result, or a function of the params); anything else is "not loaded".
  request: async (method, params) => {
    if (preview.scenario.rpc && method in preview.scenario.rpc) {
      const answer = preview.scenario.rpc[method]
      return typeof answer === 'function' ? answer(params) : answer
    }
    throw Object.assign(new Error(`preview: ${method}`), { code: -32601 })
  },
  onEvent: (type, fn) => {
    if (!eventListeners.has(type)) eventListeners.set(type, new Set())
    eventListeners.get(type).add(fn)
    return () => eventListeners.get(type)?.delete(fn)
  },
  // The tab the plugin opens beside the chat: the preview page draws it (preview.workspace).
  openWorkspace: (id, options) => {
    preview.workspace = { id, ...options }
    preview.onWorkspace?.(preview.workspace)
    return () => {}
  },
  profileRoutes: async () => [],
  requestProfile: async () => {
    throw Object.assign(new Error('preview'), { code: -32601 })
  },
  navigate: path => console.log('navigate', path),
  notify: notice => console.log('notify', notice.message),
  newChat: () => console.log('newChat'),
  composer: { insertText: async () => true }
}

if (liveToken) {
  const routeProfile = route => (typeof route === 'string' ? route : route?.profile)

  Object.assign(host, {
    state: { ...host.state, profile: readable(LIVE_PROFILE) },
    request: (method, params, timeoutMs) => bridge(LIVE_PROFILE, method, params, timeoutMs),
    requestProfile: (route, method, params, timeoutMs) => bridge(routeProfile(route), method, params, timeoutMs),
    profileRoutes: async () => (await fetch('/routes', { headers: { 'x-preview-token': liveToken } })).json(),
    retainProfile: async () => () => {},
    retainProfileSocket: () => () => {}
  })
  new EventSource(`/events?token=${encodeURIComponent(liveToken)}`).onmessage = message => preview.emit(JSON.parse(message.data))
}

// The served preview reloads itself when the page is rebuilt.
if (location.protocol.startsWith('http')) {
  new EventSource('/reload').addEventListener('reload', () => location.reload())
}

export const atom = initial => {
  let value = initial
  const subscribers = new Set()
  return {
    get: () => value,
    set: next => { value = next; subscribers.forEach(fn => fn(next)) },
    listen: fn => { subscribers.add(fn); return () => subscribers.delete(fn) }
  }
}
const still = () => () => {}
export const useValue = store => useSyncExternalStore(store.listen ?? still, store.get, store.get)

const useScenarioQuery = options => {
  const [, setTick] = useState(0)

  useEffect(() => {
    const fn = () => setTick(tick => tick + 1)

    listeners.add(fn)

    return () => listeners.delete(fn)
  }, [])

  return preview.scenario[options.queryKey[1]] ?? { isPending: true, data: undefined }
}

const useScenarioQueryClient = () => ({ invalidateQueries: () => listeners.forEach(fn => fn()) })

// Live, the queries are the app's own (TanStack Query, as @hermes/plugin-sdk re-exports it) and run against the gateway.
export const useQuery = liveToken ? useLiveQuery : useScenarioQuery
export const useQueryClient = liveToken ? useLiveQueryClient : useScenarioQueryClient

const BASE =
  'inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-[2.5px] text-xs leading-4 font-medium whitespace-nowrap shadow-none transition-all duration-100 disabled:pointer-events-none disabled:opacity-50'
const VARIANT = {
  default: 'bg-primary text-primary-foreground hover:bg-primary/90',
  outline:
    'bg-transparent text-(--ui-text-primary) shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--ui-stroke-secondary)_50%,transparent)] hover:bg-(--chrome-action-hover)',
  secondary: 'bg-(--ui-bg-quaternary) text-(--ui-text-primary) hover:bg-(--chrome-action-hover)',
  ghost: 'text-(--ui-text-secondary) hover:bg-(--chrome-action-hover) hover:text-(--ui-text-primary)',
  link: 'text-primary underline-offset-4 hover:underline',
  destructive: 'bg-destructive text-white hover:bg-destructive/90 dark:bg-destructive/60'
}
const SIZE = { default: 'px-3 py-1.5', sm: 'px-2.5 py-1', lg: 'px-5 py-2 text-sm leading-5', inline: 'h-auto gap-1 p-0' }

export function Button({ variant = 'default', size = 'default', children, onClick, disabled, 'aria-label': label }) {
  return jsx('button', { 'aria-label': label, className: `${BASE} ${VARIANT[variant] ?? ''} ${SIZE[size] ?? ''}`, disabled, onClick, type: 'button', children })
}

export function CopyButton({ text, label = 'Copy', buttonVariant = 'outline', buttonSize = 'sm', appearance }) {
  const [done, setDone] = useState(false)

  return jsxs(Button, {
    onClick: () => {
      navigator.clipboard?.writeText(text).catch(() => {})
      setDone(true)
      setTimeout(() => setDone(false), 1200)
    },
    size: buttonSize,
    variant: buttonVariant,
    children: [jsx(Codicon, { name: done ? 'check' : 'copy', size: 14 }), appearance === 'icon' ? null : done ? 'Copied' : label]
  })
}

export function Codicon({ name, size = 16, spinning }) {
  return jsx('i', {
    'aria-hidden': true,
    className: `codicon codicon-${name}${spinning ? ' codicon-modifier-spin' : ''}`,
    style: { fontSize: size }
  })
}

export const Badge = ({ children }) => jsx('span', { children })
export const ScrollArea = ({ children, style }) => jsx('div', { style: { ...style, overflow: 'auto' }, children })
export const Separator = () => jsx('hr', { style: { border: 0, borderTop: '1px solid var(--ui-stroke-tertiary)', margin: 0 } })
export const Tip = ({ children }) => children
// The preview paints one mode per load (entry.mjs, ?mode=dark): read it off the root the way the app marks it.
export const useTheme = () => {
  const mode = document.documentElement.classList.contains('dark') ? 'dark' : 'light'

  return { renderedMode: mode, resolvedMode: mode }
}
export const SandboxedFrame = ({ src, title, sandbox, onLoad, ref }) =>
  jsx('iframe', { onLoad, ref, sandbox, src, style: { border: 0, display: 'block', height: '100%', width: '100%' }, title })
export const MessageTextContent = ({ text }) => jsx('div', { style: { whiteSpace: 'pre-wrap' }, children: text })
export const randomUuid = () => crypto.randomUUID()
export const PALETTE_AREA = 'palette'
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export { createElement }
