// Updating hermretro from its own page: Hermes's update (the same one as Capabilities > Plugins), then what Hermes
// does not do by itself for us: reload the plugin in the hermretro profile (it only links the installed copy, and
// Hermes reloads only the profile that ran the update), refresh that profile's settings, and refresh this page.
// No React here, so the steps can be tested on their own.
import { host } from '#sdk'
import { ID } from '#app/ids.js'
import { routeProfile } from '#app/routing.js'
import { RPC_STUDIO_PROFILE } from '#app/rpc.js'

export const UPDATE_STEPS = ['Downloading and checking the new version', 'Loading it into the hermretro profile', 'Refreshing this page']
// Remembered across the page's own reload (the last step), so the new page can say how it went.
export const UPDATE_MARKER = 'update'
const UPDATE_TIMEOUT_MS = 300_000

/** Call `method` on `target` ({ route, profile }): the app's own connection when `route` is null. */
export function requestOn(target, method, params, timeoutMs) {
  return target.route ? host.requestProfile(target.route, method, params, timeoutMs) : host.request(method, params, timeoutMs)
}

/** Where Hermes's update runs: the profile the plugin was installed into (status `plugin.installed_in`), reached
 *  through the app's own connection when the app is on it, else through its profile route. Null when there is
 *  nothing Hermes can update (a linked checkout) or that profile cannot be reached. */
export async function installTarget(installedIn) {
  const profile = installedIn?.linked ? null : (installedIn?.profile ?? null)

  if (!profile) {
    return null
  }

  let active = null

  try {
    active = host.state.profile?.get?.() ?? null
  } catch {
    active = null
  }

  if (profile === active) {
    return { route: null, profile }
  }

  if (typeof host.profileRoutes !== 'function' || typeof host.requestProfile !== 'function') {
    return null
  }

  const routes = (await host.profileRoutes().catch(() => [])) ?? []
  const route = routes.find(candidate => routeProfile(candidate) === profile)

  return route ? { route, profile } : null
}

/** hermretro's row in Hermes's `plugins.manage list` answer, or null. */
export function pluginRow(list) {
  const rows = Array.isArray(list?.plugins) ? list.plugins : []

  return rows.find(row => row?.name === ID || row?.key === ID) ?? null
}

/** The page's copy of itself is refreshed only by the app: the same call Capabilities > Plugins makes after an
 *  update. Not part of the plugin SDK, so it is used only when the app has it; false when it does not. */
export async function refreshDesktopHalf() {
  const reconcile = globalThis.window?.hermesDesktop?.reconcileDesktopPlugins

  if (typeof reconcile !== 'function') {
    return false
  }

  try {
    await reconcile()

    return true
  } catch {
    return false
  }
}

/** Turn the plugin off and on again in the hermretro profile: Hermes then loads the new code there too (it
 *  reloaded only the profile that ran the update). True when that profile now runs it without a restart. */
async function reloadStudio(studio) {
  const toggle = enable => requestOn(studio, 'plugins.manage', { action: 'toggle', name: ID, enable }, 60_000)

  await toggle(false)

  let answer = null

  for (let attempt = 0; attempt < 2 && !answer?.ok; attempt += 1) {
    answer = await toggle(true).catch(() => null)
  }

  if (!answer?.ok) {
    throw new Error('hermretro could not be switched back on in the hermretro profile. Open Setup and press Repair.')
  }

  return Boolean(answer.gateway_reloaded) && !answer.restart_required
}

/** Run the whole update. `install` and `studio` are targets ({ route, profile }; `studio` null when there is no
 *  hermretro profile yet); `options` carries `force` / `accept_capabilities` after the user agreed to what Hermes
 *  asked; `onStep(i)` follows UPDATE_STEPS. Resolves to one outcome, never throws:
 *  `{ kind: 'updated', restart, pageRefreshed }`, `{ kind: 'current' }`, `{ kind: 'review', findings, lines,
 *  retry }` (Hermes wants the user to agree to something first: retry with `retry`), `{ kind: 'blocked', error }`
 *  (the security check refused the new version) or `{ kind: 'failed', error }`. */
export async function runUpdate({ install, studio, options = {}, onStep = () => {}, remember = () => {} }) {
  onStep(0)

  let result

  try {
    result = await requestOn(install, 'plugins.manage', { action: 'update', name: ID, ...options }, UPDATE_TIMEOUT_MS)
  } catch (error) {
    return { kind: 'failed', error: String(error?.message ?? error ?? 'The update did not finish.') }
  }

  if (result?.scan_blocked) {
    const findings = Array.isArray(result.scan_findings) ? result.scan_findings : []

    return result.scan_verdict === 'caution' && !options.force
      ? { kind: 'review', findings, lines: [], retry: { force: true } }
      : { kind: 'blocked', error: `Hermes's security check stopped this version (${result.scan_verdict ?? 'blocked'}). Nothing was changed.` }
  }

  if (result?.consent_required) {
    return options.accept_capabilities
      ? { kind: 'failed', error: result.error ?? 'Hermes did not apply the update.' }
      : { kind: 'review', findings: [], lines: Array.isArray(result.delta_lines) ? result.delta_lines : [], retry: { accept_capabilities: true } }
  }

  if (!result?.ok) {
    return { kind: 'failed', error: result?.error ?? 'The update did not finish.' }
  }

  if (result.unchanged) {
    return { kind: 'current' }
  }

  let restart = Boolean(result.restart_required)

  onStep(1)

  if (studio && studio.profile !== install.profile) {
    // Settings the new version ships for the hermretro profile (its SOUL, toolsets): best effort, a Repair redoes it.
    await requestOn(install, RPC_STUDIO_PROFILE, {}, 240_000).catch(() => null)

    try {
      restart = !(await reloadStudio(studio)) || restart
    } catch (error) {
      return { kind: 'failed', error: String(error?.message ?? error) }
    }
  }

  onStep(2)
  remember({ result: 'updated', restart, at: Date.now() })

  return { kind: 'updated', restart, pageRefreshed: await refreshDesktopHalf() }
}

