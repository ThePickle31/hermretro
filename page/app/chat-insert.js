// "Use in chat": prompts go into a chat's message box, never sent for the user.
import { host } from '#sdk'
import { STUDIO_PROFILE } from './ids.js'
import { studioTarget } from './routing.js'

async function insertText(target, text) {
  try {
    return (await host.composer.insertText(target, text, { mode: 'block' })) === true
  } catch {
    return false
  }
}

/** A freshly opened chat needs a beat to mount its composer. */
async function insertWhenMounted(ctx, target, text) {
  const sleep = ms => new Promise(resolve => ctx.setTimeout(resolve, ms))

  for (const delay of [150, 250, 400, 600, 900]) {
    await sleep(delay)

    if (await insertText(target, text)) {
      return true
    }
  }

  return false
}

const promptAdded = () => host.notify({ kind: 'success', message: 'Prompt added to the composer' })

/** Put a prompt into a chat composer without sending it. Order: the composer
 *  the user is in → the focused chat's composer → a fresh chat → clipboard.
 *  `fresh` skips straight to a new chat ("Start a new chat"). */
export async function sendPromptToChat(ctx, prompt, { fresh = false } = {}) {
  // Only a chat in the hermretro profile has hermretro's tools; no other profile is ever used.
  const target = studioTarget()

  if (!target) {
    const copied = await ctx.os.writeClipboard(prompt).catch(() => false)

    host.notify({
      kind: 'warning',
      message: `The hermretro profile is not set up yet, so no chat can use this prompt. Create it on Setup (Profile step), then ask Hermes there${copied ? '; the prompt is copied' : ''}.`
    })

    return
  }

  const profile = target.profile

  if (!profile && !fresh) {
    if (await insertText(null, prompt)) {
      promptAdded()

      return
    }

    const focused = host.state.focusedSessionId.get()

    if (focused && (await insertText(focused, prompt))) {
      promptAdded()

      return
    }
  }

  if (typeof host.newChat === 'function') {
    try {
      profile ? host.newChat(profile) : host.newChat()

      if (await insertWhenMounted(ctx, 'new', prompt)) {
        promptAdded()

        return
      }
    } catch {
      // fall through to the clipboard
    }
  }

  const copied = await ctx.os.writeClipboard(prompt).catch(() => false)

  host.notify(
    copied
      ? { kind: 'info', message: 'Prompt copied — paste it into a chat to use it.' }
      : { kind: 'warning', message: 'Could not reach a chat composer or the clipboard. Copy the prompt from the page.' }
  )
}

/** The game's own conversation: its Build conversation when it has one in this profile, else the chat that last
 *  worked on it (from the games registry); null without either. */
function gameConversation(game) {
  const session = game?.session

  if (session?.storedId && session.thisProfile !== false && session.exists !== false) {
    return { stored: session.storedId, profile: session.profileName ?? null }
  }

  return game?.chat?.sessionId ? { stored: game.chat.sessionId, profile: game.chat.profile ?? null } : null
}

/** Open the game's own chat (its Build conversation first); answers its stored session id, or null. */
export async function openGameChat(game) {
  const conversation = gameConversation(game)
  const target = studioTarget()
  // A chat made in another profile (before chats lived only in hermretro) is not opened there.
  const inStudio = conversation?.profile ? conversation.profile === STUDIO_PROFILE : true
  const stored = conversation?.stored

  if (!stored || !target || !inStudio || typeof host.openSession !== 'function') {
    return null
  }

  try {
    await host.openSession(stored, target.profile ? { profile: target.profile } : {})

    return stored
  } catch {
    return null
  }
}

/** Text about one game goes into that game's own chat (opened, not sent); without one, into a new hermretro chat,
 *  never the chat the user happens to be in, which may be another game's. */
export async function sendToGameChat(ctx, game, text) {
  const stored = await openGameChat(game)

  // Into that chat's own composer by its id: never the active one, which may by then be another game's.
  if (stored && (await insertWhenMounted(ctx, stored, text))) {
    promptAdded()

    return
  }

  await sendPromptToChat(ctx, text, { fresh: true })
}
