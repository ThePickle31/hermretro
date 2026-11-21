// Model, effort and (ChatGPT or Codex Subscription models) speed: one button, one panel.
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
import { effortLabel, modelName, providerMark } from './model-names.js'
import { ModelSettings } from './model-settings.js'

// The panel's width: wide enough beside Speed for the Effort buttons to keep their usual width.
const PANEL = 580
const PANEL_WITH_SPEED = 720

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
 *  scrolls sideways. */
function panelArea(node) {
  let start = 0
  let end = window.innerWidth || 1200

  for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
    const rect = parent.getBoundingClientRect()

    if (rect.width > 0 && getComputedStyle(parent).overflowX !== 'visible') {
      start = Math.max(start, rect.left)
      end = Math.min(end, rect.right)

      break
    }
  }

  return [start, end]
}

function ModelPicker({ value, held = null, confirm = null, options, onPick, onEffort, onFast, onConfirm, onCancelConfirm, disabled = false, up = true }) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState(null)
  const [query, setQuery] = useState('')
  const box = useRef(null)
  const search = useRef(null)
  const data = options?.data
  const providers = useMemo(() => (Array.isArray(data?.providers) ? data.providers.filter(item => item?.authenticated && Array.isArray(item.models) && item.models.length) : []), [data])
  const shown = { model: held?.model ?? value?.model ?? data?.model ?? null, provider: held?.provider ?? value?.provider ?? data?.provider ?? null, effort: held?.effort ?? value?.effort ?? '', fast: held?.fast ?? value?.fast ?? false }
  const current = providers.find(item => item.slug === shown.provider) ?? null
  const signedOut = Boolean(data && shown.provider && !current && Array.isArray(data.providers))
  const caps = current?.capabilities?.[shown.model] ?? null
  const speed = hasFastMode(shown.provider, caps)
  const activeTab = providers.find(item => item.slug === tab) ? tab : (current?.slug ?? providers[0]?.slug ?? null)
  const needle = query.trim().toLowerCase()
  const rows = useMemo(() => {
    const list = needle ? providers : providers.filter(item => item.slug === activeTab)

    return list.flatMap(item =>
      item.models
        .filter(model => !needle || model.toLowerCase().includes(needle) || modelName(model).name.toLowerCase().includes(needle))
        .map(model => ({ model, provider: item.slug, providerName: item.name, caps: item.capabilities?.[model] ?? null }))
    )
  }, [providers, activeTab, needle])
  const name = shown.model ? modelName(shown.model).name : 'Default model'
  // The panel opens from the button and stays inside the window and the box that scrolls it (New Game's form
  // scrolls sideways when a panel sticks out of it): where there is too little room it moves left and narrows.
  const [place, setPlace] = useState(null)

  useLayoutEffect(() => {
    if (!open || !box.current?.getBoundingClientRect) {
      setPlace(null)

      return
    }

    const left = box.current.getBoundingClientRect().left
    const [start, end] = panelArea(box.current)
    const room = end - start - 24
    // Speed sits beside Effort when there is room for the wider panel, else on its own line under it.
    const beside = speed && room >= PANEL_WITH_SPEED
    const width = Math.min(beside ? PANEL_WITH_SPEED : PANEL, room)
    const shift = Math.max(start + 12 - left, Math.min(0, end - 12 - left - width))

    setPlace({ left: shift, width, beside })
  }, [open, speed])

  useEffect(() => {
    if (!open) {
      return undefined
    }

    setQuery('')

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
      // xAI read it as their own fast mode), so a model without it goes back to normal.
      onPick({ model: row.model, provider: row.provider, ...(shown.fast && !hasFastMode(row.provider, row.caps) ? { fast: false } : {}) })
    }
  }

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
          signedOut ? jsx(Codicon, { name: 'warning', size: 12 }) : jsx('span', { 'aria-hidden': true, className: 'cs-b-mp-mark', children: providerMark(current?.name ?? shown.provider) }),
          jsx('span', { className: 'cs-b-mp-name', children: signedOut ? `${shown.provider} is signed out` : name }),
          !signedOut ? jsx('span', { className: 'cs-b-mp-dot', children: '·' }) : null,
          !signedOut ? jsx('span', { className: 'cs-b-mp-effortname', children: effortLabel(shown.effort) }) : null,
          !signedOut && shown.fast ? jsx('span', { 'aria-label': 'Fast mode', className: 'cs-b-mp-bolt', role: 'img', title: 'Fast mode', children: jsx(Codicon, { name: 'zap', size: 11 }) }) : null,
          held ? jsx('span', { className: 'cs-b-mp-next', title: `Switches when ${AGENT} finishes this turn`, children: 'next message' }) : null,
          jsx(Codicon, { name: 'chevron-down', size: 11 })
        ]
      }),
      open
        ? jsxs('div', {
            'aria-label': 'Model and effort',
            className: `cs-b-mp-pop${up ? ' up' : ''}${place && place.width < 520 ? ' narrow' : ''}`,
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
                  jsxs('div', {
                    className: 'cs-b-mp-providers',
                    children: [
                      jsx('span', { className: 'cs-eyebrow', children: 'Providers' }),
                      ...providers.map(item =>
                        jsxs(
                          'button',
                          {
                            'aria-pressed': !needle && item.slug === activeTab,
                            className: 'cs-b-mp-prov',
                            onClick: () => {
                              setTab(item.slug)
                              setQuery('')
                            },
                            title: item.name,
                            type: 'button',
                            children: [
                              jsx('span', { className: 'cs-b-mp-pname', children: item.name }),
                              jsx('small', { children: item.total_models ?? item.models.length })
                            ]
                          },
                          item.slug
                        )
                      ),
                      !data && !options?.isError ? jsx('span', { className: 'cs-faint', children: 'Loading…' }) : null,
                      options?.isError ? jsx('span', { className: 'cs-faint', children: 'Could not list the models.' }) : null,
                      data && !providers.length ? jsx('span', { className: 'cs-faint', children: 'No provider is connected.' }) : null,
                      jsx('span', { className: 'cs-grow' }),
                      jsxs('button', {
                        className: 'cs-b-link',
                        onClick: () => {
                          setOpen(false)
                          host.navigate?.('/settings?tab=providers')
                        },
                        type: 'button',
                        children: [jsx(Codicon, { name: 'add', size: 11 }), ' Connect another']
                      })
                    ]
                  }),
                  jsxs('div', {
                    className: 'cs-b-mp-models',
                    children: [
                      jsxs('label', {
                        className: 'cs-b-mp-search',
                        children: [
                          jsx(Codicon, { name: 'search', size: 12 }),
                          jsx('input', {
                            'aria-label': 'Search models',
                            onChange: event => setQuery(event.target.value),
                            onKeyDown: event => {
                              if (event.key === 'Enter' && rows[0]) {
                                event.preventDefault()
                                choose(rows[0])
                              }
                            },
                            placeholder: needle || !activeTab ? 'Search every provider' : `Search ${providers.find(item => item.slug === activeTab)?.name ?? ''}`,
                            ref: search,
                            value: query
                          })
                        ]
                      }),
                      jsx('div', {
                        className: 'cs-b-mp-list',
                        role: 'listbox',
                        children: rows.length
                          ? rows.map(row => {
                              const label = modelName(row.model)
                              const on = row.model === shown.model && row.provider === shown.provider

                              return jsxs(
                                'button',
                                {
                                  'aria-selected': on,
                                  className: 'cs-b-mp-row',
                                  onClick: () => choose(row),
                                  role: 'option',
                                  title: row.model,
                                  type: 'button',
                                  children: [
                                    jsx('span', { className: 'cs-b-mp-check', children: on ? jsx(Codicon, { name: 'check', size: 12 }) : null }),
                                    jsxs('span', {
                                      className: 'cs-b-mp-label',
                                      children: [label.name, needle ? jsx('small', { children: row.providerName }) : null]
                                    }),
                                    jsx('span', { className: 'cs-grow' }),
                                    ...label.tags.map(tag => jsx('span', { className: 'cs-b-mp-tag', children: tag }, tag)),
                                    row.caps?.fast ? jsx('span', { className: 'cs-b-mp-tag', children: 'fast mode' }) : null
                                  ]
                                },
                                `${row.provider}:${row.model}`
                              )
                            })
                          : jsx('p', { className: 'cs-faint', children: needle ? 'No model matches.' : 'Pick a provider.' })
                      }),
                      jsx(ModelSettings, { beside: Boolean(place?.beside), caps, disabled, onEffort, onFast, shown, speed })
                    ]
                  })
                ]
              }),
              held ? jsx('p', { className: 'cs-b-mp-foot', children: `Switches when ${AGENT} finishes this turn.` }) : null
            ]
          })
        : null
    ]
  })
}

/** The picker for a Build conversation: what it runs on now, and changes to it. */
export function ChatModelPicker({ stored, chat, disabled }) {
  const options = useModelOptions(chat?.runtime ?? null)

  return jsx(ModelPicker, {
    confirm: chat?.pickConfirm ?? null,
    disabled,
    held: chat?.busy ? (chat?.heldPick ?? null) : null,
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
