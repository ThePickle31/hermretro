// Which Hermes profile answers for hermretro, and how the page finds it.
import { host } from '../sdk.js'
import { STUDIO_PROFILE } from './ids.js'
import { RPC_STATUS } from './rpc.js'

// The page is app-wide, the plugin's backend is per profile. When the profile the app is on
// does not have it, use a profile that does (without switching the app to it) and send
// "Use in chat" prompts to that profile.
// `studio` is set when the route is the dedicated hermretro profile: it is then preferred
// over the profile the app is on, even when that one has the plugin too.
export const routing = { route: null, profile: null, scannedAt: 0, studio: false }
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
