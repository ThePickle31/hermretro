import { useEffect, useRef, useState, useValue } from '#sdk'
import { BUILD_PRESENTED } from '#pages/build/chat/store.js'

// An agent presentation opens the game once the conversation is ready. The open choice survives later turns.
export function useInlinePlayer(gameId, chat) {
  const [playerFor, setPlayerFor] = useState(null)
  const presentationSeq = useValue(BUILD_PRESENTED)[gameId ?? '']?.seq
  const seenPresentation = useRef(presentationSeq ?? 0)
  const openWhenDone = useRef(false)

  useEffect(() => {
    const seq = presentationSeq ?? 0

    if (seq !== seenPresentation.current) {
      seenPresentation.current = seq
      openWhenDone.current = true
    }
  }, [presentationSeq])

  useEffect(() => {
    if (gameId && openWhenDone.current && !chat?.busy && !chat?.opening) {
      openWhenDone.current = false
      setPlayerFor(gameId)
    }
  }, [chat?.busy, chat?.opening, presentationSeq, gameId])

  // A deferred open is scoped to the current game view.
  useEffect(() => {
    openWhenDone.current = false
  }, [gameId])

  return {
    playerOpen: Boolean(gameId && playerFor === gameId),
    onPlay: () => gameId && setPlayerFor(gameId),
    onClosePlayer: () => setPlayerFor(null)
  }
}
