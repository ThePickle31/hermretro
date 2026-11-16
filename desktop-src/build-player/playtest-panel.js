// The play-test panel beside the game: HermRetro's note, the Try-this checklist from the build
// report, the controls, and "this moment" actions. Beside the game when there is room, under it as
// tabs when the chat is narrow, and folded to a slim tab when the user folds it or has ticked
// everything.
import { Codicon, jsx, jsxs, useId, useState } from '../sdk.js'
import { AGENT } from '../core/ids.js'
import { moveFocus } from './arrow-keys.js'
import { BarButton } from './control-bar.js'

const KEYS = [
  ['\u2190 \u2191 \u2193 \u2192', 'move'],
  ['Z', 'A'],
  ['X', 'B'],
  ['Enter', 'Start'],
  ['Shift', 'Select']
]

export function KeyHints({ className = 'cs-ip-keys' }) {
  return jsx('div', {
    className,
    children: KEYS.map(([key, word]) => jsxs('span', { children: [jsx('kbd', { children: key }), ` ${word}`] }, word))
  })
}

const STATE_NOTE = {
  untested: `${AGENT} didn\u2019t test this`,
  reported: `Reported \u00b7 ${AGENT} is on it`
}

function CheckItem({ item, build, asking, onToggle, onWorked, onWrong }) {
  const note = item.state === 'fixed' ? `Fixed in #${build} \u00b7 check it again` : STATE_NOTE[item.state]

  return jsxs('li', {
    className: 'cs-ip-check',
    'data-state': item.state,
    children: [
      jsxs('label', {
        children: [
          jsx('input', { checked: item.state === 'done', disabled: item.state === 'reported', onChange: event => onToggle(item, event.target.checked), type: 'checkbox' }),
          jsxs('span', { children: [jsx('span', { className: 'cs-ip-check-text', children: item.text }), note ? jsx('em', { children: note }) : null] })
        ]
      }),
      asking
        ? jsxs('div', {
            className: 'cs-ip-ask',
            role: 'group',
            'aria-label': `What happened with ${item.text}`,
            children: [
              jsx('span', { children: 'What happened?' }),
              jsxs('div', {
                className: 'cs-row',
                children: [
                  jsx(BarButton, { icon: 'check', label: 'It worked', onClick: () => onWorked(item), text: 'It worked' }),
                  jsx(BarButton, { icon: 'comment-discussion', label: `Something's wrong: tell ${AGENT}`, onClick: () => onWrong(item), primary: true, text: 'Something\u2019s wrong' })
                ]
              })
            ]
          })
        : null
    ]
  })
}

function Checklist({ playtest, build, onWrong }) {
  const [asking, setAsking] = useState(null)

  // Ticking a check HermRetro did not test (or one it fixed) asks how it went first.
  const toggle = (item, on) => {
    if (on && (item.state === 'untested' || item.state === 'fixed')) {
      setAsking(asking === item.key ? null : item.key)
    } else {
      playtest.tick(item.key, on)
    }
  }

  return jsx('ul', {
    className: 'cs-ip-checks',
    children: playtest.items.map(item =>
      jsx(
        CheckItem,
        {
          asking: asking === item.key,
          build,
          item,
          onToggle: toggle,
          onWorked: entry => {
            setAsking(null)
            playtest.tick(entry.key, true)
          },
          onWrong: entry => {
            setAsking(null)
            onWrong(entry)
          }
        },
        item.key
      )
    )
  })
}

function Moment({ ready, onAsk, onAnnotate, onShot }) {
  return jsxs('div', {
    className: 'cs-row cs-ip-moment',
    children: [
      jsx(BarButton, { disabled: !ready, icon: 'comment-discussion', label: `Ask ${AGENT} about what the game shows now`, onClick: onAsk, primary: true, text: `Ask ${AGENT}` }),
      jsx(BarButton, { disabled: !ready, icon: 'inspect', label: 'Annotate', onClick: onAnnotate, text: 'Annotate' }),
      jsx(BarButton, { disabled: !ready, icon: 'device-camera', label: 'Screenshot', onClick: onShot })
    ]
  })
}

const Heading = ({ children, extra = null }) => jsxs('div', { className: 'cs-ip-sh', children: [jsx('span', { children }), extra] })

/** `layout`: 'side' (beside the game) or 'tabs' (under it, narrow chats). */
export function PlaytestPanel({ layout, note, playtest, build, ready, onWrong, onAsk, onAnnotate, onShot }) {
  const [tab, setTab] = useState(playtest.items.length ? 'try' : note ? 'note' : 'controls')
  const ids = useId()
  const { done, total } = playtest.counts
  const sections = {
    note: note ? jsxs('div', { className: 'cs-ip-sec', children: [layout === 'side' ? jsx(Heading, { children: `${AGENT}\u2019s note` }) : null, jsx('p', { className: 'cs-ip-note', children: note })] }) : null,
    try: total
      ? jsxs('div', {
          className: 'cs-ip-sec',
          children: [
            layout === 'side' ? jsx(Heading, { extra: jsx('b', { className: 'cs-ip-count', children: `${done}/${total}` }), children: 'Try this' }) : null,
            jsx(Checklist, { build, onWrong, playtest })
          ]
        })
      : null,
    controls: jsxs('div', { className: 'cs-ip-sec', children: [layout === 'side' ? jsx(Heading, { children: 'Controls' }) : null, jsx(KeyHints, { className: 'cs-ip-keys stacked' })] })
  }
  const moment = jsxs('div', { className: 'cs-ip-sec', children: [layout === 'side' ? jsx(Heading, { children: 'This moment' }) : null, jsx(Moment, { onAnnotate, onAsk, onShot, ready })] })

  if (layout === 'side') {
    return jsxs('aside', { 'aria-label': 'Play-test', className: 'cs-ip-panel', children: [sections.note, sections.try, sections.controls, moment] })
  }

  const tabs = [
    ['try', total ? `Try this \u00b7 ${done}/${total}` : null],
    ['note', note ? 'Note' : null],
    ['controls', 'Controls']
  ].filter(([, label]) => label)
  const current = sections[tab] ? tab : tabs[0][0]

  return jsxs('div', {
    'aria-label': 'Play-test',
    className: 'cs-ip-panel tabs',
    children: [
      jsx('div', {
        'aria-label': 'Play-test',
        className: 'cs-ip-tabs',
        onKeyDown: event => {
          const target = moveFocus(event, event.currentTarget, '[role=tab]')

          if (target) {
            setTab(target.dataset.tab)
          }
        },
        role: 'tablist',
        children: tabs.map(([id, label]) =>
          jsx(
            'button',
            {
              'aria-controls': `${ids}-panel`,
              'aria-selected': id === current,
              'data-tab': id,
              id: `${ids}-${id}`,
              onClick: () => setTab(id),
              role: 'tab',
              tabIndex: id === current ? 0 : -1,
              type: 'button',
              children: label
            },
            id
          )
        )
      }),
      jsx('div', { 'aria-labelledby': `${ids}-${current}`, id: `${ids}-panel`, role: 'tabpanel', children: sections[current] }),
      moment
    ]
  })
}

/** The folded panel: a slim tab that says how much is left to try. */
export function FoldedPanel({ counts, onOpen }) {
  const allDone = counts.complete

  return jsxs('button', {
    'aria-label': 'Open the play-test panel',
    className: 'cs-ip-fold',
    onClick: onOpen,
    type: 'button',
    children: [
      jsx(Codicon, { name: 'checklist', size: 14 }),
      counts.total ? jsx('span', { className: allDone ? 'cs-ip-pill ok' : 'cs-ip-pill', children: allDone ? '\u2713' : String(counts.left) }) : null,
      jsx('span', { className: 'cs-ip-vt', children: allDone ? 'All checked' : counts.total ? `Play-test \u00b7 ${counts.left} left` : 'Play-test' })
    ]
  })
}
