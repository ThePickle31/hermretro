// External links and copyable command lines.
import { Button, Codicon, CopyButton, jsx, jsxs } from '../sdk.js'
import { S } from '../styles/tokens.js'

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
