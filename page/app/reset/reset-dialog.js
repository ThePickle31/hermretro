// The factory reset's dialog: choose what to keep, confirm by typing "reset", the steps while it runs, how it ended.
// Closes on Escape or its close button, except while running.
import { Button, Codicon, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Input, jsx, jsxs, SegmentedControl } from '#sdk'
import { formatBytes } from '#app/format.js'
import { RESET_PARTS } from './reset-steps.js'

const CHOICES = [
  { id: 'keep', label: 'Keep' },
  { id: 'delete', label: 'Delete' }
]
const CONFIRM_WORD = 'reset'

/** What a part holds, as its row says it: a size, a count, or what it is. */
function detail(id, parts) {
  const part = parts[id] ?? {}
  const size = part.bytes > 0 ? formatBytes(part.bytes) : null

  if (id === 'games') {
    return [`${part.count ?? 0} ${part.count === 1 ? 'game' : 'games'}`, size].filter(Boolean).join(' · ')
  }

  if (id === 'chats') {
    return part.count == null ? null : `${part.count} ${part.count === 1 ? 'chat' : 'chats'}`
  }

  return id === 'profile' ? 'Model, sign-in, SOUL' : size
}

function Choose({ reset }) {
  const { parts } = reset.context

  return jsx('ul', {
    className: 'cs-rst-parts',
    children: RESET_PARTS.map(({ id, label }) =>
      jsxs(
        'li',
        {
          className: 'cs-rst-part',
          children: [
            jsxs('div', {
              className: 'cs-rst-name',
              children: [jsx('b', { children: label }), jsx('span', { children: [detail(id, parts), reset.forced[id] ?? reset.notes[id]].filter(Boolean).join(' · ') })]
            }),
            // Hermes's control drops an aria-label: the group names which part its Keep and Delete are for.
            jsx('div', {
              'aria-label': label,
              role: 'group',
              children: jsx(SegmentedControl, {
                'aria-label': label,
                disabled: Boolean(reset.forced[id]),
                onChange: value => reset.choose(id, value),
                options: CHOICES,
                sizing: 'equal',
                value: reset.choices[id]
              })
            })
          ]
        },
        id
      )
    )
  })
}

function Column({ title, kind, ids, parts, notes = {} }) {
  return jsxs('div', {
    className: 'cs-rst-col',
    'data-kind': kind,
    children: [
      jsx('h4', { children: title }),
      jsx('ul', {
        children: ids.map(id =>
          jsxs('li', { children: [jsx('span', { children: RESET_PARTS.find(part => part.id === id).label }), jsx('span', { children: notes[id] ?? (parts[id]?.bytes > 0 ? formatBytes(parts[id].bytes) : '') })] }, id)
        )
      })
    ]
  })
}

function Confirm({ reset }) {
  const ids = RESET_PARTS.map(part => part.id)
  const { parts } = reset.context

  return jsxs('div', {
    className: 'cs-rst-confirm',
    children: [
      jsxs('div', {
        className: 'cs-rst-cols',
        children: [
          jsx(Column, { title: 'Delete', kind: 'delete', ids: ids.filter(id => reset.choices[id] === 'delete'), parts }),
          jsx(Column, { title: 'Keep', kind: 'keep', ids: ids.filter(id => reset.choices[id] !== 'delete'), parts, notes: reset.notes })
        ]
      }),
      jsxs('label', {
        className: 'cs-rst-type',
        children: [jsxs('span', { children: ['Type ', jsx('b', { children: CONFIRM_WORD })] }), jsx(Input, { autoFocus: true, onChange: event => reset.type(event.target.value), value: reset.typed })]
      })
    ]
  })
}

function Steps({ reset }) {
  return jsxs('div', {
    children: [
      jsx('div', { className: 'cs-rst-bar', children: jsx('i', { style: { width: `${((reset.step + 1) / reset.steps.length) * 100}%` } }) }),
      jsx('ol', {
        className: 'cs-rst-steps',
        children: reset.steps.map((step, index) =>
          jsxs(
            'li',
            {
              'data-state': index < reset.step ? 'done' : index === reset.step ? 'now' : 'todo',
              children: [
                index < reset.step ? jsx(Codicon, { name: 'check', size: 13 }) : index === reset.step ? jsx(Codicon, { name: 'loading', size: 13, spinning: true }) : jsx('i', {}),
                step.label
              ]
            },
            step.id
          )
        )
      })
    ]
  })
}

/** The update's outcome, as the Version row says it. */
function versionLine(update, from, to) {
  switch (update?.kind) {
    case 'updated':
      return update.restart ? 'Updated. Restart Hermes to finish.' : to && from && to !== from ? `${from} → ${to}` : 'Updated'
    case 'current':
      return from ? `${from}, up to date` : 'Up to date'
    case 'review':
      return 'The update needs your review on the hermretro page'
    case 'busy':
      return 'Not updated: a game is being built'
    case undefined:
    case null:
      return from
    default:
      return `Not updated: ${update.error ?? 'the update did not finish'}`
  }
}

function Done({ reset }) {
  const { summary } = reset
  const rows = [
    ...(summary.failed ? [['Stopped at', `${summary.failed.step}: ${summary.failed.error}`]] : []),
    ['Deleted', formatBytes(summary.deleted)],
    ['Kept', summary.kept.join(', ') || 'Nothing'],
    ['Version', versionLine(summary.update, summary.from, reset.version)]
  ].filter(([, value]) => value)

  return jsx('dl', {
    className: 'cs-rst-done',
    children: rows.map(([name, value]) => jsxs('div', { 'data-error': name === 'Stopped at' ? '' : undefined, children: [jsx('dt', { children: name }), jsx('dd', { children: value })] }, name))
  })
}

function body(reset) {
  switch (reset.phase) {
    case 'loading':
      return jsxs('p', { className: 'cs-rst-note', children: [jsx(Codicon, { name: 'loading', size: 13, spinning: true }), 'Reading what hermretro keeps…'] })
    case 'failed':
      return jsx('p', { className: 'cs-rst-note', 'data-error': '', children: reset.error })
    case 'choose':
      return jsx(Choose, { reset })
    case 'confirm':
      return jsx(Confirm, { reset })
    case 'running':
      return jsx(Steps, { reset })
    default:
      return jsx(Done, { reset })
  }
}

function footer(reset) {
  const cancel = jsx(Button, { onClick: reset.close, size: 'sm', variant: 'ghost', children: reset.phase === 'done' || reset.phase === 'failed' ? 'Close' : 'Cancel' }, 'cancel')

  switch (reset.phase) {
    case 'choose':
      return [
        jsx(Button, { className: 'cs-rst-left', onClick: reset.deleteAll, size: 'sm', variant: 'outline', children: 'Delete everything' }, 'all'),
        cancel,
        jsx(Button, { onClick: reset.confirm, size: 'sm', variant: 'destructive', children: 'Continue' }, 'go')
      ]
    case 'confirm':
      return [
        jsx(Button, { className: 'cs-rst-left', onClick: reset.back, size: 'sm', variant: 'outline', children: 'Back' }, 'back'),
        cancel,
        jsx(Button, { disabled: reset.typed.trim().toLowerCase() !== CONFIRM_WORD, onClick: reset.run, size: 'sm', variant: 'destructive', children: 'Reset' }, 'go')
      ]
    case 'running':
      return []
    case 'done':
      return [
        cancel,
        jsx(Button, { disabled: !reset.canRestart || reset.restarting, onClick: reset.restart, size: 'sm', variant: 'default', children: reset.restarting ? 'Restarting…' : 'Reload & restart gateway' }, 'restart')
      ]
    default:
      return [cancel]
  }
}

const TITLES = { running: 'Resetting hermretro', done: 'hermretro is reset' }

export function ResetDialog({ reset }) {
  const running = reset.phase === 'running'
  const failedRun = reset.phase === 'done' && reset.summary?.failed

  return jsx(Dialog, {
    open: reset.phase !== 'closed',
    onOpenChange: open => {
      if (!open && !running) {
        reset.close()
      }
    },
    children: jsxs(DialogContent, {
      className: 'cs-rst-dlg',
      showCloseButton: !running,
      children: [
        jsx(DialogHeader, { children: jsx(DialogTitle, { children: failedRun ? 'The reset stopped' : (TITLES[reset.phase] ?? 'Factory reset hermretro') }) }),
        body(reset),
        jsx(DialogFooter, { className: 'cs-rst-foot', children: footer(reset) })
      ]
    })
  })
}
