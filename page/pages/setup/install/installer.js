// The toolchain install driven by the page (no chat): state, polling and the studio profile.
import { host, useState } from '#sdk'
import { callBackend, describeRequestError, nodeState } from '#app/backend.js'
import { sendPromptToChat } from '#app/chat-insert.js'
import { forgetRoute, routing } from '#app/routing.js'
import { RPC_INSTALL, RPC_STUDIO_PROFILE } from '#app/rpc.js'
import { isUpdating, UPDATING_MESSAGE, useUpdating } from '#app/update/lock.js'
import { confirmedInstall, INSTALL_STATUS_UNKNOWN } from './install-status.js'

const SETUP_PROMPT =
  'Set up hermretro so I can create games, build ROMs, and run automated playtests. Check what is already installed and prepare the missing dependencies.'

/** Hermes creates the profile; the plugin then makes it a hermretro one. */
async function createStudioProfile(profile) {
  if (isUpdating()) {
    throw new Error(UPDATING_MESSAGE)
  }

  if (!profile.studio?.exists) {
    await host.request('profiles.create', profile.create)
  }

  const { data } = await callBackend(RPC_STUDIO_PROFILE, {}, 240_000)

  if (!data?.ok) {
    throw new Error(data?.error || 'The profile could not be set up.')
  }
}

// One profile creation at a time, whether started by the install or the Setup page's own button.
let profileCreation = null

export function createStudioProfileOnce(profile) {
  profileCreation ??= createStudioProfile(profile).finally(() => {
    profileCreation = null
  })

  return profileCreation
}

// What a stopped install (state) looks like on the page: every one of these offers a way on.
const STOPPED = ['failed', 'cancelled', 'interrupted']

/** The tools check ran after the install finished (react-query's update times; a stub without them counts as checked). */
function checkedSince(doctor, finishedAt) {
  if (!doctor || doctor.isFetching || !(doctor.data || doctor.isError)) {
    return false
  }

  const at = Math.max(doctor.dataUpdatedAt ?? 0, doctor.errorUpdatedAt ?? 0)

  return !at || !finishedAt || at >= finishedAt * 1000
}

/** Everything one install view needs: phase, rows, actions. Shared by onboarding and the Setup step.
 *  `doctor` is the tools check: it decides whether a finished install verified, and what to offer when not. */
export function useInstaller({ ctx, status, install, toolchainDone, doctor }) {
  const [failure, setFailure] = useState(null)
  // A cancel that did not go through, shown while the install it was meant to stop keeps running.
  const [cancelError, setCancelError] = useState(null)
  const [profileWork, setProfileWork] = useState({ state: 'idle', error: null })
  // A chat is already preparing the tools: wait for it instead of reporting a failure. The backend says so too
  // (`install.elsewhere`); an older one does not, and then only this answer to the start is known.
  const [elsewhere, setElsewhere] = useState(false)
  const { data, canStart, starting, unavailable } = install
  const unsupported = data?.unsupported || (install.isError && describeRequestError(install.error).notLoaded)
  const state = data?.install?.state ?? 'idle'
  const profile = status.data?.profile
  const needsProfile = Boolean(profile && !profile.is_studio && !profile.studio?.installed)
  // A profile named hermretro that someone else made: finishing it is refused, so nothing is downloaded either.
  const conflict = Boolean(needsProfile && profile.studio?.conflict)
  const node = nodeState(status.data?.node)
  // Without the download list there is nothing to review: never start blind.
  const manifestReady = Boolean(data?.manifest?.items?.length) && Number(data?.manifest?.bytes) > 0
  const noSpace = data?.space?.enough === false
  const backendElsewhere = data?.install?.elsewhere
  const waitingElsewhere = backendElsewhere === true || (elsewhere && backendElsewhere === undefined)
  // The chat's install ended without the tools verifying: say so, and offer the page's own install.
  const elsewhereEnded = elsewhere && backendElsewhere === false && !toolchainDone
  // While hermretro updates, the install and the profile setup wait (their buttons read `updating`).
  const updating = useUpdating()

  const makeProfile = () => {
    if (!needsProfile || conflict) {
      return
    }

    setProfileWork({ state: 'running', error: null })
    createStudioProfileOnce(profile).then(
      () => {
        setProfileWork({ state: 'done', error: null })
        status.refetch?.()
      },
      error => setProfileWork({ state: 'failed', error: String(error?.message ?? error) })
    )
  }

  // The profile is made but its route never answers: finish it again and look for its route afresh.
  const repairProfile = async () => {
    if (!profile) {
      return
    }

    setProfileWork({ state: 'running', error: null })

    try {
      await createStudioProfileOnce(profile)
      routing.scannedAt = 0
      forgetRoute()
      setProfileWork({ state: 'done', error: null })
      await status.refetch?.()
    } catch (error) {
      setProfileWork({ state: 'failed', error: String(error?.message ?? error) })
    }
  }

  const start = async () => {
    if (!canStart || starting || waitingElsewhere || !manifestReady || conflict || noSpace) {
      return
    }

    if (isUpdating()) {
      setFailure(UPDATING_MESSAGE)

      return
    }

    setFailure(null)
    try {
      const answer = await install.start()

      if (answer?.code === 'OPERATION_IN_PROGRESS') {
        setElsewhere(true)
        await install.refetch?.()

        return
      }

      if (!answer || answer.code === 'UNAVAILABLE') {
        return
      }

      if (!answer?.ok) {
        throw new Error(answer?.error || 'The install could not start.')
      }

      // The profile is made while the tools download.
      makeProfile()
      setElsewhere(false)
    } catch (error) {
      setFailure(describeRequestError(error).message || String(error?.message ?? error))
    }
  }

  /** Ask the install on screen (its run_id) to stop: the engine's own cancellation, then the page waits for it to
   *  let go. A cancel that arrives after that run ended never stops a retry started since. */
  const cancel = async () => {
    setCancelError(null)

    try {
      const { data: answer } = await callBackend(RPC_INSTALL, { action: 'cancel', run_id: data?.install?.run_id ?? null }, 30_000)

      if (!confirmedInstall(answer)) {
        setCancelError(answer?.error || INSTALL_STATUS_UNKNOWN)
      }
    } catch (error) {
      setCancelError(describeRequestError(error).message || String(error?.message ?? error))
    }

    await install.refetch?.()
  }

  /** Read the download list, the profile and the tools again (nothing is installed). */
  const recheck = async () => {
    setFailure(null)
    await Promise.all([install.refetch?.(), status.refetch?.(), doctor?.refetch?.()])
  }

  const ask = () =>
    sendPromptToChat(
      ctx,
      `${SETUP_PROMPT}\n\nThe install on the hermretro page stopped with this error:\n${failure ?? data?.install?.error ?? 'unknown error'}`,
      { fresh: true }
    )

  // Finished, checked again, and still not ready: a failed verification, never an endless "checking".
  const unverified = state === 'done' && !toolchainDone && checkedSince(doctor, data?.install?.finished_at)
  const verifying = ((state === 'done' && !unverified) || waitingElsewhere) && !toolchainDone
  const phase = toolchainDone
    ? 'done'
    : starting || state === 'running' || verifying
      ? 'running'
      : failure || unverified || STOPPED.includes(state)
        ? 'failed'
        : 'review'
  const missing = doctor?.data?.ok ? (doctor.data.missing_required ?? []) : []

  return {
    ask,
    cancel,
    cancelError: state === 'running' ? cancelError : null,
    cancelling: Boolean(data?.install?.cancelling),
    conflict,
    canStart,
    data,
    doctor,
    elsewhere: waitingElsewhere,
    elsewhereEnded,
    failure: failure ?? data?.install?.error ?? null,
    hint: failure ? null : (data?.install?.hint ?? null),
    makeProfile,
    manifestReady,
    missing,
    needsProfile,
    node,
    noSpace,
    phase,
    spaceWarning: data?.space?.warning ?? null,
    profile,
    profileWork,
    recheck,
    repairProfile,
    start,
    starting,
    state,
    unavailable,
    unsupported,
    unverified,
    updating,
    verifying
  }
}
