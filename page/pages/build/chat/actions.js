// What the user can do with a Build conversation: open, send, stop, resume, answer.
import { host } from '#sdk'
import { describeRequestError } from '#app/backend.js'
import { studioTarget } from '#app/routing.js'
import { isUpdating, UPDATING_MESSAGE } from '#app/update/lock.js'
import { attachmentLine } from './attachments.js'
import { FAST_PROVIDERS, settleBuildPick } from './model-pick.js'
import { historyItems } from './history.js'
import { endTurn, lostTurns, sealText } from './reducer.js'
import { APPROVAL_LABELS, schedulePromptCheck } from './requests.js'
import { withInfo } from './steps.js'
import { BUILD_CHATS, buildRuntime, chatRequest, newId, patchChat, retainChatRoute } from './store.js'

/** Attach to a game's conversation (stored id) and load what it says so far. */
export async function openBuildChat(stored) {
  const known = BUILD_CHATS.get()[stored]

  if (known?.runtime || known?.opening) {
    return
  }

  patchChat(stored, chat => ({ ...chat, opening: true, failure: null }))
  await retainChatRoute()

  try {
    const result = await chatRequest('session.resume', { session_id: stored }, 60_000)
    const runtime = result?.session_id

    if (runtime) {
      buildRuntime.set(runtime, stored)
    }

    const running = typeof result?.running === 'boolean' ? result.running : Boolean(BUILD_CHATS.get()[stored]?.busy)
    const pending = result?.pending ?? result?.info?.pending_submissions
    const at = Date.now()

    patchChat(stored, chat => ({
      ...withInfo(chat, result?.info),
      runtime,
      opening: false,
      items: historyItems(result?.messages, running),
      // Messages Hermes holds for later (behind a running or lost turn) wait under the conversation.
      queued: (Array.isArray(pending) ? pending : [])
        .filter(row => row?.status === 'queued' && typeof row.text === 'string' && row.text)
        .map(row => ({ kind: 'user', text: row.text, at })),
      lost: lostTurns(pending),
      lostFailure: null,
      missing: false,
      busy: running,
      activity: running ? (chat.activity ?? 'thinking') : null,
      turnStartedAt: running ? (chat.turnStartedAt ?? Date.now()) : null,
      lastEventAt: Date.now(),
      unreachable: 0
    }))
  } catch (error) {
    const { message } = describeRequestError(error)

    // Only a definite "no such session" means it was removed; anything else can be retried.
    const missing = error?.code === 4007 || /^session not found$/i.test(message.trim())

    patchChat(stored, chat => ({ ...chat, opening: false, failure: message, missing }))
  }
}

/** Attach again after a gateway restart or a replay gap: a fresh runtime and the stored transcript. */
export async function reopenBuildChat(stored) {
  const known = BUILD_CHATS.get()[stored]

  if (known?.opening) {
    return
  }

  for (const [runtime, owner] of buildRuntime) {
    if (owner === stored) {
      buildRuntime.delete(runtime)
    }
  }

  patchChat(stored, chat => ({ ...chat, runtime: null, seq: null, epoch: null, segments: {}, failure: null }))
  await openBuildChat(stored)

  const chat = BUILD_CHATS.get()[stored]

  // Still working after the reload: keep watching for questions and approvals.
  if (chat?.runtime && chat.busy) {
    schedulePromptCheck(stored)
  }
}

/** A new hidden session in the studio profile, on the model, effort and fast mode picked for it (else the
 *  profile's default). Fast mode is sent only for a ChatGPT or Codex Subscription or OpenAI API model. Returns its stored id. */
export async function createBuildChat(title, pick = null) {
  await retainChatRoute()

  const choice = {
    ...(pick?.model && pick?.provider ? { model: pick.model, provider: pick.provider } : {}),
    ...(pick?.effort ? { reasoning_effort: pick.effort } : {}),
    ...(typeof pick?.fast === 'boolean' && FAST_PROVIDERS.has(pick?.provider) ? { fast: pick.fast } : {})
  }
  // On the canonical gateway a title finds an existing session before creating one. This title is a Build label only.
  const result = await chatRequest('session.create', { hidden: true, source: 'gui', ...choice }, 60_000)
  const stored = result?.stored_session_id ?? result?.session_id
  const runtime = result?.session_id
  const info = result?.info

  if (!stored || !runtime) {
    throw new Error('Hermes did not return a session.')
  }
  if (result.message_count > 0 || result.messages?.length) {
    throw new Error('Hermes returned an existing conversation. Your message was not sent.')
  }
  if (choice.model && (info?.model !== choice.model || info?.provider !== choice.provider)) {
    throw new Error(`Hermes did not confirm ${choice.model} (${choice.provider}) for the new conversation. Your message was not sent.`)
  }

  buildRuntime.set(runtime, stored)
  patchChat(stored, chat => ({ ...withInfo(chat, info), runtime, title, items: [] }))

  return stored
}

/** Send a message. Returns true once the transcript owns the message, even if it must offer a retry.
 *  `attachments` (./attachments.js) are named at the top of the message and shown as chips. With `mustLand` (a New
 *  Game's first message), true only once Hermes accepted it: a message it did not take is not the transcript's to
 *  keep, so the caller keeps its own copy. */
export async function sendBuildChat(stored, text, shown = text, attachments = [], { mustLand = false } = {}) {
  // An update is swapping and reloading the plugin: no new turn starts until it is done.
  if (isUpdating()) {
    host.notify({ kind: 'warning', message: UPDATING_MESSAGE })

    return false
  }

  if (!BUILD_CHATS.get()[stored]?.runtime) {
    await openBuildChat(stored)

    // An update may have started while the conversation opened.
    if (isUpdating()) {
      host.notify({ kind: 'warning', message: UPDATING_MESSAGE })

      return false
    }
  }

  const before = BUILD_CHATS.get()[stored]
  // A model, effort or speed just picked is applied before the message goes, so the message runs on it.
  const settled = before?.runtime && !before.busy && before.heldPick ? await settleBuildPick(stored) : { ok: true }
  const chat = BUILD_CHATS.get()[stored]

  const now = Date.now()
  const live = Boolean(chat?.runtime)
  // Whether a turn was already running when this was sent: only then can the message really wait.
  // A lost turn pauses the conversation: Hermes keeps the message, and it runs once that is dropped.
  const paused = Boolean(chat?.lost?.length)
  const behindTurn = Boolean(chat?.busy) || paused

  patchChat(stored, current => ({
    ...current,
    busy: live && !paused,
    activity: live && !paused ? 'thinking' : current.activity,
    turnStartedAt: live && !paused ? (current.busy && current.turnStartedAt ? current.turnStartedAt : now) : current.turnStartedAt,
    lastEventAt: now,
    items: [
      ...sealText(current).items,
      { kind: 'user', text: shown, at: now, ...(current.info?.model ? { model: current.info.model, effort: current.info.effort ?? '' } : {}), ...(attachments.length ? { attachments } : {}) }
    ]
  }))

  if (!chat?.runtime) {
    patchChat(stored, current => ({ ...current, items: [...current.items, { kind: 'error', text: 'This conversation could not be opened, so the message was not sent.' }] }))

    return !mustLand
  }

  // The change it waited for failed ("Could not switch" says why): the message is kept to send again, not sent on
  // settings the user just moved away from.
  if (!settled.ok) {
    patchChat(stored, current => endTurn({ ...current, items: [...current.items, { kind: 'error', text: 'The model change did not go through, so the message was not sent.', resend: { text, shown, attachments } }] }, 'error'))

    return !mustLand
  }

  schedulePromptCheck(stored)

  try {
    // `submission_id` makes a retried submit the same admission (the canonical gateway requires one).
    const named = attachments.length ? `${attachments.map(attachmentLine).join('\n')}\n${text}` : text

    const reply = await chatRequest('prompt.submit', { session_id: chat.runtime, submission_id: newId(), text: named })

    // Sent while the agent worked, and Hermes queued it for after this turn (an attachment, or the
    // user's busy-input setting): it waits under the conversation until its turn starts. Hermes also
    // answers "queued" when it puts a message through the gateway's queue with nothing ahead of it (a
    // New Game's first message): that one starts at once, so it stays in the conversation.
    if (reply?.status === 'queued' && behindTurn) {
      patchChat(stored, current => {
        const index = current.items.findLastIndex(item => item.kind === 'user' && item.at === now)

        if (index === -1) {
          return current
        }

        const item = current.items[index]

        return { ...current, items: [...current.items.slice(0, index), ...current.items.slice(index + 1)], queued: [...(current.queued ?? []), item] }
      })
    }
  } catch (error) {
    const { message } = describeRequestError(error)

    patchChat(stored, current => endTurn({ ...current, items: [...current.items, { kind: 'error', text: message, resend: { text, shown, attachments } }] }, 'error'))

    // The runtime went away (gateway restart): attach again so the next message works.
    if (/not.?found|4007|unknown session/i.test(message)) {
      void reopenBuildChat(stored)
    }

    return !mustLand
  }

  return true
}

export async function stopBuildChat(stored) {
  const chat = BUILD_CHATS.get()[stored]

  if (chat?.runtime) {
    await chatRequest('session.interrupt', { session_id: chat.runtime }).catch(() => {})
  }
}

/** Get a conversation paused on a lost turn going again: drop the lost turn (Hermes does not run it
 *  again; what it saved stays), then the messages that waited behind it run. With none waiting, ask
 *  HermRetro to pick up where it stopped. */
export async function resumeBuildChat(stored) {
  const chat = BUILD_CHATS.get()[stored]

  if (!chat?.runtime || chat.resuming) {
    return
  }

  // Dropping the lost turn releases the messages waiting behind it: not while an update reloads the plugin.
  if (isUpdating()) {
    host.notify({ kind: 'warning', message: UPDATING_MESSAGE })

    return
  }

  patchChat(stored, current => ({ ...current, resuming: true, lostFailure: null }))

  try {
    // Read the lost turns fresh: this also gives the app the generation each acknowledgement needs.
    const snapshot = await chatRequest('session.resume', { session_id: stored, omit_messages: true }, 60_000)
    const runtime = snapshot?.session_id ?? chat.runtime
    const pending = snapshot?.pending ?? snapshot?.info?.pending_submissions ?? []

    for (const turn of lostTurns(pending)) {
      // An update may have started while this waited: stay paused, nothing released.
      if (isUpdating()) {
        patchChat(stored, current => ({ ...current, resuming: false }))
        host.notify({ kind: 'warning', message: UPDATING_MESSAGE })

        return
      }

      await chatRequest('prompt.resolve_unknown', { session_id: runtime, admission_id: turn.id })
    }

    const waiting = Array.isArray(pending) && pending.some(row => row?.status === 'queued')

    patchChat(stored, current => ({ ...current, lost: [], resuming: false }))

    if (!waiting) {
      await sendBuildChat(stored, 'Your last turn was cut off when Hermes restarted. Continue where you left off.', 'Continue')
    }
  } catch (error) {
    patchChat(stored, current => ({ ...current, resuming: false, lostFailure: describeRequestError(error).message }))
  }
}

/** Answer a question or approval card. `answer` is the approval choice, or qid → text for a question. */
export async function answerBuildPrompt(stored, item, answer) {
  const chat = BUILD_CHATS.get()[stored]

  if (!chat?.runtime) {
    return
  }

  const payload = item.payload ?? {}
  let call

  if (item.requestId && item.kind === 'clarify') {
    // A viewer attached to the session locks each answer; the last lock resolves the question.
    // `request.answer` is the older proxy path (a gateway without clarify.lock).
    call = (async () => {
      try {
        for (const [qid, value] of Object.entries(answer ?? {})) {
          await chatRequest('clarify.lock', { request_id: item.requestId, question_id: qid, answer: value ?? '' })
        }
      } catch (error) {
        if (!describeRequestError(error).notLoaded) {
          throw error
        }

        const reply = await chatRequest('request.answer', { id: item.requestId, result: { answers: answer, outcome: 'submitted' } })

        if (reply?.status === 'expired') {
          throw new Error('That question has already closed.')
        }
      }
    })()
  } else if (item.kind === 'approval') {
    call = chatRequest('approval.respond', { session_id: chat.runtime, choice: answer, ...(payload.request_id ? { request_id: payload.request_id } : {}) })
  } else {
    const id = payload.prompt_id ?? payload.request_id
    const text = typeof answer === 'string' ? answer : Object.values(answer ?? {}).filter(Boolean).join('; ')

    call = chatRequest('clarify.respond', { session_id: chat.runtime, answer: text, ...(id ? { request_id: id } : {}) })
  }

  try {
    await call

    const label = typeof answer === 'string' ? answer : Object.values(answer ?? {}).map(value => value ?? 'skipped').join('; ')

    const picked = typeof answer === 'string' ? [APPROVAL_LABELS[answer] ?? answer] : Object.values(answer ?? {}).map(value => String(value ?? 'skipped'))

    patchChat(stored, current => ({
      ...current,
      waiting: false,
      items: current.items.map(entry =>
        entry === item || (item.requestId && entry.requestId === item.requestId) ? { ...entry, answered: label, answers: picked } : entry
      )
    }))
  } catch (error) {
    host.notify({ kind: 'error', message: `Could not answer Hermes: ${describeRequestError(error).message}` })
  }
}

export function openInFullChat(stored) {
  const target = studioTarget()

  if (target && typeof host.openSession === 'function') {
    void host.openSession(stored, target.profile ? { profile: target.profile } : {}).catch(error =>
      host.notify({ kind: 'error', message: `Could not open the chat: ${describeRequestError(error).message}` })
    )
  }
}
