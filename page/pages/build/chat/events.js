// The gateway event stream: batching, and the listeners registered with the plugin.
import { host } from '#sdk'
import { reopenBuildChat } from './actions.js'
import { applyBuildPick } from './model-pick.js'
import { reduceChat } from './reducer.js'
import { schedulePromptCheck } from './requests.js'
import { BUILD_CHATS, BUILD_EVENTS, buildRuntime, patchChat } from './store.js'

// Events are applied in batches, once per animation frame: a fast token stream then costs one render
// per frame, not one per token. Anything that is not text is applied at once with what is queued.
const queuedEvents = new Map()
let queuedFlush = null
const STREAM_EVENTS = new Set(['message.delta', 'reasoning.delta', 'thinking.delta', 'tool.progress'])

function flushChatEvents() {
  queuedFlush = null

  const batches = [...queuedEvents]

  queuedEvents.clear()

  for (const [stored, events] of batches) {
    patchChat(stored, chat => events.reduce(reduceChat, chat))

    const chat = BUILD_CHATS.get()[stored]

    if (chat && !chat.busy && chat.heldPick) {
      void applyBuildPick(stored)
    }

    if (events.some(event => event.type === 'message.start' || event.type === 'tool.start' || event.type === 'tool.generating')) {
      schedulePromptCheck(stored)
    }
  }
}

function queueChatEvent(stored, event) {
  const list = queuedEvents.get(stored)

  if (list) {
    list.push(event)
  } else {
    queuedEvents.set(stored, [event])
  }

  if (!STREAM_EVENTS.has(event.type)) {
    if (queuedFlush) {
      queuedFlush.cancel()
    }

    flushChatEvents()

    return
  }

  if (!queuedFlush) {
    const visible = typeof document === 'undefined' || document.visibilityState !== 'hidden'

    if (visible && typeof requestAnimationFrame === 'function') {
      const id = requestAnimationFrame(flushChatEvents)

      queuedFlush = { cancel: () => cancelAnimationFrame(id) }
    } else {
      const id = setTimeout(flushChatEvents, 50)

      queuedFlush = { cancel: () => clearTimeout(id) }
    }
  }
}

// The listeners of the last `register`: registering again replaces them, so no event is applied twice.
let buildChatListeners = []

/** Listen once (from `register`), so a conversation keeps streaming while the page is closed. */
export function watchBuildChats(ctx) {
  const listen = typeof ctx.onEvent === 'function' ? ctx.onEvent : typeof host.onEvent === 'function' ? host.onEvent : null

  for (const stop of buildChatListeners) {
    try {
      stop?.()
    } catch {
      // already gone
    }
  }

  buildChatListeners = []

  if (!listen) {
    return
  }

  for (const type of BUILD_EVENTS) {
    buildChatListeners.push(listen(type, event => {
      const stored = buildRuntime.get(event?.session_id)

      if (!stored) {
        return
      }

      // The gateway's replay no longer covers this session (it restarted or the socket fell behind):
      // attach again and reload the transcript.
      if (event.type === 'session.replay_gap') {
        void reopenBuildChat(stored)

        return
      }

      queueChatEvent(stored, event)
    }))
  }
}
