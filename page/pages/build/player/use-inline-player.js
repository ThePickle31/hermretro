import { atom, useEffect, useValue } from '#sdk'
import { BUILD_PRESENTED } from '#pages/build/chat/store.js'

// Owned by the shell for one visit to Build, including backend reconnects.
export function createBuildPlayerVisit() {
  return atom({ openFor: null, seen: BUILD_PRESENTED.get() })
}

export function useInlinePlayer(visit, gameId, chat) {
  const { openFor } = useValue(visit)
  const presentations = useValue(BUILD_PRESENTED)

  useEffect(() => {
    if (!gameId || chat?.busy || chat?.opening) {
      return
    }
    if ((presentations[gameId]?.seq ?? 0) > (visit.get().seen[gameId]?.seq ?? 0)) {
      visit.set({ openFor: gameId, seen: presentations })
    }
  }, [visit, gameId, presentations, chat?.busy, chat?.opening])

  return {
    // Take a new baseline on navigation. Attaching a conversation or its project stays in the same visit.
    markPresentationsSeen: () => visit.set({ ...visit.get(), seen: BUILD_PRESENTED.get() }),
    playerOpen: Boolean(gameId && openFor === gameId),
    onPlay: () => gameId && visit.set({ ...visit.get(), openFor: gameId }),
    onClosePlayer: () => visit.set({ ...visit.get(), openFor: null })
  }
}
