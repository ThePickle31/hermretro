// The corner card that says a new version is out, once per version: what it changes, Later and Update. A click
// anywhere else, or Escape, puts it away like Later; the header chip stays and opens the full dialog.
import { Button, jsx, useEffect, useRef } from '#sdk'
import { ReleaseNotes } from './release-notes.js'
import { Fill, UpdateButton, UpdateFoot, UpdateHead, WaitLine } from './update-parts.js'

/** `update` is shell.pluginUpdate (use-update.js). */
export function UpdateCard({ update }) {
  const root = useRef(null)
  const { card, later } = update

  useEffect(() => {
    if (!card) {
      return undefined
    }

    const away = event => {
      if (!root.current?.contains(event.target)) {
        later()
      }
    }
    const escape = event => {
      if (event.key === 'Escape') {
        later()
      }
    }

    window.addEventListener('pointerdown', away, true)
    window.addEventListener('keydown', escape, true)

    return () => {
      window.removeEventListener('pointerdown', away, true)
      window.removeEventListener('keydown', escape, true)
    }
  }, [card])

  if (!card) {
    return null
  }

  return jsx('div', {
    className: 'cs-upd-card',
    ref: root,
    children: jsx('div', {
      'aria-label': 'hermretro update',
      className: 'cs-upd-dlg',
      role: 'dialog',
      children: [
        jsx(UpdateHead, { accent: 'ready', from: update.version, onClose: later, title: 'Update', to: update.latest }, 'h'),
        jsx(ReleaseNotes, { releases: update.notes }, 'n'),
        jsx(WaitLine, { text: update.blocked }, 'w'),
        jsx(UpdateFoot, { children: [jsx(Button, { onClick: later, size: 'sm', variant: 'ghost', children: 'Later' }, 'later'), jsx(Fill, {}, 'fill'), jsx(UpdateButton, { update }, 'go')] }, 'f')
      ]
    })
  })
}

