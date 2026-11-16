// Model and effort: one button, one panel.
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
} from '../sdk.js'
import { applyBuildPick, cancelBuildPick, pickBuildModel } from '../build-chat/model-pick.js'
import { chatRequest } from '../build-chat/store.js'
import { AGENT, ID } from '../core/ids.js'
import { effortLabel, EFFORTS, modelName, providerMark } from './model-names.js'

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

function ModelPicker({ value, held = null, confirm = null, options, onPick, onEffort, onConfirm, onCancelConfirm, disabled = false, up = true }) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState(null)
  const [query, setQuery] = useState('')
  const box = useRef(null)
  const search = useRef(null)
  const data = options?.data
  const providers = useMemo(() => (Array.isArray(data?.providers) ? data.providers.filter(item => item?.authenticated && Array.isArray(item.models) && item.models.length) : []), [data])
  const shown = { model: held?.model ?? value?.model ?? data?.model ?? null, provider: held?.provider ?? value?.provider ?? data?.provider ?? null, effort: held?.effort ?? value?.effort ?? '' }
  const current = providers.find(item => item.slug === shown.provider) ?? null
  const signedOut = Boolean(data && shown.provider && !current && Array.isArray(data.providers))
  const caps = current?.capabilities?.[shown.model] ?? null
  const fixedEffort = caps ? caps.reasoning === false : false
  const efforts = EFFORTS.filter(([key]) => key !== 'none' || caps?.can_disable_reasoning !== false)
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
  // The panel opens from the button and stays inside the window: on a narrow one it moves left and narrows.
  const [place, setPlace] = useState(null)

  useLayoutEffect(() => {
    if (!open || !box.current?.getBoundingClientRect) {
      setPlace(null)

      return
    }

    const left = box.current.getBoundingClientRect().left
    const room = (window.innerWidth || 1200) - 24
    const width = Math.min(580, room)
    const shift = Math.min(0, room + 12 - left - width)

    setPlace({ left: shift, width })
  }, [open])

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
      onPick({ model: row.model, provider: row.provider })
    }
  }

  const effortRow = jsxs('div', {
    className: 'cs-b-mp-effort',
    children: [
      jsxs('div', {
        className: 'cs-row',
        children: [
          jsx('span', { className: 'cs-eyebrow', children: 'Effort' }),
          jsx('span', { className: 'cs-grow' }),
          jsx('span', { className: 'cs-faint', children: fixedEffort ? 'This model has a fixed effort' : (EFFORTS.find(([key]) => key === shown.effort)?.[2] ?? 'The model\u2019s default') })
        ]
      }),
      jsx('div', {
        'aria-label': 'Effort',
        className: 'cs-b-seg',
        role: 'radiogroup',
        children: efforts.map(([key, label]) =>
          jsx(
            'button',
            {
              'aria-checked': shown.effort === key,
              disabled: disabled || fixedEffort,
              onClick: () => key !== shown.effort && onEffort(key),
              role: 'radio',
              type: 'button',
              children: label
            },
            key
          )
        )
      })
    ]
  })

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
                      effortRow
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
