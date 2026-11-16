// Where the user's games live, with a button that opens the folder (the Games page's own chrome).
import { Button, Codicon, host, jsx, jsxs } from '../sdk.js'

async function openFolder(ctx, path) {
  const shown = await ctx.os?.revealPath?.(path).catch(() => false)

  if (!shown) {
    const copied = await ctx.os?.writeClipboard?.(path).catch(() => false)

    host.notify({ kind: 'info', message: copied ? 'The games folder is on the computer running Hermes. Its path is copied.' : path })
  }
}

export function GamesFolder({ ctx, path }) {
  if (typeof path !== 'string' || !path) {
    return null
  }

  return jsxs('div', {
    className: 'cs-gfolder',
    children: [
      jsx('span', { className: 'cs-faint', children: 'Games folder' }),
      jsx('span', { className: 'cs-mono', title: path, children: path }),
      jsxs(Button, {
        onClick: () => void openFolder(ctx, path),
        size: 'sm',
        variant: 'ghost',
        children: [jsx(Codicon, { name: 'folder-opened', size: 14 }), 'Open games folder']
      })
    ]
  })
}
