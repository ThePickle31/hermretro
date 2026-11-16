// The game ↔ conversation binding (backend: `build` RPC, `games[].session`, `pending`).
import { callStudio, describeRequestError } from '../core/backend.js'
import { RPC_BUILD } from '../core/rpc.js'

/** Ask the backend to record a binding. An older backend without the RPC answers -32601: the page then
 *  keeps the binding for this visit only and names the project in the first message instead. */
export async function buildRpc(params) {
  try {
    const answer = await callStudio(RPC_BUILD, params)

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

  return plan
    ? `Use hermretro to help me plan a new Game Boy Color game${title ? ` called "${title}"` : ''}: ${what}. Interview me briefly, then create the project, and write the game brief, backlog and test plan into it before building anything.`
    : `Use hermretro to make a new Game Boy Color game${title ? ` called "${title}"` : ''}: ${what}. Ask me a few quick questions first, then create the project, build it and show it to me in the emulator.`
}
