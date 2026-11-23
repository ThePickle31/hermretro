// Calls to the hermretro backend through the gateway, and the status / doctor queries.
import { host, useQuery, useValue } from '#sdk'
import { ID, STUDIO_PROFILE } from './ids.js'
import { adoptStudioRoute, findRoute, ROUTE_SCAN_EVERY_MS, routeProfile, routing, StudioProfileMissing, studioTarget } from './routing.js'
import { RPC_DOCTOR, RPC_STATUS } from './rpc.js'

/** A rejected `host.request` (backend not loaded, unknown method, gateway down). */
export function describeRequestError(error) {
  const message = String(error?.message ?? error ?? '')
  const notLoaded = error?.code === -32601 || /-32601|unknown method|method not found/i.test(message)

  return { message, notLoaded }
}

/** Call the plugin's backend: in the hermretro profile when there is one, else in the
 *  profile the app is on, else in any profile that has it. Resolves to `{ data, profile }`: the RPC's
 *  answer is `data` (`(await callBackend(RPC_GAMES)).data`), `profile` the profile that answered or null.
 *  callStudio and callStudioOnly (below) resolve to the answer itself. */
export async function callBackend(method, params = {}, timeoutMs) {
  if (routing.studio && routing.route) {
    try {
      return { data: await host.requestProfile(routing.route, method, params, timeoutMs), profile: routing.profile }
    } catch (error) {
      if (!describeRequestError(error).notLoaded) {
        throw error
      }

      routing.route = null
      routing.profile = null
      routing.studio = false
    }
  }

  try {
    const data = await host.request(method, params, timeoutMs)

    routing.route = null
    routing.profile = null

    return { data, profile: null }
  } catch (error) {
    if (!describeRequestError(error).notLoaded) {
      throw error
    }

    // Asking every profile is not free: do it on open and on Refresh (Setup's Check everything again,
    // the not-running panel), then only now and again.
    if (!routing.route && Date.now() - routing.scannedAt >= ROUTE_SCAN_EVERY_MS) {
      routing.scannedAt = Date.now()

      const found = await findRoute()

      if (found) {
        routing.route = found.route
        routing.profile = routeProfile(found.route)
        routing.studio = routing.profile === STUDIO_PROFILE
      }
    }

    if (!routing.route) {
      throw error
    }

    try {
      return { data: await host.requestProfile(routing.route, method, params, timeoutMs), profile: routing.profile }
    } catch (inner) {
      if (describeRequestError(inner).notLoaded) {
        routing.route = null
        routing.profile = null
      }

      throw inner
    }
  }
}

async function fetchStatus(sessionId) {
  // `chat` only picks which conversation's project to report. It is deliberately not sent as
  // `session_id`: the gateway treats that as a session to authorize and rejects the whole call
  // (not_found) for a chat that has no live session yet, such as a new draft.
  const { data, profile } = await callBackend(RPC_STATUS, sessionId ? { chat: sessionId } : {})

  // Answered by the profile the plugin was installed into, and the dedicated profile has since
  // been made: move over to it.
  if (data?.ok && data.profile && !data.profile.is_studio && data.profile.studio?.installed && !routing.studio) {
    const studio = await adoptStudioRoute()

    if (studio) {
      return { ...studio, via_profile: STUDIO_PROFILE }
    }
  }

  return profile ? { ...data, via_profile: profile } : data
}

async function fetchDoctor() {
  return (await callBackend(RPC_DOCTOR, {}, 60_000)).data
}

export function useBackend({ fast, pollDoctor }) {
  const gateway = useValue(host.state.gateway)
  const sessionId = useValue(host.state.focusedSessionId)
  const connected = gateway === 'open'

  const status = useQuery({
    queryKey: [ID, 'status', sessionId ?? null],
    queryFn: () => fetchStatus(sessionId),
    enabled: connected,
    // Cheap and passive. Poll quickly during setup so a finished step is noticed at once.
    refetchInterval: fast ? 4_000 : 30_000,
    staleTime: 2_000,
    retry: false
  })

  const statusOk = Boolean(status.data?.ok)

  // Doctor reads tool metadata on disk: run it when the page mounts and on Refresh (Setup's Check everything again), and
  // repeat it only while the toolchain step is the one waiting to complete.
  const doctor = useQuery({
    queryKey: [ID, 'doctor', status.data?.via_profile ?? null],
    queryFn: fetchDoctor,
    enabled: connected && statusOk,
    staleTime: Infinity,
    refetchInterval: pollDoctor ? 8_000 : false,
    refetchOnMount: 'always',
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
    retry: false
  })

  let backend = 'checking'

  if (!connected) {
    backend = 'offline'
  } else if (status.isError) {
    // Not loaded in any profile, versus loaded but the call itself failed.
    backend = describeRequestError(status.error).notLoaded ? 'unavailable' : 'failed'
  } else if (status.data && !status.data.ok) {
    backend = 'error'
  } else if (statusOk) {
    backend = 'ok'
  }

  return { backend, connected, doctor, gateway, status }
}

export function nodeState(node) {
  if (!node) {
    return { ok: false, label: 'Unknown' }
  }

  const required = parseInt(String(node.required ?? '22'), 10) || 22
  const major = parseInt(String(node.version ?? '').replace(/^v/i, ''), 10)
  const ok = Boolean(node.found) && Number.isFinite(major) && major >= required

  return { ok, required, version: node.found ? node.version : null }
}

/** The newer studio RPCs go to the backend that answered `status`, without a profile scan: a
 *  backend that predates them answers -32601, which the pages report as "needs an update".
 *  Resolves to the RPC's answer itself (`await callStudio(RPC_GAMES)` is the games list), not `{ data }`. */
export async function callStudio(method, params = {}, timeoutMs) {
  return routing.route ? host.requestProfile(routing.route, method, params, timeoutMs) : host.request(method, params, timeoutMs)
}

/** RPCs that read or bind a profile's conversations (build, builds, build_restore, asset*), or read its plugin
 *  data folder (host._data_dir(), one per profile: the history snapshots builds/build_restore list and restore,
 *  the asset versions and saved frames asset* read). Chosen by what the handler reads, not by the feature or page
 *  the RPC belongs to: one that answers the same from any profile with the plugin (games, player, captures: the
 *  shared hermretro home; games' chat titles are best effort) uses callStudio. Goes to the hermretro profile only
 *  (studioTarget(): its route, or the app itself when the app is on that profile), like the Build chats
 *  themselves, never whichever profile answered `status`; StudioProfileMissing otherwise. Resolves to the RPC's
 *  answer itself, like callStudio. */
export async function callStudioOnly(method, params = {}, timeoutMs) {
  const target = studioTarget()

  if (!target) {
    throw new StudioProfileMissing()
  }

  return target.route ? host.requestProfile(target.route, method, params, timeoutMs) : host.request(method, params, timeoutMs)
}

export function studioError(error, what) {
  const { message, notLoaded } = describeRequestError(error)

  return notLoaded
    ? `This hermretro backend cannot ${what} yet. Update the plugin in the profile it runs in.`
    : message || 'Unknown error'
}
