// The game ↔ conversation binding (backend: `build` RPC, `games[].session`, `pending`).
import { callStudioOnly, describeRequestError } from '#app/backend.js'
import { RPC_BUILD } from '#app/rpc.js'
import { BUILD_START, PLAN_START } from './workflow.js'

/** Ask the backend to record a binding. An older backend without the RPC answers -32601: the page then
 *  keeps the binding for this visit only and names the project in the first message instead. */
export async function buildRpc(params) {
  try {
    const answer = await callStudioOnly(RPC_BUILD, params)

    if (answer && answer.ok === false) {
      throw Object.assign(new Error(answer.error || 'The backend refused.'), { code: answer.code })
    }

    return answer
  } catch (error) {
    if (describeRequestError(error).notLoaded) {
      return null
    }

    throw error
  }
}

export function newGamePrompt({ name, idea, plan }) {
  const what = idea.trim() || 'a small game'
  const title = name.trim()

  const introduction = plan ? 'help me plan' : 'make'

  return `Use hermretro to ${introduction} a new Game Boy Color game${title ? ` called "${title}"` : ''}: ${what}. ${plan ? PLAN_START : BUILD_START}`
}
