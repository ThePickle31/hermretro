// Restore the project first, then submit the rebuild in the same conversation.
import { host } from '#sdk'
import { callStudioOnly, describeRequestError } from '#app/backend.js'
import { RPC_BUILD_RESTORE } from '#app/rpc.js'
import { sendBuildChat } from './chat/actions.js'

/** Returns whether to close the Builds menu. A complete or incomplete restore already acted on the project. */
export async function restoreProjectBuild(game, stored, build, snapshot, onLibraryChanged) {
  let answer

  try {
    answer = await callStudioOnly(RPC_BUILD_RESTORE, { game, ...snapshot }, 60_000)
  } catch (error) {
    onLibraryChanged()
    host.notify({ kind: 'error', message: `Could not confirm restore of build #${build.n}: ${describeRequestError(error).message}` })

    return true
  }

  if (answer?.code === 'PARTIAL' || answer?.problems?.length) {
    onLibraryChanged()
    const detail = answer.problems?.[0]

    host.notify({ kind: 'error', message: `Restore of build #${build.n} was incomplete. The previous files were saved.${detail ? ` ${detail}` : ''}` })

    return true
  }

  if (!answer || answer.code === 'ERROR') {
    onLibraryChanged()
    host.notify({ kind: 'error', message: `Could not confirm restore of build #${build.n}: ${answer?.error ?? 'No restore result was returned.'}` })

    return true
  }

  if (!answer.ok) {
    host.notify({ kind: 'error', message: `Could not restore build #${build.n}: ${answer.error ?? 'Restore failed.'}` })

    return false
  }

  onLibraryChanged()
  try {
    const sent = await sendBuildChat(
      stored,
      `I restored the game to build #${build.n} ("${build.title}") from the hermretro Builds menu: its files are back as they were then (the version before this is saved). Please build it again and check that it still works.`,
      `Restore build #${build.n} \u00b7 ${build.title}`,
      [],
      { mustLand: true }
    )

    if (sent) {
      return true
    }
  } catch (error) {
    host.notify({ kind: 'error', message: `Build #${build.n} was restored, but the rebuild request failed: ${describeRequestError(error).message}` })

    return true
  }

  host.notify({ kind: 'error', message: `Build #${build.n} was restored. The rebuild request could not be confirmed.` })

  return true
}
