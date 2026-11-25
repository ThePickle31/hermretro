// The full-screen update dialog: what a new version changes and its Update button, the update's steps while it runs,
// and how it ended. Opened from the header chip or the corner card's Update; closes on Escape, the close button or a
// click beside it, except while updating.
import { Button, Codicon, jsx, jsxs, useEffect, useRef } from '#sdk'
import { UPDATE_STEPS } from './flow.js'
import { ReleaseNotes } from './release-notes.js'
import { Fill, UpdateButton, UpdateFoot, UpdateHead, WaitLine } from './update-parts.js'

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
            index < step ? jsx(Codicon, { name: 'check', size: 13 }) : index === step ? jsx(Codicon, { name: 'loading', size: 13, spinning: true }) : jsx('i', {}),
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

const p = (text, key = 'p') => jsx('p', { className: 'cs-upd-text', children: text }, key)

/** [head, ...rest] for each phase. */
function content(update, close) {
  const versions = { from: update.version, to: update.latest }
  const plugins = jsx(Button, { onClick: update.openPlugins, size: 'sm', variant: 'link', children: 'Open Capabilities → Plugins' }, 'plugins')

  switch (update.phase) {
    case 'updating':
      return [
        jsx(UpdateHead, { title: 'Updating', ...versions }, 'h'),
        jsx('div', { className: 'cs-upd-bar', children: jsx('i', { style: { width: `${((update.step + 1) / UPDATE_STEPS.length) * 100}%` } }) }, 'bar'),
        jsx(Steps, { step: update.step, waiting: update.waiting }, 's'),
        jsx(UpdateFoot, { children: jsx('span', { className: 'cs-upd-note', children: 'You can keep using Hermes.' }) }, 'f')
      ]
    case 'review':
      return [
        jsx(UpdateHead, { title: 'Review the new version', onClose: close, ...versions }, 'h'),
        jsxs(
          'div',
          {
            className: 'cs-upd-body',
            children: [
              p(
                update.review?.findings?.length
                  ? "Hermes's security check found something to look at before installing it. Nothing has changed yet."
                  : 'The new version adds to what hermretro can do in Hermes. Nothing has changed yet.'
              ),
              update.review ? jsx(Findings, { review: update.review }, 'f') : null
            ]
          },
          'b'
        ),
        jsx(
          UpdateFoot,
          {
            children: [
              jsx(Button, { onClick: update.cancel, size: 'sm', variant: 'ghost', children: 'Cancel' }, 'no'),
              jsx(Fill, {}, 'fill'),
              jsx(Button, { disabled: Boolean(update.blocked), onClick: update.agree, size: 'sm', variant: 'default', children: 'Install anyway' }, 'yes')
            ]
          },
          'f'
        )
      ]
    case 'failed':
      return [
        jsx(UpdateHead, { title: "Couldn't update", onClose: close }, 'h'),
        jsx('div', { className: 'cs-upd-body', children: p(`${update.error ?? 'The update did not finish.'} Nothing was changed${update.version ? `; you are still on ${update.version}` : ''}.`) }, 'b'),
        jsx(UpdateFoot, { children: [plugins, jsx(Fill, {}, 'fill'), jsx(Button, { disabled: Boolean(update.blocked), onClick: update.start, size: 'sm', variant: 'default', children: 'Try again' }, 'again')] }, 'f')
      ]
    case 'partial':
      return [
        jsx(UpdateHead, { title: 'Almost there', onClose: close }, 'h'),
        jsx(
          'div',
          {
            className: 'cs-upd-body',
            children: p(`The new version is installed, but ${String(update.error ?? 'its last steps did not finish').replace(/\.$/, '')}. Finish the update to load it everywhere.`)
          },
          'b'
        ),
        jsx(WaitLine, { text: update.blocked }, 'w'),
        jsx(UpdateFoot, { children: [plugins, jsx(Fill, {}, 'fill'), jsx(Button, { disabled: Boolean(update.blocked), onClick: update.finish, size: 'sm', variant: 'default', children: 'Finish update' }, 'finish')] }, 'f')
      ]
    case 'restart':
      return [
        jsx(UpdateHead, { title: 'Almost done', onClose: close }, 'h'),
        jsx('div', { className: 'cs-upd-body', children: p(`The new version is installed. ${update.restartAdvice} to finish loading it; until then hermretro keeps working.`) }, 'b'),
        jsx(UpdateFoot, { children: [jsx(Fill, {}, 'fill'), jsx(Button, { onClick: close, size: 'sm', variant: 'default', children: 'Got it' }, 'ok')] }, 'f')
      ]
    case 'done':
      return [
        jsx(UpdateHead, { title: 'You’re on', accent: update.version, onClose: close }, 'h'),
        jsx(ReleaseNotes, { releases: update.installedNotes }, 'n'),
        jsx(
          UpdateFoot,
          {
            children: [
              jsxs('span', { className: 'cs-upd-ok', children: [jsx(Codicon, { name: 'check', size: 13 }), 'Ready to use'] }, 'ok'),
              jsx(Fill, {}, 'fill'),
              jsx(Button, { onClick: close, size: 'sm', variant: 'default', children: 'Done' }, 'done')
            ]
          },
          'f'
        )
      ]
    default:
      return [
        jsx(UpdateHead, { title: 'A new version', accent: 'is ready', onClose: close, ...versions }, 'h'),
        jsx(ReleaseNotes, { releases: update.notes }, 'n'),
        update.notes.length ? null : jsxs(Button, { className: 'cs-upd-link', onClick: update.whatsNew, size: 'sm', variant: 'link', children: ["What's new", jsx(Codicon, { name: 'link-external', size: 12 })] }, 'new'),
        jsx(WaitLine, { text: update.blocked }, 'w'),
        jsx(
          UpdateFoot,
          {
            children: [
              jsx(Button, { onClick: update.queued ? update.cancel : close, size: 'sm', variant: 'ghost', children: update.queued ? 'Cancel' : 'Later' }, 'later'),
              jsx(Fill, {}, 'fill'),
              jsx(UpdateButton, { update }, 'go')
            ]
          },
          'f'
        )
      ]
  }
}

const FOCUSABLE = 'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

/** `update` is shell.pluginUpdate (use-update.js). */
export function UpdateDialog({ update }) {
  const { open, phase, setOpen } = update
  const closable = phase !== 'updating'
  const close = () => setOpen(false)
  const box = useRef(null)
  const shown = open && !(phase === 'idle' && !update.ready)

  // A modal: focus moves into it, Tab stays inside, and focus goes back where it was when it closes.
  useEffect(() => {
    if (!shown) {
      return undefined
    }

    const before = document.activeElement
    const inside = () => [...(box.current?.querySelectorAll(FOCUSABLE) ?? [])]

    ;(inside()[0] ?? box.current)?.focus()

    const tab = event => {
      if (event.key !== 'Tab') {
        return
      }

      const items = inside()

      if (!items.length) {
        event.preventDefault()

        return
      }

      const at = items.indexOf(document.activeElement)
      const next = event.shiftKey ? (at <= 0 ? items.length - 1 : at - 1) : at === -1 || at === items.length - 1 ? 0 : at + 1

      event.preventDefault()
      items[next].focus()
    }

    window.addEventListener('keydown', tab, true)

    return () => {
      window.removeEventListener('keydown', tab, true)
      before?.focus?.()
    }
  }, [shown])

  useEffect(() => {
    if (!shown || !closable) {
      return undefined
    }

    const escape = event => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    window.addEventListener('keydown', escape, true)

    return () => window.removeEventListener('keydown', escape, true)
  }, [shown, closable])

  if (!shown) {
    return null
  }

  return jsx('div', {
    className: 'cs-upd-scrim',
    onPointerDown: event => {
      if (closable && event.target === event.currentTarget) {
        close()
      }
    },
    children: jsx('div', {
      'aria-label': 'hermretro update',
      'aria-modal': 'true',
      className: 'cs-upd-dlg',
      ref: box,
      role: 'dialog',
      tabIndex: -1,
      children: content(update, closable ? close : null)
    })
  })
}
