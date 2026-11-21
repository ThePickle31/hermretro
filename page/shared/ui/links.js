// External links and copyable command lines.
import { Button, Codicon, CopyButton, jsx, jsxs } from '#sdk'
import { S } from '#shared/styles/tokens.js'

// Pages outside hermretro that several pages link to.
export const LINKS = {
  node: 'https://nodejs.org/',
  firmware: 'https://support.modretro.com/en_us/articles/chromatic-firmware-updater-ryhoYnzCx',
  quickstart: 'https://support.modretro.com/en_us/chromatic-codex-edition-quickstart-guide-By1iOlcMg',
  releases: 'https://github.com/ThePickle31/hermretro/releases'
}

export function ExternalLink({ ctx, href, children, variant = 'link' }) {
  return jsxs(Button, {
    onClick: () => void ctx.os.openExternal(href),
    size: variant === 'link' ? 'inline' : 'sm',
    variant,
    children: [children, jsx(Codicon, { name: 'link-external', size: 12 })]
  })
}

export function CommandLine({ command }) {
  return jsxs('div', {
    style: { ...S.row, gap: 4 },
    children: [
      jsx('code', { className: 'font-mono', style: S.code, children: command }),
      jsx(CopyButton, { appearance: 'icon', label: 'Copy command', text: command })
    ]
  })
}
