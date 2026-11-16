// The annotate overlay laid over the game canvas: a light veil, the box under the pointer with a
// label naming it, every marked object numbered, and a "Frozen" tag. Positions are kept as fractions
// of the canvas, so the overlay follows the canvas when the frame is resized.
import { targetLabel } from '../player/targets.js'

const element = (className, text) => {
  const node = document.createElement('div')

  node.className = className

  if (text !== undefined) {
    node.textContent = text
  }

  return node
}

/** Fractions of `bounds` covered by a viewport rectangle from the engine's hit test. */
export function boxIn(rect, bounds) {
  return {
    x: (rect.x - bounds.left) / bounds.width,
    y: (rect.y - bounds.top) / bounds.height,
    w: rect.width / bounds.width,
    h: rect.height / bounds.height
  }
}

export function createOverlay(surfaceElement, { tip = null, onMove, onDown }) {
  const root = element('hr-ann')
  const layer = element('hr-layer')

  root.append(element('hr-veil'), layer, element('hr-frozen', 'Frozen'))

  if (tip) {
    root.append(element('hr-tip', tip))
  }

  let bounds = surfaceElement.getBoundingClientRect()

  const place = () => {
    bounds = surfaceElement.getBoundingClientRect()
    Object.assign(root.style, { left: `${bounds.left}px`, top: `${bounds.top}px`, width: `${bounds.width}px`, height: `${bounds.height}px` })
  }

  const boxNode = (className, box) => {
    const node = element(`hr-box ${className}`)

    Object.assign(node.style, {
      left: `${box.x * bounds.width}px`,
      top: `${box.y * bounds.height}px`,
      width: `${box.w * bounds.width}px`,
      height: `${box.h * bounds.height}px`
    })

    return node
  }

  /** Redraw from scratch: a handful of nodes, so this stays cheap on every pointer move. */
  const draw = ({ hovered, marks, selectedId }) => {
    const nodes = []

    for (const mark of marks) {
      const node = boxNode(mark.id === selectedId ? 'mark on' : 'mark', mark.box)

      const badge = element('hr-n', String(mark.n))

      // At the top or right edge of the screen the badge would be cut off: tuck it inside the box.
      badge.classList.toggle('in-top', mark.box.y * bounds.height < 10)
      badge.classList.toggle('in-right', (mark.box.x + mark.box.w) * bounds.width > bounds.width - 10)
      node.append(badge)
      nodes.push(node)
    }

    if (hovered && !marks.some(mark => mark.id === hovered.id)) {
      nodes.push(boxNode('hov', hovered.box))

      const label = element('hr-label', targetLabel(hovered.name, hovered.role))

      Object.assign(label.style, { left: `${Math.min(hovered.box.x * bounds.width, bounds.width - 140)}px`, top: `${Math.max(hovered.box.y * bounds.height, 30)}px` })
      nodes.push(label)
    }

    layer.replaceChildren(...nodes)
  }

  root.addEventListener('pointermove', event => onMove(event))
  root.addEventListener('pointerdown', event => onDown(event))
  addEventListener('resize', place)
  place()
  document.body.append(root)

  return {
    root,
    place,
    draw,
    bounds: () => bounds,
    remove() {
      removeEventListener('resize', place)
      root.remove()
    }
  }
}
