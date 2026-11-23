import { useEffect, useQueryClient, useRef, useState } from '#sdk'
import { shrinkFrame } from '#shared/player/frame-image.js'
import { callStudio, describeRequestError } from '#app/backend.js'
import { ID } from '#app/ids.js'
import { RPC_GAME_THUMB } from '#app/rpc.js'

/** Capture from this game's loaded frame once the shelf confirms it still needs a title screen. */
export function useTitleScreen(ctx, frameRef, gameId, snap) {
  const [loadedFrame, setLoadedFrame] = useState(null)
  const tried = useRef(new Set())
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!gameId || !loadedFrame || loadedFrame !== frameRef.current || tried.current.has(gameId)) {
      return undefined
    }

    let active = true
    let cancelTimer
    const current = () => active && loadedFrame === frameRef.current
    const capture = async remaining => {
      if (!current()) {
        return
      }

      const png = await shrinkFrame(await snap())

      if (!current()) {
        return
      }

      if (!png && remaining > 0) {
        cancelTimer = ctx.setTimeout(() => void capture(remaining - 1), 5_000)

        return
      }

      tried.current.add(gameId)
      if (png) {
        try {
          await callStudio(RPC_GAME_THUMB, { id: gameId, png })
          void queryClient.invalidateQueries({ queryKey: [ID, 'games'] })
        } catch (error) {
          console.warn('[hermretro] title screen not saved:', describeRequestError(error).message)
        }
      }
    }

    cancelTimer = ctx.setTimeout(() => void capture(3), 3_000)

    return () => {
      active = false
      cancelTimer()
    }
  }, [ctx, frameRef, gameId, loadedFrame, queryClient, snap])

  return () => setLoadedFrame(frameRef.current)
}
