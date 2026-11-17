// The game switcher: the title in the Build header.
import { Codicon, jsx, jsxs, useEffect, useRef, useState } from '#sdk'
import { AGENT } from '#app/ids.js'
import { GAME_STATES } from '#pages/games/model.js'

/** The games being edited, in menu order: New Game conversations still being set up, then each game
 *  with its own conversation (and the one just picked from the library, until its first message makes
 *  one). Each has its status, from its conversation. The rest of the library is under Edit a game. */
export function switcherEntries(games, pending, states, selected) {
  const sub = (state, fallback) => (state?.waiting ? 'Needs your answer' : state?.busy ? `${AGENT} is working…` : state?.unread ? 'New reply' : fallback)

  return [
    ...pending.map(item => {
      const state = states[item.storedId] ?? null

      return { key: `pending:${item.storedId}`, title: item.name || 'New game', sub: sub(state, 'Setting up…'), state, game: null, pending: item, stored: item.storedId }
    }),
    ...games
      .filter(game => game.buildSession || game.id === selected)
      .map(game => {
        const state = game.buildSession ? (states[game.buildSession] ?? null) : null
        const mine = Boolean(game.buildSession) && game.session?.thisProfile !== false

        return {
          key: game.id,
          title: game.title,
          sub: game.buildSession ? sub(state, (GAME_STATES[game.state] ?? GAME_STATES.unbuilt)[1]) : 'New editing chat',
          state,
          game,
          stored: mine ? game.buildSession : null
        }
      })
  ]
}

const libraryWhen = game => (GAME_STATES[game.state] ?? GAME_STATES.unbuilt)[1]

export function BuildSwitcher({ entries, library, selected, title, onSelect, onOpenChat, onStop, onDiscard }) {
  const [open, setOpen] = useState(false)
  // 'menu' (New game, Edit a game, the games being edited) or 'library' (Edit a game's list).
  const [view, setView] = useState('menu')
  const [query, setQuery] = useState('')
  // The right-click menu on a game being edited: { key, x, y } inside the popover.
  const [ctxMenu, setCtxMenu] = useState(null)
  const box = useRef(null)
  const pop = useRef(null)
  const others = entries.filter(entry => entry.key !== selected)
  const waiting = others.filter(entry => entry.state?.waiting).length
  const working = others.filter(entry => entry.state?.busy && !entry.state?.waiting).length
  const unread = others.some(entry => entry.state?.unread)
  const needle = query.trim().toLowerCase()
  const shelf = needle ? library.filter(game => game.title.toLowerCase().includes(needle)) : library

  const close = () => {
    setOpen(false)
    setView('menu')
    setQuery('')
    setCtxMenu(null)
  }

  useEffect(() => {
    if (!open) {
      return undefined
    }

    const items = () => [...(box.current?.querySelectorAll?.(ctxMenu ? '.cs-b-ctx button:not(:disabled)' : '.cs-b-sw-pop button') ?? [])]
    const away = event => {
      if (box.current && !box.current.contains(event.target)) {
        close()
      } else if (ctxMenu && !event.target.closest?.('.cs-b-ctx')) {
        setCtxMenu(null)
      }
    }
    const key = event => {
      if (event.key === 'Escape') {
        event.preventDefault()

        if (ctxMenu) {
          setCtxMenu(null)
        } else if (view === 'library') {
          setView('menu')
          setQuery('')
        } else {
          close()
          box.current?.querySelector?.('.cs-b-sw')?.focus?.()
        }
      } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        const list = items()
        const at = list.indexOf(document.activeElement)

        event.preventDefault()
        list[(at + (event.key === 'ArrowDown' ? 1 : -1) + list.length) % list.length]?.focus?.()
      }
    }

    document.addEventListener('mousedown', away)
    window.addEventListener('keydown', key)

    return () => {
      document.removeEventListener('mousedown', away)
      window.removeEventListener('keydown', key)
    }
  }, [open, view, Boolean(ctxMenu)])

  // On opening (or going back to the menu) the current game is focused first, so Enter keeps it and the
  // arrows move from there; the library starts in its search box; the right-click menu on its first item.
  useEffect(() => {
    if (!open) {
      return
    }

    if (ctxMenu) {
      box.current?.querySelector?.('.cs-b-ctx button:not(:disabled)')?.focus?.()
    } else if (view === 'library') {
      box.current?.querySelector?.('.cs-b-sw-search input')?.focus?.()
    } else {
      const list = [...(box.current?.querySelectorAll?.('.cs-b-sw-pop button') ?? [])]

      ;(list.find(item => item.getAttribute('aria-current') === 'true') ?? list[0])?.focus?.()
    }
  }, [open, view, ctxMenu?.key])

  const pick = key => {
    close()
    onSelect(key)
  }

  const openMenuAt = (entry, x, y) => {
    if (!entry.stored) {
      return
    }

    const frame = pop.current?.getBoundingClientRect?.()

    setCtxMenu({ key: entry.key, x: frame ? x - frame.left : 16, y: frame ? y - frame.top : 16 })
  }

  const mark = state =>
    state?.waiting
      ? jsx('i', { 'aria-label': 'Needs your answer', className: 'dot wait' })
      : state?.busy
        ? jsx('i', { 'aria-label': `${AGENT} is working`, className: 'cs-b-spin' })
        : state?.unread
          ? jsx('i', { 'aria-label': 'New reply', className: 'dot new' })
          : null

  const thumb = game =>
    game?.thumb
      ? jsx('img', { alt: '', className: 'cs-b-sw-thumb', draggable: false, src: game.thumb })
      : jsx('span', { 'aria-hidden': true, className: 'cs-b-sw-thumb ph', children: jsx(Codicon, { name: game ? 'game' : 'sparkle', size: 12 }) })

  const ctxEntry = ctxMenu ? entries.find(entry => entry.key === ctxMenu.key) : null
  const ctx = ctxEntry
    ? jsxs('div', {
        'aria-label': `${ctxEntry.title} options`,
        className: 'cs-b-ctx',
        role: 'menu',
        style: { left: Math.min(ctxMenu.x, 200), top: ctxMenu.y },
        children: [
          jsxs('button', {
            onClick: () => {
              close()
              onOpenChat(ctxEntry.stored)
            },
            role: 'menuitem',
            type: 'button',
            children: [jsx(Codicon, { name: 'link-external', size: 12 }), 'Open in full chat']
          }),
          jsx('hr', {}),
          jsxs('button', {
            className: 'danger',
            disabled: Boolean(ctxEntry.state?.busy),
            onClick: () => {
              close()
              void (ctxEntry.pending ? onDiscard(ctxEntry.pending) : onStop(ctxEntry.game))
            },
            role: 'menuitem',
            title: ctxEntry.state?.busy ? `Wait for ${AGENT} to finish first` : undefined,
            type: 'button',
            children: [jsx(Codicon, { name: 'close', size: 12 }), ctxEntry.pending ? 'Discard' : 'Stop editing']
          })
        ]
      })
    : null

  const editing = entries.filter(entry => entry.game)
  const openNames = editing.map(entry => entry.title)
  const openNote = !openNames.length
    ? null
    : openNames.length === 1
      ? `${openNames[0]} is already open above.`
      : openNames.length === 2
        ? `${openNames[0]} and ${openNames[1]} are already open above.`
        : `${openNames.length} games you\u2019re editing are already open above.`

  const menuView = [
    jsxs(
      'button',
      {
        'aria-current': selected === 'new' ? 'true' : undefined,
        className: 'cs-b-game cs-b-sw-new',
        onClick: () => pick('new'),
        role: 'menuitem',
        type: 'button',
        children: [jsx('span', { className: 'cs-b-sw-thumb add', children: jsx(Codicon, { name: 'add', size: 14 }) }), jsx('b', { children: 'New game' })]
      },
      'new'
    ),
    library.length
      ? jsxs(
          'button',
          {
            'aria-haspopup': 'menu',
            className: 'cs-b-game cs-b-sw-new',
            onClick: () => setView('library'),
            role: 'menuitem',
            type: 'button',
            children: [
              jsx('span', { className: 'cs-b-sw-thumb edit', children: jsx(Codicon, { name: 'edit', size: 12 }) }),
              jsxs('span', { className: 'nm', children: [jsx('b', { children: 'Edit a game' }), jsx('small', { children: 'Open one from your library' })] }),
              jsx('span', { className: 'cs-b-sw-go', children: jsx(Codicon, { name: 'chevron-right', size: 13 }) })
            ]
          },
          'edit'
        )
      : null,
    entries.length ? jsx('p', { className: 'cs-eyebrow', children: 'Editing now' }, 'eyebrow') : null,
    jsx(
      'div',
      {
        className: 'cs-b-sw-list',
        children: entries.map((entry, index) =>
          jsxs(
            'button',
            {
              'aria-current': selected === entry.key ? 'true' : undefined,
              className: `cs-b-game${entry.state?.waiting ? ' wait' : ''}`,
              onClick: () => pick(entry.key),
              onContextMenu: event => {
                if (entry.stored) {
                  event.preventDefault()
                  openMenuAt(entry, event.clientX, event.clientY)
                }
              },
              onKeyDown: event => {
                if (entry.stored && (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10'))) {
                  event.preventDefault()
                  const rect = event.currentTarget.getBoundingClientRect()

                  openMenuAt(entry, rect.left + 40, rect.bottom - 4)
                }
              },
              role: 'menuitem',
              type: 'button',
              children: [
                thumb(entry.game),
                jsxs('span', { className: 'nm', children: [jsx('b', { children: entry.title }), jsx('small', { children: entry.sub })] }),
                mark(entry.state),
                index < 9 ? jsxs('span', { className: 'cs-b-sw-key', children: ['Ctrl ', index + 1] }) : null
              ]
            },
            entry.key
          )
        )
      },
      'list'
    ),
    entries.length || library.length ? null : jsx('p', { className: 'cs-faint cs-b-sw-empty', children: 'Games you make here show up in this list.' }, 'empty')
  ]

  const libraryView = [
    jsxs(
      'button',
      {
        className: 'cs-b-sw-back',
        onClick: () => {
          setView('menu')
          setQuery('')
        },
        type: 'button',
        children: [jsx(Codicon, { name: 'chevron-left', size: 13 }), 'Edit a game']
      },
      'back'
    ),
    jsxs(
      'label',
      {
        className: 'cs-b-sw-search',
        children: [
          jsx(Codicon, { name: 'search', size: 12 }),
          jsx('input', {
            'aria-label': 'Search your games',
            onChange: event => setQuery(event.target.value),
            onKeyDown: event => {
              if (event.key === 'Enter' && shelf[0]) {
                event.preventDefault()
                pick(shelf[0].id)
              }
            },
            placeholder: 'Search your games',
            value: query
          })
        ]
      },
      'search'
    ),
    jsx(
      'div',
      {
        className: 'cs-b-sw-list',
        children: shelf.map(game =>
          jsxs(
            'button',
            {
              className: 'cs-b-game',
              onClick: () => pick(game.id),
              role: 'menuitem',
              type: 'button',
              children: [
                thumb(game),
                jsxs('span', { className: 'nm', children: [jsx('b', { children: game.title }), jsx('small', { children: libraryWhen(game) })] }),
                jsx('span', { className: 'go', children: 'Start editing' })
              ]
            },
            game.id
          )
        )
      },
      'shelf'
    ),
    shelf.length ? null : jsx('p', { className: 'cs-faint cs-b-sw-empty', children: needle ? 'No game by that name.' : 'Every game is already open above.' }, 'none'),
    openNote ? jsx('p', { className: 'cs-b-sw-foot', children: openNote }, 'foot') : null
  ]

  return jsxs('div', {
    className: 'cs-b-swwrap',
    ref: box,
    children: [
      jsxs('button', {
        'aria-expanded': open,
        'aria-haspopup': 'menu',
        'aria-label': `${title}: switch game`,
        className: `cs-b-sw${open ? ' open' : ''}`,
        onClick: () => (open ? close() : setOpen(true)),
        type: 'button',
        children: [jsx('h2', { className: 'cs-word', children: title }), jsx(Codicon, { name: 'chevron-down', size: 14 })]
      }),
      waiting
        ? jsx('button', {
            className: 'cs-b-needs',
            onClick: () => setOpen(true),
            title: others.filter(entry => entry.state?.waiting).map(entry => entry.title).join(', '),
            type: 'button',
            children: `${waiting} needs you`
          })
        : working
          ? jsxs('span', { className: 'cs-b-others', children: [jsx('i', { className: 'cs-b-spin' }), `${working} working`] })
          : unread
            ? jsx('i', { 'aria-label': 'Another game has a new reply', className: 'cs-b-otherdot' })
            : null,
      open
        ? jsxs('div', {
            'aria-label': view === 'library' ? 'Edit a game' : 'Your games',
            className: `cs-b-sw-pop${view === 'library' ? ' lib' : ''}`,
            ref: pop,
            role: 'menu',
            children: [...(view === 'library' ? libraryView : menuView), ctx]
          })
        : null
    ]
  })
}
