// Questions and approvals a running turn is waiting on.
import { applyBuildPick } from './model-pick.js'
import { endTurn } from './reducer.js'
import { BUILD_CHATS, chatRequest, patchChat } from './store.js'

// Questions and approvals reach the app as server requests, not events, so the page cannot hear
// them. While a turn runs (a plugin's approval gate asks before `tool.start`), the page reads the
// session's open requests and shows them as cards; answers go back through `clarify.lock` /
// `request.answer` / `approval.respond`.
const promptChecks = new Map()

function toolRunning(chat) {
  return Boolean(chat?.busy && chat.items.some(item => item.kind === 'tools' && item.tools.some(tool => tool.state === 'running')))
}

function mergeOpenRequests(chat, open) {
  const ids = new Set(open.map(request => request.id))
  const known = new Set(chat.items.filter(item => item.requestId).map(item => item.requestId))
  // A card whose request is gone was answered somewhere else (the full chat) or timed out.
  const items = chat.items.map(item =>
    item.requestId && !item.answered && !ids.has(item.requestId) ? { ...item, answered: 'answered elsewhere' } : item
  )
  const added = open
    .filter(request => !known.has(request.id))
    .map(request => ({ kind: request.method === 'approval' ? 'approval' : 'clarify', requestId: request.id, payload: request.params ?? {} }))

  return added.length || items.some((item, index) => item !== chat.items[index])
    ? { ...chat, items: [...items, ...added], waiting: added.length > 0 || items.some(item => item.requestId && !item.answered) }
    : chat
}

async function checkOpenRequests(stored) {
  promptChecks.delete(stored)

  const chat = BUILD_CHATS.get()[stored]

  if (!chat?.runtime || !chat.busy) {
    return
  }

  try {
    const snapshot = await chatRequest('session.resume', { session_id: stored, omit_messages: true })
    const open = (Array.isArray(snapshot?.open_requests) ? snapshot.open_requests : []).filter(
      request => request && typeof request.id === 'string' && (request.method === 'clarify' || request.method === 'approval')
    )

    patchChat(stored, current => {
      const merged = mergeOpenRequests(current, open)

      // The gateway says the turn is over (its end was missed, e.g. across a reconnect): stop waiting.
      return snapshot?.running === false && !open.length && merged.busy ? endTurn(merged, 'complete') : merged
    })
    patchChat(stored, current => (current.unreachable ? { ...current, unreachable: 0 } : current))

    if (!BUILD_CHATS.get()[stored]?.busy && BUILD_CHATS.get()[stored]?.heldPick) {
      void applyBuildPick(stored)
    }
  } catch {
    // Asked again on the next tick; after a few misses the status line says it is reconnecting.
    patchChat(stored, current => ({ ...current, unreachable: (current.unreachable ?? 0) + 1 }))
  }

  if (BUILD_CHATS.get()[stored]?.busy) {
    schedulePromptCheck(stored, toolRunning(BUILD_CHATS.get()[stored]) ? 2_500 : 4_000)
  }
}

export function schedulePromptCheck(stored, delay = 1_200) {
  if (!promptChecks.has(stored)) {
    promptChecks.set(stored, setTimeout(() => void checkOpenRequests(stored), delay))
  }
}

export const APPROVAL_LABELS = { once: 'Allow once', session: 'Allow for this chat', always: 'Always allow', deny: 'Deny' }
