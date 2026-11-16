// An attachment (build-chat/attachments.js) as a chip, in the message box and in the sent message.
import { Codicon, jsx, jsxs } from '../sdk.js'
import { baseName } from '../core/paths.js'

export function AttachmentChip({ item, onRemove = null }) {
  const label = item.name || baseName(item.path)

  return jsxs('span', {
    className: item.image ? 'cs-b-chip mention pic' : 'cs-b-chip mention',
    title: item.path,
    children: [
      item.image ? jsx('img', { alt: '', src: item.image }) : '@',
      label,
      onRemove
        ? jsx('button', { 'aria-label': `Remove ${label}`, className: 'cs-b-x', onClick: () => onRemove(item), type: 'button', children: jsx(Codicon, { name: 'close', size: 10 }) })
        : null
    ]
  })
}
