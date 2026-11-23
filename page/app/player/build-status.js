import { callStudio, readGamesShelf } from '#app/backend.js'
import { RPC_GAME_BUILD_STATUS } from '#app/rpc.js'

export const buildStatusUnsupported = error => error?.code === -32601

export async function readGameBuildStatus(call, id) {
  const data = await call(RPC_GAME_BUILD_STATUS, { id })

  if (data?.ok === true || data?.code === 'NO_GAME') {
    return data
  }

  // Keep the query's last good data during a temporary read failure.
  throw new Error(data?.error || 'Could not read the game build.')
}

export async function readSideBuildStatus(id) {
  try {
    return await readGameBuildStatus(callStudio, id)
  } catch (error) {
    if (!buildStatusUnsupported(error)) {
      throw error
    }
  }

  const shelf = await readGamesShelf()

  if (Array.isArray(shelf.unavailable) && shelf.unavailable.includes(id)) {
    throw new Error('Could not read the game build.')
  }

  const game = shelf.games.find(item => item?.id === id) ?? null

  return { ok: true, game, device: shelf.device }
}
