import { atom, useEffect, useValue } from '#sdk'
import { callStudioOnly, describeRequestError } from '#app/backend.js'
import { RPC_PRESENTATIONS } from '#app/rpc.js'
import { BUILD_PRESENTED, buildRuntime } from '#pages/build/chat/store.js'

function selectionState(startedChat = null, createdAt = undefined) {
  // undefined until the first reply, null on a failed read. A live-only older backend has no history cutoff.
  const since = atom(Number.isFinite(createdAt) ? createdAt : undefined)
  let pending = null
  const capture = () => {
    if (since.get() == null && !pending) {
      pending = callStudioOnly(RPC_PRESENTATIONS, { cursorOnly: true }, 3000)
        .then(answer => {
          since.set(answer?.ok && Number.isFinite(answer.now) ? answer.now : null)
        })
        .catch(error => since.set(describeRequestError(error).notLoaded ? -Infinity : null))
        .finally(() => { pending = null })
    }
    return pending
  }
  return { openFor: null, seen: BUILD_PRESENTED.get(), since, capture, startedChat }
}

export async function playerSelection(startedChat, createdAt) {
  const selection = selectionState(startedChat, createdAt)
  await selection.capture()
  return selection
}

// Owned by the shell for one visit to Build, including backend reconnects.
export function createBuildPlayerVisit() {
  const state = atom(selectionState())
  let pending = null
  const accept = selection => {
    pending = null
    state.set(selection)
  }
  return {
    state, accept,
    async choose(onSelect) {
      // A second choice or an accepted New Game supersedes an outstanding switch.
      const request = onSelect ? playerSelection() : null
      pending = request
      if (request) {
        const selection = await request
        if (pending === request) {
          accept(selection)
          onSelect()
        }
      }
    }
  }
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
    const newConversation = current.startedChat && [event?.sessionId, event?.conversationId]
      .some(id => id === current.startedChat || buildRuntime.get(id) === current.startedChat)
    const afterSelection = Number.isFinite(event?.t)
      ? typeof selectedAt === 'number' && event.t > selectedAt
      : !fromHistory && selectedAt !== undefined
    if (current.since === since && unseen && (newConversation || afterSelection)) {
      visit.set({ ...current, openFor: gameId, seen: presentations })
    }
  }, [visit, gameId, presentations, event, fromHistory, since, selectedAt, chat?.busy, chat?.opening])

  return {
    playerReady: selectedAt !== undefined,
    playerOpen: Boolean(gameId && openFor === gameId),
    onPlay: () => gameId && visit.set({ ...visit.get(), openFor: gameId }),
    onClosePlayer: () => visit.set({ ...visit.get(), openFor: null, seen: BUILD_PRESENTED.get() })
  }
}
