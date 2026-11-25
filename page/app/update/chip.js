// The header's update chip: shown while an update is ready, running or just finished. It opens the update dialog.
import { Codicon, jsx, jsxs } from '#sdk'

const CHIP = {
  idle: ['accent', 'Update ready'],
  updating: ['accent', 'Updating'],
  review: ['warn', 'Needs a look'],
  failed: ['bad', 'Update failed'],
  restart: ['warn', 'Restart to finish'],
  partial: ['bad', 'Finish update'],
  done: ['good', 'Updated']
}

/** `update` is shell.pluginUpdate (use-update.js). */
export function UpdateChip({ update }) {
  if (!update.visible) {
    return null
  }

  const { open, phase, setOpen } = update
  const [tone, label] = CHIP[phase] ?? CHIP.idle

  return jsx('span', {
    className: 'cs-upd',
    children: jsxs('button', {
      'aria-expanded': open,
      'aria-haspopup': 'dialog',
      'aria-label': `hermretro: ${label}`,
      className: `cs-chip cs-upd-chip ${tone}`,
      'data-phase': phase,
      onClick: () => setOpen(true),
      title: label,
      type: 'button',
      children: [phase === 'updating' ? jsx(Codicon, { name: 'loading', size: 11, spinning: true }) : jsx('i', {}), jsx('span', { className: 'cs-lbl', children: label })]
    })
  })
}
