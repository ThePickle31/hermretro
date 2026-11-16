// Opens the emulator when the agent presents a game; builds only refresh what is open.
import { host } from '../sdk.js'
import { BUILD_VIEWING, buildRuntime } from '../build-chat/store.js'
import { toolResultObject, unwrapCalls } from '../build-chat/tool-results.js'
import { callBackend } from '../core/backend.js'
import { RPC_PRESENTATIONS } from '../core/rpc.js'
import { BUILD_TOOLS, PRESENT_TOOL } from '../core/tools.js'
import { BUILD_TICK, presentationsSeen, PRESENTED, sideTabs } from './state.js'
import { openSideEmulator } from './tab.js'

/** The `studio` part of a successful `chromatic_present_game` result, from a `tool.complete` payload. */
function presentedGame(payload) {
  const name = payload?.name === 'tool_call' ? unwrapCalls(null, 'tool_call', payload.args)[0]?.name : payload?.name

  if (!payload || name !== PRESENT_TOOL || payload.error) {
    return null
  }

  const result = toolResultObject(payload.result)
  const studio = result?.studio

  if (!result || result.ok !== true || result.error || !studio || typeof studio.gameId !== 'string' || !studio.gameId) {
    return null
  }

  return studio
}

/** The agent presented a game: note it for the tab (which then loads the newest build) and open or
 *  front the tab beside the chat. Each presentation is acted on once. A game's Build conversation
 *  (or the game the Build page is showing) plays in the Build page's own pane instead. */
function presentGame(ctx, { gameId, title, note, presentedAt }, { fromBuild = false } = {}) {
  const mark = `${gameId}:${presentedAt ?? ''}`

  if (presentedAt != null && presentationsSeen.has(mark)) {
    return false
  }

  presentationsSeen.add(mark)

  const shown = PRESENTED.get()
  const seq = (shown[gameId]?.seq ?? 0) + 1

  PRESENTED.set({ ...shown, [gameId]: { seq, note: typeof note === 'string' && note.trim() ? note.trim() : null, t: presentedAt ?? null } })
  BUILD_TICK.set(BUILD_TICK.get() + 1)

  if (fromBuild || BUILD_VIEWING.get() === gameId) {
    return false
  }

  return openSideEmulator(ctx, { id: gameId, title: typeof title === 'string' && title ? title : 'Game' })
}

/** Listen in every chat (registered with the plugin, so it works before the Studio page was ever
 *  opened). Only a successful `chromatic_present_game` opens the emulator; builds just refresh what
 *  open players know. A gateway with tool progress off sends no `tool.complete`, so each turn end
 *  also asks the backend for presentations since the last one seen. */
export function watchBuilds(ctx) {
  const listen = typeof ctx.onEvent === 'function' ? ctx.onEvent : typeof host.onEvent === 'function' ? host.onEvent : null

  if (!listen) {
    return
  }

  // Backend clock (seconds) of the last `presentations` answer; until then, this plugin's start.
  let since = Date.now() / 1000 - 5
  let pending = null

  listen('tool.complete', event => {
    const payload = event?.payload

    if (!payload || event.replayed) {
      return
    }

    // Hermes runs deferred tools through `tool_call`: act on the call inside it.
    const inner = payload.name === 'tool_call' ? unwrapCalls(payload.tool_id ?? null, 'tool_call', payload.args)[0] : null
    const name = inner?.name ?? payload.name

    if (BUILD_TOOLS.has(name)) {
      BUILD_TICK.set(BUILD_TICK.get() + 1) // an open tab re-reads the library and shows the rebuilt banner
    } else if (name === PRESENT_TOOL) {
      const studio = presentedGame(payload)

      if (studio) {
        presentGame(ctx, studio, { fromBuild: buildRuntime.has(event.session_id) })
      }
    }
  })

  listen('message.complete', event => {
    if (event?.replayed) {
      return
    }

    pending?.()

    const fromBuild = buildRuntime.has(event?.session_id)

    const run = async () => {
      BUILD_TICK.set(BUILD_TICK.get() + 1)

      let answer

      try {
        answer = (await callBackend(RPC_PRESENTATIONS, { since })).data
      } catch {
        return // an older backend without the RPC, or none running
      }

      if (!answer?.ok) {
        return
      }

      if (typeof answer.now === 'number') {
        since = answer.now - 1 // the backend's clock; a repeat inside that second is skipped below
      }

      const list = Array.isArray(answer.presentations) ? answer.presentations : []
      // Only the newest presentation per game counts.
      const newest = new Map()

      for (const item of list) {
        if (item && typeof item.gameId === 'string') {
          newest.set(item.gameId, item)
        }
      }

      for (const item of newest.values()) {
        presentGame(ctx, { gameId: item.gameId, title: item.title, note: item.note, presentedAt: item.t }, { fromBuild })
      }
    }

    const cancel = ctx.setTimeout?.(() => void run(), 600)

    pending = typeof cancel === 'function' ? cancel : null
  })

  ctx.onDispose?.(() => {
    for (const close of [...sideTabs.values()]) {
      try {
        close()
      } catch {
        // already gone
      }
    }
  })
}
