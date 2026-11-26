// hermretro's page under Settings → Plugins (ctx.registerSettingsPage): the factory reset. Hermes folds the plugin's
// own settings (plugin.yaml config_schema) under it as "Agent settings".
import { Button, jsx, jsxs, ListRow } from '#sdk'
import { RESET_CSS } from './reset.css.js'
import { ResetDialog } from './reset-dialog.js'
import { useReset } from './use-reset.js'

export function SettingsPage({ ctx }) {
  const reset = useReset(ctx)

  return jsxs('div', {
    className: 'cs-rst-page',
    children: [
      jsx('style', { children: RESET_CSS }),
      jsx('h3', { className: 'cs-rst-head', children: 'Reset' }),
      jsx('div', {
        className: 'cs-rst-card',
        children: jsx(ListRow, {
          title: 'Factory reset',
          action: jsx(Button, { onClick: reset.open, size: 'sm', variant: 'destructive', children: 'Factory reset…' })
        })
      }),
      jsx(ResetDialog, { reset })
    ]
  })
}
