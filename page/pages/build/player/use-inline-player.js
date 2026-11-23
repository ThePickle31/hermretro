import { atom, useEffect, useValue } from '#sdk'
import { callStudioOnly } from '#app/backend.js'
import { RPC_PRESENTATIONS } from '#app/rpc.js'
import { BUILD_PRESENTED } from '#pages/build/chat/store.js'

function selectionState() {
  // The registry dates presentations on the backend. Sample that same clock once for this selection.
  const since = atom(null)
  let pending = null
  const capture = () => {
    if (since.get() === null && !pending) {
      pending = callStudioOnly(RPC_PRESENTATIONS, { cursorOnly: true }, 3000)
        .then(answer => {
          if (answer?.ok && Number.isFinite(answer.now)) since.set(answer.now)
        })
        .catch(() => {}) // Live events still work. A later lookup or reconnect can retry.
        .finally(() => { pending = null })
    }
    return pending
  }
  return { openFor: null, seen: BUILD_PRESENTED.get(), since, capture }
}

export function playerSelection() {
  const selection = selectionState()
  void selection.capture()
  return selection
}

// Owned by the shell for one visit to Build, including backend reconnects.
export function createBuildPlayerVisit() {
  return atom(selectionState())
}

export function useInlinePlayer(visit, gameId, chat) {
  const { openFor, since, capture } = useValue(visit)
  const selectedAt = useValue(since)
  const presentations = useValue(BUILD_PRESENTED)
  const event = presentations[gameId]
  const fromHistory = event?.fromHistory ? event : null

  useEffect(() => { void capture() }, [capture, fromHistory])

  useEffect(() => {
    if (!gameId || chat?.busy || chat?.opening) {
      return
    }
    const current = visit.get()
    const unseen = event && event.seq > (current.seen[gameId]?.seq ?? 0)
    const afterSelection = !fromHistory || (selectedAt !== null && fromHistory.t > selectedAt)
    if (current.since === since && unseen && afterSelection) {
      visit.set({ ...current, openFor: gameId, seen: presentations })
    }
  }, [visit, gameId, presentations, event, fromHistory, since, selectedAt, chat?.busy, chat?.opening])

  return {
    playerOpen: Boolean(gameId && openFor === gameId),
    onPlay: () => gameId && visit.set({ ...visit.get(), openFor: gameId }),
    onClosePlayer: () => visit.set({ ...visit.get(), openFor: null, seen: BUILD_PRESENTED.get() })
  }
}
