import { useEffect, useRef, useState, useValue } from '#sdk'
import { BUILD_PRESENTED } from '#pages/build/chat/store.js'

// An agent presentation opens the game once the conversation is ready. The open choice survives later turns.
export function useInlinePlayer(gameId, chat) {
  const [playerFor, setPlayerFor] = useState(null)
  const presentations = useValue(BUILD_PRESENTED)
  const seen = useRef(presentations)

  useEffect(() => {
    if (!gameId || chat?.busy || chat?.opening) {
      return
    }
    if ((presentations[gameId]?.seq ?? 0) > (seen.current[gameId]?.seq ?? 0)) {
      seen.current = presentations
      setPlayerFor(gameId)
    }
  }, [gameId, presentations, chat?.busy, chat?.opening])

  return {
    // Take a new baseline on navigation. Attaching a conversation or its project stays in the same visit.
    markPresentationsSeen: () => { seen.current = BUILD_PRESENTED.get() },
    playerOpen: Boolean(gameId && playerFor === gameId),
    onPlay: () => gameId && setPlayerFor(gameId),
    onClosePlayer: () => setPlayerFor(null)
  }
}
