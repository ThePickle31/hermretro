// The toolchain install driven by the page (no chat): state, polling and the studio profile.
import { host, useQuery, useState } from '#sdk'
import { callBackend, describeRequestError, nodeState } from '#app/backend.js'
import { sendPromptToChat } from '#app/chat-insert.js'
import { ID } from '#app/ids.js'
import { RPC_INSTALL, RPC_STUDIO_PROFILE } from '#app/rpc.js'
import { isUpdating, UPDATING_MESSAGE, useUpdating } from '#app/update/lock.js'

const SETUP_PROMPT =
  'Set up hermretro so I can create games, build ROMs, and run automated playtests. Check what is already installed and prepare the missing dependencies.'

async function fetchInstall() {
  return (await callBackend(RPC_INSTALL, { action: 'status' }, 30_000)).data
}

const installInterval = arg => ((arg?.state ? arg.state.data : arg)?.install?.state === 'running' ? 1_500 : 5_000)

/** The install's status: polled quickly while it runs, slowly otherwise. */
export function useInstall({ enabled }) {
  return useQuery({
    queryKey: [ID, 'install'],
    queryFn: fetchInstall,
    enabled,
    refetchInterval: enabled ? installInterval : false,
    staleTime: 1_000,
    retry: false
  })
}

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

/** Everything one install view needs: phase, rows, actions. Shared by onboarding and the Setup step. */
export function useInstaller({ ctx, status, install, toolchainDone }) {
  const [starting, setStarting] = useState(false)
  const [failure, setFailure] = useState(null)
  const [profileWork, setProfileWork] = useState({ state: 'idle', error: null })
  // A chat is already preparing the tools: wait for it instead of reporting a failure.
  const [elsewhere, setElsewhere] = useState(false)
  const data = install.data
  const unsupported = install.isError && describeRequestError(install.error).notLoaded
  const state = data?.install?.state ?? 'idle'
  const profile = status.data?.profile
  const needsProfile = Boolean(profile && !profile.is_studio && !profile.studio?.installed)
  const node = nodeState(status.data?.node)
  // While hermretro updates, the install and the profile setup wait (their buttons read `updating`).
  const updating = useUpdating()

  const makeProfile = () => {
    if (!needsProfile) {
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

  const start = async () => {
    if (starting) {
      return
    }

    if (isUpdating()) {
      setFailure(UPDATING_MESSAGE)

      return
    }

    setStarting(true)
    setFailure(null)
    // The profile is made while the tools download.
    makeProfile()

    try {
      const { data: answer } = await callBackend(RPC_INSTALL, { action: 'start' }, 60_000)

      if (answer?.code === 'OPERATION_IN_PROGRESS') {
        setElsewhere(true)

        return
      }

      if (!answer?.ok) {
        throw new Error(answer?.error || 'The install could not start.')
      }

      setElsewhere(false)
      await install.refetch?.()
    } catch (error) {
      setFailure(describeRequestError(error).message || String(error?.message ?? error))
    } finally {
      setStarting(false)
    }
  }

  const ask = () =>
    sendPromptToChat(
      ctx,
      `${SETUP_PROMPT}\n\nThe install on the hermretro page stopped with this error:\n${failure ?? data?.install?.error ?? 'unknown error'}`,
      { fresh: true }
    )

  const verifying = (state === 'done' || elsewhere) && !toolchainDone
  const phase = toolchainDone
    ? 'done'
    : starting || state === 'running' || verifying
      ? 'running'
      : failure || state === 'failed'
        ? 'failed'
        : 'review'

  return {
    ask,
    data,
    elsewhere,
    failure: failure ?? data?.install?.error ?? null,
    makeProfile,
    needsProfile,
    node,
    phase,
    profileWork,
    start,
    starting,
    state,
    unsupported,
    updating,
    verifying
  }
}
