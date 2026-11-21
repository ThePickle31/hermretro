// Model, effort and (ChatGPT or Codex Subscription models) speed: one button, one panel with a provider rail,
// the models, an Effort column and a speed bar.
import {
  Button,
  Codicon,
  host,
  jsx,
  jsxs,
  useEffect,
  useLayoutEffect,
  useMemo,
  useQuery,
  useRef,
  useState,
  useValue
} from '#sdk'
import { applyBuildPick, cancelBuildPick, hasFastMode, pickBuildModel } from '#pages/build/chat/model-pick.js'
import { chatRequest } from '#pages/build/chat/store.js'
import { AGENT, ID } from '#app/ids.js'
import { effortLabel, modelName, providerMark, providerMarks } from './model-names.js'
import { connectProvider, ModelList, ProviderRail, STARRED, starKey, useModelRows } from './model-list.js'
import { EffortColumn, SpeedBar } from './model-settings.js'

// The panel's width, the width under which it narrows its Effort column and shortens its words, and the one under
// which three columns no longer fit, so Effort moves under the models.
const PANEL = 560
const NARROW = 500
const TINY = 440

/** The connected providers and their models (`model.options`), for a conversation or the profile. */
function useModelOptions(runtime) {
  const gateway = useValue(host.state.gateway)

  return useQuery({
    queryKey: [ID, 'models', runtime ?? 'profile'],
    queryFn: () => chatRequest('model.options', runtime ? { session_id: runtime } : {}, 30_000),
    enabled: gateway === 'open',
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1
  })
}

/** The left and right edges the panel must stay within: the window, narrowed by the nearest box that clips or
 *  scrolls sideways (returned as `clip`, so the panel can follow its size). */
function panelArea(node) {
  let start = 0
  let end = window.innerWidth || 1200
  let clip = null

  for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
    const rect = parent.getBoundingClientRect()

    if (rect.width > 0 && getComputedStyle(parent).overflowX !== 'visible') {
      start = Math.max(start, rect.left)
      end = Math.min(end, rect.right)
      clip = parent

      break
    }
  }

  return { start, end, clip }
}

/** Starred models (`provider:model`), kept in the page's storage: Hermes's own starred list is not open to plugins. */
function useStars(ctx) {
  const [stars, setStars] = useState(() => {
    try {
      const saved = ctx?.storage?.get?.('buildModelStars', [])

      return new Set(Array.isArray(saved) ? saved : [])
    } catch {
      return new Set()
    }
  })

  const toggle = key => {
    const next = new Set(stars)

    if (next.has(key)) {
      next.delete(key)
    } else {
      next.add(key)
    }

    setStars(next)

    try {
      ctx?.storage?.set?.('buildModelStars', [...next])
    } catch {
      // this visit only
    }
  }

  return [stars, toggle]
}

/** `pending` is a change not yet confirmed by Hermes (held for the turn's end, or on its way): the panel shows it, so
 *  every next choice (Fast, an arrow key) is judged against the model and effort it will run on. `waiting` says it is
 *  held until the turn ends. */
function ModelPicker({ ctx, value, pending = null, waiting = false, confirm = null, options, onPick, onEffort, onFast, onConfirm, onCancelConfirm, disabled = false, up = true }) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState(null)
  const [query, setQuery] = useState('')
  const [stars, toggleStar] = useStars(ctx)
  const box = useRef(null)
  const search = useRef(null)
  const data = options?.data
  const providers = useMemo(() => (Array.isArray(data?.providers) ? data.providers.filter(item => item?.authenticated && Array.isArray(item.models) && item.models.length) : []), [data])
  const shown = { model: pending?.model ?? value?.model ?? data?.model ?? null, provider: pending?.provider ?? value?.provider ?? data?.provider ?? null, effort: pending?.effort ?? value?.effort ?? '', fast: pending?.fast ?? value?.fast ?? false }
  const marks = useMemo(() => providerMarks(providers), [providers])
  const current = providers.find(item => item.slug === shown.provider) ?? null
  const signedOut = Boolean(data && shown.provider && !current && Array.isArray(data.providers))
  const caps = current?.capabilities?.[shown.model] ?? null
  const speed = hasFastMode(shown.provider, caps)
  const activeTab = tab === STARRED || providers.find(item => item.slug === tab) ? tab : (current?.slug ?? providers[0]?.slug ?? null)
  const activeProvider = providers.find(item => item.slug === activeTab) ?? null
  const needle = query.trim().toLowerCase()
  const groups = useModelRows(providers, activeTab, needle, stars)
  const name = shown.model ? modelName(shown.model).name : 'Default model'
  // The panel opens from the button and stays inside the window and the box that scrolls it: where there is too
  // little room it moves left and narrows.
  const [place, setPlace] = useState(null)
  const narrow = Boolean(place && place.width < NARROW)
  const tiny = Boolean(place && place.width < TINY)

  // Placed when it opens, and again whenever the window or the box that clips it changes size while it is open.
  useLayoutEffect(() => {
    if (!open || !box.current?.getBoundingClientRect) {
      setPlace(null)

      return undefined
    }

    const measure = () => {
      if (!box.current) {
        return null
      }

      const left = box.current.getBoundingClientRect().left
      const { start, end, clip } = panelArea(box.current)
      const width = Math.min(PANEL, end - start - 24)
      const shift = Math.max(start + 12 - left, Math.min(0, end - 12 - left - width))

      setPlace(last => (last && last.left === shift && last.width === width ? last : { left: shift, width }))

      return clip
    }
    const clip = measure()
    const watch = typeof ResizeObserver === 'function' && clip ? new ResizeObserver(() => measure()) : null

    watch?.observe(clip)
    window.addEventListener('resize', measure)

    return () => {
      watch?.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [open])

  useEffect(() => {
    if (!open) {
      return undefined
    }

    setQuery('')
    setTab(null)

    const focus = () => search.current?.focus?.()

    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(focus)
    } else {
      focus()
    }

    const away = event => {
      if (box.current && !box.current.contains(event.target)) {
        setOpen(false)
      }
    }
    const key = event => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', away)
    window.addEventListener('keydown', key)

    return () => {
      document.removeEventListener('mousedown', away)
      window.removeEventListener('keydown', key)
    }
  }, [open])

  // A model that asks before it is used opens the panel with the question.
  useEffect(() => {
    if (confirm) {
      setOpen(true)
    }
  }, [confirm?.message])

  const choose = row => {
    setOpen(false)

    if (row.model !== shown.model || row.provider !== shown.provider) {
      // Leaving fast mode on would carry Hermes's priority tier to a model without the switch (Anthropic and
      // xAI read it as their own fast mode), so a model without it goes back to standard. That covers a Fast
      // still on its way (`shown` includes `pending`), which the model pick would otherwise inherit.
      onPick({ model: row.model, provider: row.provider, ...(shown.fast && !hasFastMode(row.provider, row.caps) ? { fast: false } : {}) })
    }
  }
  const close = () => setOpen(false)
  const count = activeProvider ? (activeProvider.total_models ?? activeProvider.models.length) : 0
  const head = needle
    ? null
    : activeTab === STARRED
      ? [jsx('b', { children: 'Starred' }, 'b'), narrow ? null : jsx('span', { children: '\u00b7 from every provider' }, 'n')]
      : activeProvider
        ? [jsx('b', { title: activeProvider.name, children: activeProvider.name }, 'b'), jsx('span', { children: narrow ? `\u00b7 ${count}` : `\u00b7 ${count} ${count === 1 ? 'model' : 'models'}` }, 'n')]
        : null
  const empty = needle
    ? 'No model matches.'
    : activeTab === STARRED
      ? 'Star a model with its \u2606 to keep it here.'
      : !data && !options?.isError
        ? 'Loading\u2026'
        : options?.isError
          ? 'Could not list the models.'
          : 'No provider is connected.'

  return jsxs('div', {
    className: 'cs-b-mp',
    ref: box,
    children: [
      jsxs('button', {
        'aria-expanded': open,
        'aria-haspopup': 'dialog',
        className: `cs-b-mp-chip${open ? ' open' : ''}${signedOut ? ' warn' : ''}`,
        disabled,
        onClick: () => setOpen(!open),
        title: shown.model ? `${shown.model} · ${current?.name ?? shown.provider ?? ''}` : 'Model and effort',
        type: 'button',
        children: [
          signedOut ? jsx(Codicon, { name: 'warning', size: 12 }) : jsx('span', { 'aria-hidden': true, className: 'cs-b-mp-mark', children: marks.get(current?.slug) ?? providerMark(shown.provider) }),
          jsx('span', { className: 'cs-b-mp-name', children: signedOut ? `${shown.provider} is signed out` : name }),
          !signedOut ? jsx('span', { className: 'cs-b-mp-dot', children: '\u00b7' }) : null,
          !signedOut ? jsx('span', { className: 'cs-b-mp-effortname', children: effortLabel(shown.effort) }) : null,
          !signedOut && shown.fast ? jsx('span', { 'aria-label': 'Fast mode', className: 'cs-b-mp-bolt', role: 'img', title: 'Fast mode', children: jsx(Codicon, { name: 'zap', size: 11 }) }) : null,
          waiting ? jsx('span', { className: 'cs-b-mp-next', title: `Switches when ${AGENT} finishes this turn`, children: 'next message' }) : null,
          jsx(Codicon, { name: 'chevron-down', size: 11 })
        ]
      }),
      open
        ? jsxs('div', {
            'aria-label': 'Model and effort',
            className: `cs-b-mp-pop${up ? ' up' : ''}${narrow ? ' narrow' : ''}${tiny ? ' tiny' : ''}`,
            role: 'dialog',
            style: place ? { left: place.left, width: place.width } : undefined,
            children: [
              confirm
                ? jsxs('div', {
                    className: 'cs-b-mp-confirm',
                    children: [
                      jsx('span', { className: 'cs-grow', children: confirm.message }),
                      jsx(Button, { onClick: onConfirm, size: 'sm', children: 'Use it' }),
                      jsx(Button, { onClick: onCancelConfirm, size: 'sm', variant: 'ghost', children: 'Cancel' })
                    ]
                  })
                : null,
              jsxs('div', {
                className: 'cs-b-mp-body',
                children: [
                  jsx(ProviderRail, {
                    marks,
                    onConnect: connectProvider(close),
                    onTab: key => {
                      setTab(key)
                      setQuery('')
                    },
                    providers,
                    tab: needle ? null : activeTab
                  }),
                  jsx(ModelList, {
                    empty,
                    groups,
                    head,
                    marks,
                    onChoose: choose,
                    onStar: row => toggleStar(starKey(row.provider, row.model)),
                    placeholder: 'Search models',
                    query,
                    search,
                    setQuery,
                    shown,
                    stars,
                    withProvider: !needle && activeTab === STARRED
                  }),
                  jsx(EffortColumn, { caps, disabled, narrow, onEffort, shown })
                ]
              }),
              jsx(SpeedBar, { disabled, fast: shown.fast, held: waiting, narrow, onFast: on => onFast(on, { model: shown.model, provider: shown.provider }), onManage: connectProvider(close), speed })
            ]
          })
        : null
    ]
  })
}

/** The picker for a Build conversation: what it runs on now, and changes to it. */
export function ChatModelPicker({ ctx, stored, chat, disabled }) {
  const options = useModelOptions(chat?.runtime ?? null)

  return jsx(ModelPicker, {
    ctx,
    confirm: chat?.pickConfirm ?? null,
    disabled,
    // A model that asks first is not on its way until Use it: until then the panel keeps the model in use.
    pending: chat?.pickConfirm ? null : (chat?.heldPick ?? null),
    waiting: Boolean(chat?.busy && chat?.heldPick),
    onCancelConfirm: () => cancelBuildPick(stored),
    onConfirm: () => void applyBuildPick(stored, { confirmed: true }),
    onEffort: effort => void pickBuildModel(stored, { effort }),
    onFast: fast => void pickBuildModel(stored, { fast }),
    onPick: pick => void pickBuildModel(stored, pick),
    options,
    value: chat?.info ?? null
  })
}

/** The picker before a conversation exists (New Game, a game with no conversation): the pick is used
 *  when the conversation is made, and remembered for the next one. */
export function DraftModelPicker({ ctx, pick, onPick, up = true }) {
  const options = useModelOptions(null)

  return jsx(ModelPicker, {
    ctx,
    up,
    onEffort: effort => onPick({ ...pick, effort }),
    // The draft keeps the model the speed was picked for (the profile's default when none was picked).
    onFast: (fast, at) => onPick({ ...pick, ...(at.model && at.provider ? at : {}), fast }),
    onPick: choice => onPick({ ...pick, ...choice }),
    options,
    value: pick
  })
}

export function useDraftPick(ctx) {
  const [pick, setPick] = useState(() => {
    try {
      const saved = ctx.storage.get('buildModel', null)

      return saved && typeof saved === 'object' ? saved : {}
    } catch {
      return {}
    }
  })

  const update = next => {
    setPick(next)

    try {
      ctx.storage.set('buildModel', next)
    } catch {
      // this visit only
    }
  }

  return [pick, update]
}
