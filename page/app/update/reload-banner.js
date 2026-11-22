// The page-wide banner while Hermes runs older hermretro code than is on disk (status `restart_needed`): an update made
// outside this page (a terminal, Capabilities > Plugins, git). Reload loads it without a restart (use-update.js).
import { Button, Codicon, jsx, jsxs } from '#sdk'

function banner(tone, icon, text, ...actions) {
  return jsxs('div', {
    className: tone ? `cs-repair ${tone}` : 'cs-repair',
    role: 'status',
    children: [jsx(Codicon, { name: icon, size: 14 }), jsx('span', { children: text }), ...actions]
  })
}

/** `update` is shell.pluginUpdate (use-update.js). */
export function ReloadBanner({ update }) {
  const { reload } = update

  if (reload.phase === 'failed') {
    return banner(
      'bad',
      'warning',
      `Reload did not finish: ${String(reload.error ?? 'no answer').replace(/\.$/, '')}.`,
      jsx(Button, { disabled: Boolean(reload.blocked), onClick: reload.start, size: 'sm', variant: 'outline', children: 'Try again' }, 'again')
    )
  }

  if (reload.phase === 'restart') {
    return banner(null, 'refresh', 'hermretro was updated. Restart Hermes to finish loading it.')
  }

  const reloading = reload.phase === 'reloading'

  return banner(
    null,
    'refresh',
    'hermretro was updated, but Hermes is still running the old version.',
    reload.blocked && !reloading ? jsxs('span', { className: 'cs-repair-wait', children: [jsx(Codicon, { name: 'clock', size: 12 }), reload.blocked] }, 'wait') : null,
    jsxs(
      Button,
      {
        disabled: reloading || Boolean(reload.blocked),
        onClick: reload.start,
        size: 'sm',
        variant: 'outline',
        children: [reloading ? jsx(Codicon, { name: 'loading', size: 12, spinning: true }, 'spin') : null, reloading ? 'Reloading' : 'Reload']
      },
      'reload'
    )
  )
}
