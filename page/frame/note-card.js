// The note card for surfaces without a play-test panel (the Emulator page and the tab beside the
// chat): name the picked object, type what should change, Ask HermRetro.
import { targetLabel } from '#shared/player/targets.js'

export function openNoteCard(overlay, target, { onAsk, onCancel }) {
  overlay.root.querySelector('.hr-card')?.remove()

  const bounds = overlay.bounds()
  const card = document.createElement('div')
  const title = document.createElement('b')
  const kind = document.createElement('small')
  const note = document.createElement('textarea')
  const actions = document.createElement('div')
  const cancel = document.createElement('button')
  const ask = document.createElement('button')

  card.className = 'hr-card'
  title.textContent = targetLabel(target.name, target.role)
  kind.textContent = target.name || 'Part of the screen'
  note.placeholder = 'What should HermRetro change or check here?'
  cancel.textContent = 'Cancel'
  ask.textContent = 'Ask HermRetro'
  ask.dataset.primary = 'true'
  actions.append(cancel, ask)
  card.append(title, kind, note, actions)

  const below = bounds.top + (target.box.y + target.box.h) * bounds.height + 10

  card.style.left = `${Math.min(innerWidth - 300, Math.max(8, bounds.left + target.box.x * bounds.width))}px`
  card.style.top = `${Math.min(innerHeight - 180, below)}px`
  cancel.addEventListener('click', () => {
    card.remove()
    onCancel()
  })
  ask.addEventListener('click', () => onAsk(note.value))
  // Keys and clicks in the card are the card's, not the game's or the overlay's.
  card.addEventListener('pointerdown', event => event.stopPropagation())
  card.addEventListener('keydown', event => event.stopPropagation())
  overlay.root.append(card)
  note.focus()
}
