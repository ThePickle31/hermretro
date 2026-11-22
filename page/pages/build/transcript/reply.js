// A reply's text and the images it delivered.
import { jsx, jsxs, memo, MessageTextContent } from '#sdk'
import { useAsset } from '#pages/build/assets/cache.js'
import { SheetFrame } from '#pages/build/assets/images.js'
import { isAbsolute, joinPath } from '#app/paths.js'
import { assetKind } from './step-words.js'

// A line that is only `MEDIA:<image>` (the path may hold spaces, or sit in quotes or backticks).
const MEDIA_IMAGE_LINE = /^[ \t]*MEDIA:[ \t]*([`"']?)(.+?\.(?:png|gif|jpe?g|webp))\1[ \t]*$/gim

/** A reply split around its image `MEDIA:` lines: text for the app's markdown, images for the page. */
function replySegments(text, root) {
  const segments = []
  let from = 0

  for (const match of String(text ?? '').matchAll(MEDIA_IMAGE_LINE)) {
    const raw = match[2].trim().replace(/^file:\/\//, '')
    const path = isAbsolute(raw) ? raw : joinPath(root, raw)

    if (!path) {
      continue
    }

    segments.push({ type: 'text', text: text.slice(from, match.index) })
    segments.push({ type: 'image', path, line: match[0] })
    from = match.index + match[0].length
  }

  segments.push({ type: 'text', text: String(text ?? '').slice(from) })

  return segments.filter(segment => segment.type === 'image' || segment.text.trim())
}

/** The images a turn's replies delivered, as viewer assets (a reply's time versions the file: a later
 *  turn that rewrote cover.png fetches it again). */
export function replyAssets(items, root) {
  return items.flatMap(item =>
    replySegments(item.text, root)
      .filter(segment => segment.type === 'image')
      .map(segment => ({ path: segment.path, version: `reply:${item.at ?? ''}`, kind: assetKind(segment.path), step: 'In the reply', at: item.at ?? null }))
  )
}

/** A picture the reply delivered, as a small card (the reply stays words; the Assets panel and the
 *  viewer show pictures big): a click opens the asset viewer. Another game's picture stays an inert line (the app
 *  would read the file itself); anything else the backend will not give (outside the games) stays the app's own
 *  MEDIA rendering. */
function ReplyImage({ asset, line, onOpen }) {
  const { state, code, asset: loaded } = useAsset(asset.path, asset.version)

  if (state === 'none') {
    return MessageTextContent ? jsx(MessageTextContent, code === 'OTHER_GAME' ? { media: false, previewOnly: true, text: line } : { text: line }) : null
  }

  if (state === 'loading') {
    return jsx('span', { 'aria-hidden': true, className: 'cs-b-rchip loading' })
  }

  const kind = loaded.kind === 'sprite' ? 'Sprite' : loaded.kind === 'background' ? 'Background' : /(^|[\\/])cover\.png$/i.test(asset.path) ? 'Game cover' : asset.kind

  return jsxs('button', {
    'aria-label': `Look closer at ${loaded.name}`,
    className: 'cs-b-rchip',
    onClick: event => {
      event.stopPropagation()
      onOpen?.(asset)
    },
    title: `${loaded.name} · ${loaded.width}×${loaded.height}`,
    type: 'button',
    children: [
      jsx('span', { className: 'cs-b-th sm', children: jsx(SheetFrame, { loaded }) }),
      jsxs('span', {
        className: 'cs-col',
        children: [jsx('b', { children: loaded.sprite?.name || loaded.name }), jsx('span', { children: `${kind} · ${loaded.width}×${loaded.height}` })]
      })
    ]
  })
}

// Markdown is rendered once per text: only the block still streaming re-renders as tokens arrive.
export const AgentText = memo(
  ({ item, root, onOpenAsset }) => {
    const segments = replySegments(item.text, root)
    const media = replyAssets([item], root)

    // Pictures next to each other sit in one row of small cards.
    const blocks = []

    segments.forEach((segment, index) => {
      if (segment.type === 'image') {
        const asset = media.find(entry => entry.path === segment.path)
        const chip = jsx(ReplyImage, { asset, line: segment.line, onOpen: onOpenAsset }, `m${index}`)
        const last = blocks[blocks.length - 1]

        if (last?.images) {
          last.images.push(chip)
        } else {
          blocks.push({ images: [chip], key: `r${index}` })
        }
      } else {
        blocks.push(MessageTextContent ? jsx(MessageTextContent, { text: segment.text }, `t${index}`) : jsx('span', { children: segment.text }, `t${index}`))
      }
    })

    return jsx('div', {
      className: 'cs-b-agent',
      children: blocks.map(block => (block?.images ? jsx('div', { className: 'cs-b-rimgs', children: block.images }, block.key) : block))
    })
  },
  (previous, next) => previous.item.text === next.item.text && previous.root === next.root && previous.onOpenAsset === next.onOpenAsset
)
