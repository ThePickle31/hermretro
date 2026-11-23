import { callStudioOnly } from '#app/backend.js'
import { RPC_BUILDS } from '#app/rpc.js'

export async function requestBuildSnapshots(game, stored) {
  const answer = await callStudioOnly(RPC_BUILDS, { game, stored }, 20_000)

  return answer?.ok && Array.isArray(answer.builds) ? answer.builds : false
}

/** An exact result reference, or a stored call ID and timestamp corroborated by the backend. */
export function snapshotFor(build, snapshots) {
  if (!Array.isArray(snapshots)) {
    return null
  }

  const matches = snapshots.flatMap(snap => {
    const refs = Array.isArray(snap.buildRefs) ? snap.buildRefs : []
    const calls = Array.isArray(snap.buildCalls) ? snap.buildCalls : []
    const candidates = build.buildRef
      ? [build.buildRef]
      : calls.filter(call => build.resultCall && build.resultCall.id === call.id && build.resultCall.timestamp === call.timestamp).map(call => call.ref)

    return candidates.filter(ref => refs.includes(ref)).map(buildRef => ({ id: String(snap.id), buildRef }))
  })

  return matches.length === 1 ? matches[0] : null
}
