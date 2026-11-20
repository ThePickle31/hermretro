// The New Game screen.
import { Codicon, jsx, jsxs, useLayoutEffect, useRef, useState } from '#sdk'
import { AGENT } from '#app/ids.js'

// The two ways to start, as the backend tells the agent (backend/library/rpcs.py build context): keep the words in step.
const NEW_GAME_MODES = [
  { id: 'build', title: 'Build it', text: `A few quick questions, then ${AGENT} makes the game and shows it to you in the emulator.`, ends: 'Ends with a game you can play' },
  { id: 'plan', title: 'Plan first', text: 'A short interview, then a brief, backlog and test plan. Nothing is built until you say so.', ends: 'Ends with a plan to review' }
]

/** New Game: one centred composer (the Build page's own) and two choices under it, each saying what it does.
 *  No name field: the agent names the project when it creates it. The title, the composer and the choices are
 *  marked `data-plat`: the attract-mode level behind the form (attract/) uses them as platforms. */
export function BuildNewGame({ onStart, picker = null }) {
  const [idea, setIdea] = useState('')
  const [mode, setMode] = useState('build')
  const [busy, setBusy] = useState(false)
  const box = useRef(null)
  // A second Enter before the re-render would start a second game: a ref sees the first at once.
  const starting = useRef(false)

  useLayoutEffect(() => {
    const element = box.current

    if (element) {
      element.style.height = 'auto'
      element.style.height = `${Math.min(Math.max(element.scrollHeight, 66), 220)}px`
    }
  }, [idea])

  const start = async () => {
    if (starting.current || !idea.trim()) {
      return
    }

    starting.current = true
    setBusy(true)

    try {
      await onStart({ idea, name: '', plan: mode === 'plan' })
    } finally {
      starting.current = false
      setBusy(false)
    }
  }

  // Arrow keys move between the two choices, as in any radio group.
  const onModeKey = event => {
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
      event.preventDefault()
      const next = mode === 'build' ? 'plan' : 'build'
      setMode(next)
      event.currentTarget.parentElement?.querySelector(`[data-mode="${next}"]`)?.focus?.()
    }
  }

  return jsxs('section', {
    className: 'cs-b-new',
    children: [
      jsxs('h1', { className: 'cs-word cs-title', 'data-plat': 'title', children: ['What are we ', jsx('span', { className: 'cs-accent', children: 'making?' })] }),
      jsxs('div', {
        className: 'cs-b-comp',
        'data-plat': 'composer',
        children: [
          jsx('textarea', {
            'aria-label': 'Your game idea',
            disabled: busy,
            onChange: event => setIdea(event.target.value),
            onKeyDown: event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent?.isComposing) {
                event.preventDefault()
                void start()
              }
            },
            placeholder: 'A lighthouse keeper who has to keep the lamp lit through one stormy night…',
            ref: box,
            rows: 3,
            value: idea
          }),
          jsxs('div', {
            className: 'cs-b-comp-row',
            children: [
              picker,
              jsx('span', { className: 'cs-grow' }),
              jsx('button', {
                'aria-label': mode === 'plan' ? 'Start planning' : 'Start building',
                className: 'cs-b-send',
                disabled: busy || !idea.trim(),
                onClick: () => void start(),
                title: mode === 'plan' ? 'Start planning' : 'Start building',
                type: 'button',
                children: [jsx(Codicon, { name: 'arrow-up', size: 14 }, 'icon'), jsx('span', { className: 'cs-sr', children: busy ? 'Starting…' : 'Start' }, 'label')]
              })
            ]
          })
        ]
      }),
      jsx('div', {
        'aria-label': 'How to start',
        className: 'cs-b-opts',
        role: 'radiogroup',
        children: NEW_GAME_MODES.map(item =>
          jsxs(
            'button',
            {
              'aria-checked': mode === item.id,
              className: mode === item.id ? 'cs-b-opt on' : 'cs-b-opt',
              'data-plat': 'opt',
              'data-mode': item.id,
              onClick: () => setMode(item.id),
              onKeyDown: onModeKey,
              role: 'radio',
              tabIndex: mode === item.id ? 0 : -1,
              type: 'button',
              children: [
                jsx('i', { 'aria-hidden': true, className: 'cs-b-opt-dot' }),
                jsxs('span', {
                  children: [
                    jsx('b', { children: item.title }),
                    jsx('span', { children: item.text }),
                    jsx('em', { children: item.ends })
                  ]
                })
              ]
            },
            item.id
          )
        )
      })
    ]
  })
}
