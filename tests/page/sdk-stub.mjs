// Stand-in for @hermes/plugin-sdk, enough to drive the hermretro page in jsdom.
// Its react-query surface: useQuery(options) records the query (scenario.queries, scenario.fns[key]) and answers
// scenario[queryKey[1]] (pending until a test sets it; queryFn never runs); useQueryClient() gives
// invalidateQueries (a no-op) and setQueryData(queryKey, value or updater) / getQueryData(queryKey) over one cache,
// scenario.queryData (a Map keyed by JSON.stringify(queryKey)). Anything else from react-query is not here: add it.
import { useSyncExternalStore } from 'react'
import { jsx } from 'react/jsx-runtime'

export const scenario = {
  status: null, doctor: null, activity: null, queries: [], notices: [], navigations: [], storage: {},
  fns: {}, byMethod: {}, inserted: [], paramsByMethod: {}, ambient: null, routes: [], byProfile: {}, calls: [],
  // Gateway event listeners (host.onEvent) and the workspace tabs a plugin opened (host.openWorkspace).
  events: {}, workspaces: [],
  // The query client's cache (setQueryData / getQueryData), keyed by JSON.stringify(queryKey).
  queryData: new Map()
}

// Deliver a gateway event the way the app's tap does (contrib/events.ts): by type, then '*'.
export const emit = event => {
  for (const type of [event.type, '*']) for (const listener of scenario.events[type] ?? []) listener(event)
}

const readable = value => ({ get: () => value })
const notLoaded = () => Object.assign(new Error('unknown method'), { code: -32601 })

export const host = {
  state: {
    gateway: readable('open'), focusedSessionId: readable('rt-1'), focusedStoredSessionId: readable('st-1'), profile: readable('default')
  },
  // The profile the app is on.
  request: async (method, params) => {
    scenario.calls.push(['request', method])
    scenario.lastParams = params
    scenario.paramsByMethod[method] = params
    if (method in scenario.byMethod) {
      const answer = scenario.byMethod[method]
      return typeof answer === 'function' ? answer(params) : answer
    }
    if (scenario.ambientError) throw scenario.ambientError
    if (!scenario.ambient) throw notLoaded()
    return scenario.ambient
  },
  profileRoutes: async () => {
    scenario.calls.push(['profileRoutes'])
    return scenario.routes
  },
  // Another profile, without switching the app to it.
  requestProfile: async (route, method) => {
    scenario.calls.push(['requestProfile', route.profile, method])
    if (!scenario.byProfile[route.profile]) throw notLoaded()
    return scenario.byProfile[route.profile]
  },
  navigate: path => scenario.navigations.push(path),
  notify: notice => scenario.notices.push(notice),
  newChat: profile => scenario.calls.push(['newChat', profile ?? null]),
  composer: { insertText: async (target, text) => { scenario.calls.push(['insert', target]); scenario.inserted.push([target, text]); return true } },
  openSession: async (stored, options) => { scenario.calls.push(['openSession', stored, options?.profile ?? null]) },
  onEvent: (type, listener) => {
    (scenario.events[type] ??= new Set()).add(listener)
    return () => scenario.events[type]?.delete(listener)
  },
  // Same contract as the app's: re-opening an id fronts the existing tab; the disposer closes it and fires onClose.
  openWorkspace: (id, options) => {
    const existing = scenario.workspaces.find(tab => tab.id === id && !tab.closed)
    if (existing) { existing.options = options; existing.fronted = (existing.fronted ?? 0) + 1; return existing.close }
    const tab = { id, options, closed: false }
    tab.close = () => { if (!tab.closed) { tab.closed = true; options.onClose?.() } }
    scenario.workspaces.push(tab)
    return tab.close
  }
}

export const atom = initial => {
  let value = initial
  const listeners = new Set()
  return {
    get: () => value,
    set: next => { value = next; for (const listener of [...listeners]) listener(next) },
    listen: listener => { listeners.add(listener); return () => listeners.delete(listener) }
  }
}
const still = () => () => {}
export const useValue = store => useSyncExternalStore(store.listen ?? still, store.get, store.get)

export const useQuery = options => {
  const key = options.queryKey[1]

  scenario.queries.push({ key, queryKey: options.queryKey, enabled: options.enabled, refetchInterval: options.refetchInterval })
  scenario.fns[key] = options.queryFn

  return scenario[key] ?? { isPending: true, isFetching: false, data: undefined }
}

export const useQueryClient = () => ({
  invalidateQueries: () => {},
  getQueryData: queryKey => scenario.queryData.get(JSON.stringify(queryKey)),
  setQueryData: (queryKey, value) => {
    const key = JSON.stringify(queryKey)
    const next = typeof value === 'function' ? value(scenario.queryData.get(key)) : value

    scenario.queryData.set(key, next)
    return next
  }
})

const el = (tag, extra = {}) => props =>
  jsx(tag, { ...extra, 'aria-label': props['aria-label'], onClick: props.onClick, disabled: props.disabled, 'data-variant': props.variant, children: props.children ?? props.text ?? props.label })

export const Button = el('button', { type: 'button' })
export const Badge = el('span', { 'data-badge': '' })
export const CopyButton = el('button', { type: 'button', 'data-copy': '' })
export const Codicon = props => jsx('i', { 'data-icon': props.name })
export const ScrollArea = el('div')
export const Separator = () => jsx('hr', {})
export const Tip = props => props.children
// The real one renders a sandboxed iframe; here a plain one is enough to see what it was given.
export const SandboxedFrame = props => jsx('iframe', { ref: props.ref, src: props.src, title: props.title, 'data-sandbox': props.sandbox })
export const MessageTextContent = props => jsx('div', { 'data-markdown': '', children: props.text })
export const randomUuid = () => `uuid-${Math.random().toString(16).slice(2)}`
export const PALETTE_AREA = 'palette'
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
