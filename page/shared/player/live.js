// Which surface holds the one live player.
import { atom } from '#sdk'

// The surface running the one live player: 'page', 'side:<game id>' or null.
export const LIVE_PLAYER = atom(null)

export const claimLive = surface => {
  if (LIVE_PLAYER.get() !== surface) {
    LIVE_PLAYER.set(surface)
  }
}

export const releaseLive = surface => {
  if (LIVE_PLAYER.get() === surface) {
    LIVE_PLAYER.set(null)
  }
}
