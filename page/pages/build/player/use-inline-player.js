import { atom, useEffect, useValue } from '#sdk'
import { BUILD_PRESENTED } from '#pages/build/chat/store.js'

// Capture when the user chooses a game, even if its first Send takes time to return.
export function playerSelection() {
  return { openFor: null, selectedAt: performance.now(), seen: BUILD_PRESENTED.get() }
}

// Owned by the shell for one visit to Build, including backend reconnects.
export function createBuildPlayerVisit() {
  return atom(playerSelection())
}

export function useInlinePlayer(visit, gameId, chat) {
  const { openFor } = useValue(visit)
  const presentations = useValue(BUILD_PRESENTED)

  useEffect(() => {
    if (!gameId || chat?.busy || chat?.opening) {
      return
    }
    const current = visit.get()
    const event = presentations[gameId]
    if (event && event.seq > (current.seen[gameId]?.seq ?? 0) && (event.knownBy == null || event.knownBy > current.selectedAt)) {
      visit.set({ ...current, openFor: gameId, seen: presentations })
    }
  }, [visit, gameId, presentations, chat?.busy, chat?.opening])

  return {
    playerOpen: Boolean(gameId && openFor === gameId),
    onPlay: () => gameId && visit.set({ ...visit.get(), openFor: gameId }),
    onClosePlayer: () => visit.set({ ...visit.get(), openFor: null })
  }
}
