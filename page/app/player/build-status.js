import { RPC_GAME_BUILD_STATUS } from '#app/rpc.js'

export async function readGameBuildStatus(call, id) {
  const data = await call(RPC_GAME_BUILD_STATUS, { id })

  if (data?.ok === true || data?.code === 'NO_GAME') {
    return data
  }

  // Keep the query's last good data during a temporary read failure.
  throw new Error(data?.error || 'Could not read the game build.')
}
