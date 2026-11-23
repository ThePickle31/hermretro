// The New Game screen.
import { Codicon, jsx, jsxs, useEffect, useLayoutEffect, useRef, useValue } from '#sdk'
import { ProviderNotice } from './composer/provider-notice.js'
import { clearNewGameDraft, editNewGameDraft, NEW_GAME_DRAFT, NEW_GAME_STARTING } from './new-game-draft.js'

// The two ways to start, as the backend tells the agent (backend/library/rpcs.py build context): keep the words in step.
const NEW_GAME_MODES = [
  { id: 'build', title: 'Build it', text: 'Approve a short list before the project is created.', ends: 'Ends with a game you can play' },
  { id: 'plan', title: 'Plan first', text: 'Start a project for the brief, backlog and test plan. Approve the brief before authoring begins.', ends: 'Ends with a plan to review' }
]

// The last handoff the box took focus for: once each, not on every later visit.
let focusedSeq = 0

/** New Game: one centred composer (the Build page's own) and two choices under it, each saying what it does.
 *  No name field: the agent names the project when it creates it. The platformer background (page/backgrounds/) plays behind
 *  it and takes no part in the form. The idea and the choice are a kept draft (new-game-draft.js): onboarding's
 *  first idea arrives here unsent, and leaving the page keeps what was typed. `onStart` answers true once the
 *  conversation has the idea; only then is the draft cleared. */
export function BuildNewGame({ onStart, picker = null, updating = false }) {
  const draft = useValue(NEW_GAME_DRAFT)
  const idea = draft.idea
  const mode = draft.plan ? 'plan' : 'build'
  const setIdea = value => editNewGameDraft({ idea: value })
  const setMode = value => editNewGameDraft({ plan: value === 'plan' })
  const busy = useValue(NEW_GAME_STARTING)
  const box = useRef(null)

  // A handed-over idea (onboarding): the box gets focus with the cursor after it, ready to send or edit.
  useEffect(() => {
    const element = box.current

    if (draft.seq && draft.seq !== focusedSeq && element) {
      focusedSeq = draft.seq
      element.focus?.()
      element.setSelectionRange?.(element.value.length, element.value.length)
    }
  }, [draft.seq])

  useLayoutEffect(() => {
    const element = box.current

    if (element) {
      element.style.height = 'auto'
      element.style.height = `${Math.min(Math.max(element.scrollHeight, 66), 220)}px`
    }
  }, [idea])

  const start = async () => {
    // The atom, not this screen's state: a second Enter before the re-render, or the screen remounted while the first
    // start runs, sees it at once.
    if (NEW_GAME_STARTING.get() || !idea.trim() || updating) {
      return
    }

    const { rev } = NEW_GAME_DRAFT.get()

    NEW_GAME_STARTING.set(true)

    try {
      if ((await onStart({ idea, name: '', plan: mode === 'plan' })) === true) {
        clearNewGameDraft(rev)
      }
    } finally {
      NEW_GAME_STARTING.set(false)
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
      jsxs('h1', { className: 'cs-word cs-title', children: ['What are we ', jsx('span', { className: 'cs-accent', children: 'making?' })] }),
      jsxs('div', {
        className: 'cs-b-comp',
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
                disabled: busy || updating || !idea.trim(),
                onClick: () => void start(),
                title: updating ? 'hermretro is updating. You can start in a moment.' : mode === 'plan' ? 'Start planning' : 'Start building',
                type: 'button',
                children: [jsx(Codicon, { name: 'arrow-up', size: 14 }, 'icon'), jsx('span', { className: 'cs-sr', children: busy ? 'Starting…' : 'Start' }, 'label')]
              })
            ]
          })
        ]
      }),
      // Right under the box, where it is seen before sending (not under the cards, where the shelf can cover it).
      jsx(ProviderNotice, {}, 'providers'),
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
