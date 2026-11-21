// Choosing the model and effort of a Build conversation.
import { host } from '#sdk'
import { describeRequestError } from '#app/backend.js'
import { withInfo } from './steps.js'
import { BUILD_CHATS, chatRequest, patchChat } from './store.js'

/** Fast mode (OpenAI's priority tier) is offered only for ChatGPT or Codex Subscription models that list it
 *  (`model.options` `capabilities[model].fast`). */
export const FAST_PROVIDER = 'openai-codex'
export const hasFastMode = (provider, caps) => provider === FAST_PROVIDER && caps?.fast === true

/** Change the model (`{model, provider}`), effort (`{effort}`) and/or fast mode (`{fast}`) of a conversation. Picked while
 *  HermRetro works, it is held and applied when the turn ends, so it never cuts into the work. */
export async function pickBuildModel(stored, pick) {
  const chat = BUILD_CHATS.get()[stored]

  if (!chat?.runtime) {
    return { ok: false }
  }

  patchChat(stored, current => ({ ...current, heldPick: { ...(current.heldPick ?? {}), ...pick } }))

  return chat.busy ? { ok: true, held: true } : applyBuildPick(stored)
}

export async function applyBuildPick(stored, { confirmed = false } = {}) {
  const chat = BUILD_CHATS.get()[stored]
  const pick = chat?.heldPick

  if (!chat?.runtime || !pick || chat.applyingPick) {
    return { ok: false }
  }

  patchChat(stored, current => ({ ...current, applyingPick: true }))

  try {
    if (pick.model && pick.provider) {
      const answer = await chatRequest('config.set', {
        session_id: chat.runtime,
        key: 'model',
        value: `${pick.model} --provider ${pick.provider} --session`,
        ...(confirmed ? { confirm_expensive_model: true } : {})
      })

      // Some models ask before they are used (cost): the picker shows the question and asks again.
      if (answer?.confirm_required) {
        patchChat(stored, current => ({ ...current, applyingPick: false, pickConfirm: { message: String(answer.confirm_message || 'This model costs more to run.') } }))

        return { ok: false, confirm: true }
      }

      patchChat(stored, current => withInfo(current, { model: pick.model, provider: pick.provider }))
    }

    if (pick.effort) {
      await chatRequest('config.set', { session_id: chat.runtime, key: 'reasoning', value: pick.effort })
      patchChat(stored, current => withInfo(current, { reasoning_effort: pick.effort }))
    }

    // After the model, so fast mode is checked against the model it will run on.
    if (typeof pick.fast === 'boolean') {
      await chatRequest('config.set', { session_id: chat.runtime, key: 'fast', value: pick.fast ? 'fast' : 'normal' })
      patchChat(stored, current => withInfo(current, { fast: pick.fast }))
    }

    patchChat(stored, current => {
      // A newer pick made while this one was in flight stays held for the next apply.
      const { heldPick, applyingPick: _applying, pickConfirm: _confirm, ...rest } = current
      const newer = heldPick && heldPick !== pick ? heldPick : null

      return newer ? { ...rest, heldPick: newer } : rest
    })

    const next = BUILD_CHATS.get()[stored]

    if (next?.heldPick && !next.busy) {
      void applyBuildPick(stored)
    }

    return { ok: true }
  } catch (error) {
    const { message } = describeRequestError(error)

    patchChat(stored, current => {
      const { heldPick: _held, applyingPick: _applying, pickConfirm: _confirm, ...rest } = current

      return rest
    })
    host.notify({ kind: 'error', message: `Could not switch: ${message}` })

    return { ok: false }
  }
}

export function cancelBuildPick(stored) {
  patchChat(stored, current => {
    const { heldPick: _held, pickConfirm: _confirm, applyingPick: _applying, ...rest } = current

    return rest
  })
}
