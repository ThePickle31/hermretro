// The Emulator page's row for opening the game beside the chat.
import { Button, Codicon, host, jsx, jsxs } from '#sdk'
import { openSideEmulator } from './tab.js'

/** Under the Emulator page's player: the user's own way to move the game beside the chat. */
export function SideEmulatorRow({ ctx, game }) {
  const canOpen = typeof host.openWorkspace === 'function'

  return jsxs('div', {
    className: 'cs-rp-foot',
    children: [
      jsx('span', { className: 'cs-rp-hint', children: 'Hermes shows your game beside the chat when it is ready for you to try.' }),
      jsx('span', { className: 'cs-grow' }),
      canOpen && game
        ? jsxs(Button, {
            onClick: () => openSideEmulator(ctx, game),
            size: 'sm',
            variant: 'ghost',
            children: [jsx(Codicon, { name: 'split-horizontal', size: 14 }), 'Open beside the chat']
          })
        : null
    ]
  })
}
