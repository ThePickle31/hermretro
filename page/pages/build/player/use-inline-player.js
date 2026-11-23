import { useEffect, useRef, useState, useValue } from '#sdk'
import { BUILD_PRESENTED } from '#pages/build/chat/store.js'

// An agent presentation opens the game once the conversation is ready. The open choice survives later turns.
export function useInlinePlayer(gameId, stored, chat) {
  const [playerFor, setPlayerFor] = useState(null)
  const presentations = useValue(BUILD_PRESENTED)
  // A New Game conversation keeps its stored ID when its project first appears on the shelf.
  const view = stored ? `chat:${stored}` : `game:${gameId}`
  const seen = useRef({ view, presentations })

  useEffect(() => {
    if (seen.current.view !== view) {
      seen.current = { view, presentations }
      return
    }
    if (!gameId || chat?.busy || chat?.opening) {
      return
    }
    if ((presentations[gameId]?.seq ?? 0) > (seen.current.presentations[gameId]?.seq ?? 0)) {
      seen.current = { view, presentations }
      setPlayerFor(gameId)
    }
  }, [view, gameId, presentations, chat?.busy, chat?.opening])

  return {
    playerOpen: Boolean(gameId && playerFor === gameId),
    onPlay: () => gameId && setPlayerFor(gameId),
    onClosePlayer: () => setPlayerFor(null)
  }
}
