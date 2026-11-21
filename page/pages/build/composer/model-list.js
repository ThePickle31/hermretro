// The left two columns of the model panel: the provider rail (Starred, each signed-in provider, connect another)
// and the search box with the models of the picked provider, of the search, or the starred ones.
import { Codicon, host, jsx, jsxs, useMemo } from '#sdk'
import { modelName } from './model-names.js'

export const STARRED = '*starred'
export const starKey = (provider, model) => `${provider}:${model}`

/** The rows the middle column shows: one group per provider while searching, else the picked tab's models. */
export function useModelRows(providers, tab, needle, stars) {
  return useMemo(() => {
    const row = (item, model) => ({ model, provider: item.slug, providerName: item.name, caps: item.capabilities?.[model] ?? null })

    if (needle) {
      return providers
        .map(item => ({
          name: item.name,
          rows: item.models
            .filter(model => model.toLowerCase().includes(needle) || modelName(model).name.toLowerCase().includes(needle))
            .map(model => row(item, model))
        }))
        .filter(group => group.rows.length)
    }

    if (tab === STARRED) {
      return [{ name: null, rows: providers.flatMap(item => item.models.filter(model => stars.has(starKey(item.slug, model))).map(model => row(item, model))) }]
    }

    const item = providers.find(provider => provider.slug === tab)

    return item ? [{ name: null, rows: item.models.map(model => row(item, model)) }] : []
  }, [providers, tab, needle, stars])
}

export function ProviderRail({ providers, marks, tab, onTab, onConnect }) {
  const tile = (key, label, mark, extra = {}) =>
    jsxs(
      'button',
      {
        'aria-label': label,
        'aria-pressed': tab === key,
        className: `cs-b-mp-tile${extra.className ? ` ${extra.className}` : ''}`,
        onClick: () => onTab(key),
        title: label,
        type: 'button',
        children: [mark, jsx('span', { className: 'cs-sr cs-b-mp-pname', children: label })]
      },
      key
    )

  return jsxs('div', {
    'aria-label': 'Providers',
    className: 'cs-b-mp-rail',
    role: 'group',
    children: [
      tile(STARRED, 'Starred', jsx(Codicon, { name: 'star-full', size: 14 }), { className: 'cs-b-mp-starred' }),
      jsx('span', { 'aria-hidden': true, className: 'cs-b-mp-sep' }),
      ...providers.map(item => tile(item.slug, item.name, jsx('span', { 'aria-hidden': true, children: marks.get(item.slug) }), { className: 'cs-b-mp-prov' })),
      jsx('span', { className: 'cs-grow' }),
      jsx('button', {
        'aria-label': 'Connect another provider',
        className: 'cs-b-mp-tile',
        onClick: onConnect,
        title: 'Connect another provider',
        type: 'button',
        children: jsx(Codicon, { name: 'add', size: 14 })
      })
    ]
  })
}

function ModelRow({ row, mark, on, starred, withProvider, onChoose, onStar }) {
  const label = modelName(row.model)

  return jsxs('div', {
    className: `cs-b-mp-item${on ? ' on' : ''}${starred ? ' starred' : ''}`,
    children: [
      jsxs('button', {
        'aria-selected': on,
        className: 'cs-b-mp-row',
        onClick: () => onChoose(row),
        role: 'option',
        title: `${row.model} · ${row.providerName}`,
        type: 'button',
        children: [
          jsx('span', { 'aria-hidden': true, className: 'cs-b-mp-glyph', children: mark }),
          // The starred list mixes providers: each row names its own under the model.
          withProvider
            ? jsxs('span', { className: 'cs-b-mp-label two', children: [jsx('span', { children: label.name }), jsx('small', { className: 'cs-b-mp-from', children: row.providerName })] })
            : jsx('span', { className: 'cs-b-mp-label', children: label.name }),
          ...label.tags.map(tag => jsx('span', { className: 'cs-b-mp-tag', children: tag }, tag)),
          on ? jsx('span', { className: 'cs-b-mp-check', children: jsx(Codicon, { name: 'check', size: 12 }) }) : null
        ]
      }),
      jsx('button', {
        'aria-label': starred ? `Unstar ${label.name}` : `Star ${label.name}`,
        'aria-pressed': starred,
        className: 'cs-b-mp-star',
        onClick: () => onStar(row),
        title: starred ? 'Unstar' : 'Star',
        type: 'button',
        children: jsx(Codicon, { name: starred ? 'star-full' : 'star-empty', size: 12 })
      })
    ]
  })
}

/** The middle column. `groups` come from useModelRows; `head` names what is listed; `withProvider` names each
 *  row's provider (the starred list mixes them). */
export function ModelList({ groups, marks, head, search, query, setQuery, placeholder, shown, stars, onChoose, onStar, empty, withProvider }) {
  const first = groups[0]?.rows[0]

  return jsxs('div', {
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
              if (event.key === 'Enter' && first) {
                event.preventDefault()
                onChoose(first)
              }
            },
            placeholder,
            ref: search,
            value: query
          })
        ]
      }),
      head ? jsx('div', { className: 'cs-b-mp-head', children: head }) : null,
      jsx('div', {
        className: 'cs-b-mp-list',
        role: 'listbox',
        children: groups.some(group => group.rows.length)
          ? groups.flatMap(group => [
              group.name ? jsx('div', { className: 'cs-b-mp-group', children: group.name }, `g:${group.name}`) : null,
              ...group.rows.map(row =>
                jsx(
                  ModelRow,
                  {
                    mark: marks.get(row.provider),
                    on: row.model === shown.model && row.provider === shown.provider,
                    onChoose,
                    onStar,
                    row,
                    starred: stars.has(starKey(row.provider, row.model)),
                    withProvider
                  },
                  starKey(row.provider, row.model)
                )
              )
            ])
          : jsx('p', { className: 'cs-faint', children: empty })
      })
    ]
  })
}

export const connectProvider = close => () => {
  close()
  host.navigate?.('/settings?tab=providers')
}
