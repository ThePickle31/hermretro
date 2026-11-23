// Track one viewer change per conversation, even if the viewer closes or shows another picture.
import { sendBuildChat } from '#pages/build/chat/actions.js'
import { BUILD_CHATS, buildChatIdle, patchChat } from '#pages/build/chat/store.js'
import { forgetAsset } from './cache.js'

export const canSendAssetChange = chat => buildChatIdle(chat) && !chat.assetChange
export const assetRestoreBlocked = chat => Boolean(chat?.busy || chat?.assetChange)

export async function sendAssetChange(stored, text, shown, attachments) {
  if (!canSendAssetChange(BUILD_CHATS.get()[stored])) {
    return false
  }

  const change = { path: attachments[0].path, text: shown }

  patchChat(stored, chat => ({ ...chat, assetChange: change }))

  let started = false
  let completed = false
  let accepted = null

  const finish = () => {
    const chat = BUILD_CHATS.get()[stored]

    started ||= chat.items.at(-1)?.assetChange === change
    completed ||= started && !chat.busy && !chat.opening

    if (accepted === null || (accepted && !completed)) {
      return
    }

    stop()
    if (accepted) {
      forgetAsset(change.path)
    }
    patchChat(stored, current => ({ ...current, assetChange: null, ...(accepted ? { lastAssetChange: change } : {}) }))
  }
  const stop = BUILD_CHATS.listen(finish)

  try {
    accepted = await sendBuildChat(stored, text, shown, attachments, { assetChange: change, mustLand: true })

    return accepted
  } finally {
    accepted ??= false
    finish()
  }
}
