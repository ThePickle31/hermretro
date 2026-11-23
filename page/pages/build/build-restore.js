// Restore the project first, then submit the rebuild in the same conversation.
import { host } from '#sdk'
import { callStudioOnly, describeRequestError } from '#app/backend.js'
import { RPC_BUILD_RESTORE } from '#app/rpc.js'

/** Returns whether to close the Builds menu. A complete or incomplete restore already acted on the project. */
export async function restoreProjectBuild(game, snapshot, target, title, rebuild, onLibraryChanged) {
  const label = target[0].toUpperCase() + target.slice(1)
  let answer

  try {
    answer = await callStudioOnly(RPC_BUILD_RESTORE, { game, ...snapshot }, 60_000)
  } catch (error) {
    onLibraryChanged()
    host.notify({ kind: 'error', message: `Could not confirm restore of ${target}: ${describeRequestError(error).message}` })

    return true
  }

  if (answer?.code === 'PARTIAL' || answer?.problems?.length) {
    onLibraryChanged()
    const detail = answer.problems?.[0]
    const backup = answer.backup ? ` (snapshot ${answer.backup})` : ''

    host.notify({ kind: 'error', message: `Restore of ${target} was incomplete. The previous files were saved${backup}.${detail ? ` ${detail}` : ''}` })

    return true
  }

  if (!answer || answer.code === 'ERROR') {
    onLibraryChanged()
    host.notify({ kind: 'error', message: `Could not confirm restore of ${target}: ${answer?.error ?? 'No restore result was returned.'}` })

    return true
  }

  if (!answer.ok) {
    host.notify({ kind: 'error', message: `Could not restore ${target}: ${answer.error ?? 'Restore failed.'}` })

    return false
  }

  onLibraryChanged()
  try {
    const description = title ? `${target} ("${title}")` : `${target} (snapshot ${snapshot.id})`
    const sent = await rebuild(
      `I restored the game to ${description} from the hermretro Builds menu. The previous files are saved. Please build it again and check that it still works.`,
      title ? `Restore ${target} · ${title}` : `Restore ${target}`
    )

    if (sent) {
      return true
    }
  } catch (error) {
    host.notify({ kind: 'error', message: `${label} was restored, but the rebuild request failed: ${describeRequestError(error).message}` })

    return true
  }

  host.notify({ kind: 'error', message: `${label} was restored. The rebuild request could not be confirmed.` })

  return true
}
