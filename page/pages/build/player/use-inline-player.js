import { useEffect, useRef, useState, useValue } from '#sdk'
import { BUILD_PRESENTED } from '#pages/build/chat/store.js'

// An agent presentation opens the game once the conversation is ready. The open choice survives later turns.
export function useInlinePlayer(gameId, stored, chat) {
  const [playerFor, setPlayerFor] = useState(null)
  const presentations = useValue(BUILD_PRESENTED)
  const previous = useRef({ gameId, stored })
  const seen = useRef(presentations)

  useEffect(() => {
    // A first edit keeps its game ID. A pending New Game keeps its conversation ID through binding.
    const last = previous.current
    const sameView = gameId && last.gameId ? gameId === last.gameId : stored && stored === last.stored
    previous.current = { gameId, stored }
    if (!sameView) {
      seen.current = presentations
    }
    if (!gameId || chat?.busy || chat?.opening) {
      return
    }
    if ((presentations[gameId]?.seq ?? 0) > (seen.current[gameId]?.seq ?? 0)) {
      seen.current = presentations
      setPlayerFor(gameId)
    }
  }, [gameId, stored, presentations, chat?.busy, chat?.opening])

  return {
    playerOpen: Boolean(gameId && playerFor === gameId),
    onPlay: () => gameId && setPlayerFor(gameId),
    onClosePlayer: () => setPlayerFor(null)
  }
}
