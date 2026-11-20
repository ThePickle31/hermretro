// The header's update chip and its popover (mockup round "one-click update", direction A): shown only while an
// update is ready, running or just finished. Closes on Escape or a click elsewhere, except while updating.
import { Button, Codicon, jsx, jsxs, useEffect, useRef } from '#sdk'
import { UPDATE_STEPS } from './flow.js'

const CHIP = {
  idle: ['accent', 'Update ready'],
  updating: ['accent', 'Updating'],
  review: ['warn', 'Needs a look'],
  failed: ['bad', 'Update failed'],
  restart: ['warn', 'Restart to finish'],
  partial: ['bad', 'Finish update'],
  done: ['good', 'Updated']
}

function Steps({ step, waiting }) {
  // A chat that started building while Hermes updated: the hermretro profile reloads once it finishes.
  const labels = waiting?.length ? UPDATE_STEPS.map((label, index) => (index === 1 ? `Waiting for "${waiting[0]}" to finish building` : label)) : UPDATE_STEPS

  return jsx('ol', {
    className: 'cs-upd-steps',
    children: labels.map((label, index) =>
      jsxs(
        'li',
        {
          'data-state': index < step ? 'done' : index === step ? 'now' : 'todo',
          children: [
            index < step ? jsx(Codicon, { name: 'check', size: 12 }) : index === step ? jsx(Codicon, { name: 'loading', size: 12, spinning: true }) : jsx('i', {}),
            label
          ]
        },
        label
      )
    )
  })
}

function Findings({ review }) {
  const lines = review.findings.length
    ? review.findings.slice(0, 6).map(f => `${String(f.severity ?? '').toUpperCase()}  ${f.file ?? ''}:${f.line ?? ''}  ${f.description || f.category || ''}`)
    : review.lines.slice(0, 8)

  return lines.length ? jsx('pre', { className: 'cs-upd-pre', children: lines.join('\n') }) : null
}

/** What the popover says for each phase. */
function body(update) {
  const actions = (...children) => jsx('div', { className: 'cs-upd-acts', children })
  const whatsNew = jsxs(Button, { onClick: update.whatsNew, size: 'sm', variant: 'link', children: ["What's new", jsx(Codicon, { name: 'link-external', size: 12 })] }, 'new')

  switch (update.phase) {
    case 'updating':
      return ['Updating…', jsx(Steps, { step: update.step, waiting: update.waiting }, 'steps'), jsx('p', { children: 'You can keep using Hermes. This page reloads by itself at the end.' }, 'p')]
    case 'review':
      return [
        'Review the new version',
        jsx(
          'p',
          {
            children: update.review?.findings?.length
              ? "Hermes's security check found something to look at before installing it. Nothing has changed yet."
              : 'The new version adds to what hermretro can do in Hermes. Nothing has changed yet.'
          },
          'p'
        ),
        update.review ? jsx(Findings, { review: update.review }, 'f') : null,
        actions(
          jsx(Button, { onClick: update.agree, size: 'sm', variant: 'default', children: 'Install anyway' }, 'yes'),
          jsx(Button, { onClick: update.cancel, size: 'sm', variant: 'ghost', children: 'Cancel' }, 'no')
        )
      ]
    case 'failed':
      return [
        "Couldn't update",
        jsx('p', { children: `${update.error ?? 'The update did not finish.'} Nothing was changed${update.version ? `; you are still on ${update.version}` : ''}.` }, 'p'),
        actions(
          jsx(Button, { onClick: update.start, size: 'sm', variant: 'default', children: 'Try again' }, 'again'),
          jsx(Button, { onClick: update.openPlugins, size: 'sm', variant: 'link', children: 'Open Capabilities → Plugins' }, 'plugins')
        )
      ]
    case 'partial':
      return [
        'Almost there',
        jsx(
          'p',
          { children: `The new version is installed, but ${update.error ?? 'its last steps did not finish'}. Finish the update to load it everywhere.` },
          'p'
        ),
        update.blocked ? jsxs('p', { className: 'cs-upd-wait', role: 'status', children: [jsx(Codicon, { name: 'clock', size: 12 }), update.blocked] }, 'wait') : null,
        actions(
          jsx(Button, { disabled: Boolean(update.blocked), onClick: update.start, size: 'sm', variant: 'default', children: 'Finish update' }, 'finish'),
          jsx(Button, { onClick: update.openPlugins, size: 'sm', variant: 'link', children: 'Open Capabilities → Plugins' }, 'plugins')
        )
      ]
    case 'restart':
      return [
        'Almost done',
        jsx('p', { children: 'The new version is installed. Quit and reopen Hermes to finish loading it; until then hermretro keeps working.' }, 'p'),
        actions(jsx(Button, { onClick: () => update.setOpen(false), size: 'sm', variant: 'outline', children: 'Got it' }, 'ok'))
      ]
    case 'done':
      return ['Up to date', jsx('p', { children: 'Your games, library and chats are kept. New chats use the new version.' }, 'p'), actions(whatsNew)]
    default:
      return [
        'A new version is ready',
        jsx('p', { children: 'Your games, library and chats are kept. It takes about a minute.' }, 'p'),
        update.version ? jsxs('p', { className: 'cs-upd-kv', children: [jsx('b', { children: 'Installed' }), update.version] }, 'kv') : null,
        update.blocked ? jsxs('p', { className: 'cs-upd-wait', role: 'status', children: [jsx(Codicon, { name: 'clock', size: 12 }), update.blocked] }, 'wait') : null,
        actions(
          jsx(Button, { disabled: Boolean(update.blocked), onClick: update.start, size: 'sm', variant: 'default', children: 'Update now' }, 'go'),
          whatsNew,
          jsx('span', { className: 'cs-upd-fill' }, 'fill'),
          jsx(Button, { onClick: update.later, size: 'sm', variant: 'ghost', children: 'Later' }, 'later')
        )
      ]
  }
}

/** `update` is shell.pluginUpdate (use-update.js). */
export function UpdateChip({ update }) {
  const root = useRef(null)
  const { open, phase, setOpen } = update

  useEffect(() => {
    if (!open || phase === 'updating') {
      return undefined
    }

    const away = event => {
      if (!root.current?.contains(event.target)) {
        setOpen(false)
      }
    }
    const escape = event => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    window.addEventListener('pointerdown', away, true)
    window.addEventListener('keydown', escape, true)

    return () => {
      window.removeEventListener('pointerdown', away, true)
      window.removeEventListener('keydown', escape, true)
    }
  }, [open, phase])

  if (!update.visible) {
    return null
  }

  const [tone, label] = CHIP[phase] ?? CHIP.idle
  const [title, ...rest] = body(update)

  return jsxs('span', {
    className: 'cs-upd',
    ref: root,
    children: [
      jsxs('button', {
        'aria-expanded': open,
        'aria-haspopup': 'dialog',
        'aria-label': `hermretro: ${label}`,
        className: `cs-chip cs-upd-chip ${tone}`,
        'data-phase': phase,
        onClick: () => setOpen(!open),
        title: label,
        type: 'button',
        children: [phase === 'updating' ? jsx(Codicon, { name: 'loading', size: 11, spinning: true }) : jsx('i', {}), jsx('span', { className: 'cs-lbl', children: label })]
      }),
      open
        ? jsxs('div', {
            'aria-label': 'hermretro update',
            className: 'cs-upd-pop',
            role: 'dialog',
            children: [jsx('p', { className: 'cs-eyebrow', children: 'hermretro' }), jsx('h3', { className: 'cs-word', children: title }), ...rest]
          })
        : null
    ]
  })
}
