// Frames from the player: saved captures, annotations and Ask Hermes.
import { host } from '../sdk.js'
import { callStudio, studioError } from '../core/backend.js'
import { sendToGameChat } from '../core/chat-insert.js'
import { RPC_CAPTURE_IMAGE } from '../core/rpc.js'

/** Save a frame into the game's captures folder; the path goes into the chat text. */
export async function saveCapture(game, png) {
  if (!png) {
    return { path: null, failure: 'the frame could not be captured' }
  }

  try {
    const result = await callStudio(RPC_CAPTURE_IMAGE, { id: game.id, png })

    return result?.path ? { path: result.path, failure: null } : { path: null, failure: result?.error || 'no path returned' }
  } catch (error) {
    return { path: null, failure: studioError(error, 'save screenshots') }
  }
}

export function annotationText(game, data, path) {
  const target = data.target ?? {}
  const role = String(target.role ?? '').replace(/^game-/, '')
  const lines = [`In ${game.title}, I marked ${target.name || 'part of the screen'}${role ? ` (${role})` : ''}.`]

  if (data.note) {
    lines.push(String(data.note))
  }

  if (target.metadata && typeof target.metadata === 'object' && Object.keys(target.metadata).length) {
    lines.push(`Details: ${JSON.stringify(target.metadata).slice(0, 800)}`)
  }

  if (path) {
    lines.push(`Screenshot: ${path}`)
  }

  return lines.join('\n')
}

/** An annotation from the player: save the marked frame, then put the note into the game's chat. */
export async function annotateGame(ctx, game, data) {
  if (!game) {
    return
  }

  const { path, failure } = await saveCapture(game, typeof data.image === 'string' ? data.image : '')

  await sendToGameChat(ctx, game, annotationText(game, data, path))

  if (failure) {
    host.notify({ kind: 'warning', message: `The screenshot was not saved: ${failure}` })
  }
}

/** Ask Hermes: the current frame and a line about it go into the game's chat, not sent. */
export async function askAboutGame(ctx, game, snap) {
  if (!game) {
    return
  }

  const { path, failure } = await saveCapture(game, await snap())

  await sendToGameChat(ctx, game, [`Here is what ${game.title} shows right now.`, path ? `Screenshot: ${path}` : null].filter(Boolean).join('\n') + '\n')

  if (failure) {
    host.notify({ kind: 'warning', message: `The screenshot was not saved: ${failure}` })
  }
}
