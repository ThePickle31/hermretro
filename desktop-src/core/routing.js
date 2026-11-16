// Which Hermes profile answers for hermretro, and how the page finds it.
import { host } from '../sdk.js'
import { STUDIO_PROFILE } from './ids.js'
import { RPC_STATUS } from './rpc.js'

// The page is app-wide, the plugin's backend is per profile. When the profile the app is on
// does not have it, use a profile that does (without switching the app to it) and send
// "Use in chat" prompts to that profile.
// `studio` is set when the route is the dedicated hermretro profile: it is then preferred
// over the profile the app is on, even when that one has the plugin too. `ambientStudio` is set when the
// app itself is on the hermretro profile (no route needed).
export const routing = { route: null, profile: null, scannedAt: 0, studio: false, ambientStudio: false }

/** Thrown by anything that must run in the hermretro profile when that profile is not ready. */
export class StudioProfileMissing extends Error {
  constructor() {
    super('The hermretro profile is not set up. Repair it from the Build page or Setup.')
    this.code = 'STUDIO_PROFILE_MISSING'
  }
}

/** Where Build chats, game chats and prompts go: ONLY the hermretro profile (its tools and prompt exist
 *  nowhere else). `{ route, profile }` for a routed call, `{ route: null, profile: null }` when the app is on
 *  that profile itself, or null when it is not ready: never another profile. */
export function studioTarget() {
  if (routing.studio && routing.route) {
    return { route: routing.route, profile: STUDIO_PROFILE }
  }

  return routing.ambientStudio || activeProfile() === STUDIO_PROFILE ? { route: null, profile: null } : null
}

function activeProfile() {
  try {
    return host.state.profile?.get?.() ?? null
  } catch {
    return null
  }
}

/** Forget the found route (ambientStudio follows the status the page renders, so it stays). */
export function forgetRoute() {
  routing.route = null
  routing.profile = null
  routing.studio = false
}
export const ROUTE_SCAN_EVERY_MS = 30_000

export function routeProfile(route) {
  return typeof route === 'string' ? route : (route?.targetProfile ?? route?.profile ?? null)
}

export async function findRoute() {
  if (typeof host.profileRoutes !== 'function' || typeof host.requestProfile !== 'function') {
    return null
  }

  let active = null

  try {
    active = host.state.profile?.get?.() ?? null
  } catch {
    active = null
  }

  const routes = [...((await host.profileRoutes().catch(() => [])) ?? [])]

  // The dedicated profile first, when there is one.
  routes.sort((a, b) => Number(routeProfile(b) === STUDIO_PROFILE) - Number(routeProfile(a) === STUDIO_PROFILE))

  for (const route of routes) {
    if (route?.profile === active) {
      continue // already asked, through the ambient connection
    }

    try {
      const data = await host.requestProfile(route, RPC_STATUS, {})

      if (data && typeof data === 'object' && 'ok' in data) {
        return { route }
      }
    } catch {
      // not on in that profile, or its backend is not reachable right now
    }
  }

  return null
}

/** Point the page at the dedicated hermretro profile, once it exists and answers. */
export async function adoptStudioRoute() {
  if (typeof host.profileRoutes !== 'function' || typeof host.requestProfile !== 'function') {
    return null
  }

  const routes = (await host.profileRoutes().catch(() => [])) ?? []
  const route = routes.find(candidate => routeProfile(candidate) === STUDIO_PROFILE)

  if (!route) {
    return null
  }

  try {
    const data = await host.requestProfile(route, RPC_STATUS, {})

    if (data?.ok && data.profile?.is_studio) {
      routing.route = route
      routing.profile = STUDIO_PROFILE
      routing.studio = true

      return data
    }
  } catch {
    // created, but its backend is not up yet: asked again on the next poll
  }

  return null
}
