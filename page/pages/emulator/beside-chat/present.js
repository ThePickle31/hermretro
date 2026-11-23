// Opens the emulator when the agent presents a game; builds only refresh what is open.
import { host } from '#sdk'
import { emit } from '#app/events.js'
import { buildShowing, isBuildSession, toolResultObject, unwrapCalls } from '#pages/build/index.js'
import { callBackend } from '#app/backend.js'
import { RPC_PRESENTATIONS } from '#app/rpc.js'
import { BUILD_TOOLS, PRESENT_TOOL } from '#app/tools.js'
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
function presentGame(ctx, { gameId, title, note, presentedAt }, { fromBuild = false, knownBy = null } = {}) {
  const mark = `${gameId}:${presentedAt ?? ''}`

  if (presentedAt != null && presentationsSeen.has(mark)) {
    return false
  }

  presentationsSeen.add(mark)

  const shown = PRESENTED.get()
  if (knownBy !== null && shown[gameId]?.t != null && presentedAt < shown[gameId].t) {
    return false
  }
  const seq = (shown[gameId]?.seq ?? 0) + 1

  const presentation = { seq, note: typeof note === 'string' && note.trim() ? note.trim() : null, t: presentedAt ?? null }

  PRESENTED.set({ ...shown, [gameId]: presentation })
  emit('emulator.presented', { gameId, ...presentation, knownBy })
  BUILD_TICK.set(BUILD_TICK.get() + 1)

  if (fromBuild || buildShowing() === gameId) {
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
  let turnEnds = new Map()

  listen('tool.complete', event => {
    const payload = event?.payload

    if (!payload || event.replayed) {
      return
    }

    // Hermes runs deferred tools through `tool_call`: act on the call inside it.
    const inner = payload.name === 'tool_call' ? unwrapCalls(payload.tool_id ?? null, 'tool_call', payload.args)[0] : null
    const name = inner?.name ?? payload.name

    if (BUILD_TOOLS.has(name)) {
      BUILD_TICK.set(BUILD_TICK.get() + 1)
    } else if (name === PRESENT_TOOL) {
      const studio = presentedGame(payload)

      if (studio) {
        presentGame(ctx, studio, { fromBuild: studio.buildConversation === true || isBuildSession(event.session_id) })
      }
    }
  })

  listen('message.complete', event => {
    if (event?.replayed) {
      return
    }

    pending?.()
    const completedAt = performance.now()
    if (event?.session_id) {
      turnEnds.set(event.session_id, completedAt)
    }

    const run = async () => {
      const finished = turnEnds
      turnEnds = new Map()
      const requestedAt = performance.now()
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
      // Only the newest presentation per game counts, and only one made in this profile.
      const newest = new Map()

      for (const item of list) {
        if (item && typeof item.gameId === 'string' && item.thisProfile !== false) {
          newest.set(item.gameId, item)
        }
      }

      for (const item of newest.values()) {
        // Whether the chat that presented it is the game's Build conversation: that presentation's own chat (as the
        // backend records it, which outlasts a restart), not the chat whose turn just ended.
        const fromBuild = item.buildConversation === true || isBuildSession(item.sessionId) || isBuildSession(item.conversationId)
        // Date the fallback on Desktop's monotonic clock. A reply can arrive after the user switches games.
        // The presenting turn and the age measured by the backend both bound when the presentation happened.
        const age = typeof answer.now === 'number' && typeof item.t === 'number' ? Math.max(0, answer.now - item.t) : null
        const reportedBy = age === null ? requestedAt : performance.now() - age * 1000
        const ended = finished.get(item.sessionId) ?? finished.get(item.conversationId)
        // Another session can present a new game while this lookup is in flight.
        const turnBound = ended ?? (item.sessionId || item.conversationId ? reportedBy : completedAt)
        const knownBy = Math.min(turnBound, reportedBy)

        presentGame(ctx, { gameId: item.gameId, title: item.title, note: item.note, presentedAt: item.t }, { fromBuild, knownBy })
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
