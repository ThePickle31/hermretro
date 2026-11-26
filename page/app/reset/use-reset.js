// The factory reset's state for its dialog: what each part holds (read when the dialog opens), the user's choices,
// the run's progress and its summary, and restarting Hermes's gateway afterwards.
import { host, useEffect, useState } from '#sdk'
import { STUDIO_PROFILE } from '#app/ids.js'
import { routeProfile } from '#app/routing.js'
import { RPC_RESET_PLAN, RPC_STATUS } from '#app/rpc.js'
import { refreshDesktopHalf, requestOn } from '#app/update/flow.js'
import { setUpdating } from '#app/update/lock.js'
import { appProfile, connectionOf, DEFAULT_CHOICES, forgetReset, pendingReset, resetSteps, runReset, settleChoices } from './reset-steps.js'

const NO_PROFILE = 'No studio profile'
const NOT_OURS = 'Not made by hermretro'

/** `profile` on the Hermes connection `here`, always through its own route (so a call reaches that profile there
 *  whatever the app switches to meanwhile); null when there is none. A profile of the same name on another connection
 *  is never picked. */
async function profileOn(profile, here) {
  const routes = typeof host.profileRoutes === 'function' ? ((await host.profileRoutes()) ?? []) : []
  const route = routes.find(candidate => routeProfile(candidate) === profile && (candidate.connectionId || 'local') === here)

  return route ? { route, profile } : null
}

/** hermretro's status on the connection `here`, through an explicit route: from the hermretro profile when it answers
 *  there, else the profile the app is on (`ambient`), else any other profile there (hermretro may be installed in one
 *  the app is not on). `skip`: profiles not to ask. `{ status, answered }`, or null when none answers. */
async function statusOn(here, ambient, skip = []) {
  const routes = typeof host.profileRoutes === 'function' ? ((await host.profileRoutes()) ?? []) : []
  const others = routes.filter(route => (route.connectionId || 'local') === here).map(routeProfile)
  const profiles = [...new Set([STUDIO_PROFILE, ambient, ...others].filter(profile => profile && !skip.includes(profile)))]

  for (const profile of profiles) {
    const target = await profileOn(profile, here)

    if (!target) {
      continue
    }

    try {
      const status = await requestOn(target, RPC_STATUS, {}, 60_000)

      if (status?.ok) {
        return { status, answered: target }
      }
    } catch {
      // hermretro is not on in that profile, or it cannot be reached right now
    }
  }

  return null
}

async function readPlan(target) {
  const plan = await requestOn(target, RPC_RESET_PLAN, {}, 120_000)

  if (!plan?.ok) {
    throw new Error(plan?.error || 'What hermretro keeps could not be read.')
  }

  return plan
}

/** Everything the dialog needs before anything is deleted: where each call goes (all on the Hermes connection the app
 *  is on as the dialog opens, never one a page reached earlier), and what each part holds. A profile the status says
 *  is there but that cannot be reached is an error, never read as "none". */
async function readContext() {
  const here = connectionOf({ route: null })
  const ambient = appProfile()
  const found = await statusOn(here, ambient)

  if (!found) {
    throw new Error('hermretro did not answer on this Hermes.')
  }

  let { status, answered } = found
  const named = status.profile?.studio ?? {}
  // A profile named hermretro that hermretro made and set up; one of the user's own with that name is never used.
  const made = Boolean(status.profile?.is_studio || (named.exists && named.ours && named.installed))
  let studio = made ? (answered.profile === STUDIO_PROFILE ? answered : await profileOn(STUDIO_PROFILE, here)) : null

  if (made && !studio) {
    throw new Error('The hermretro profile cannot be reached right now.')
  }

  // The backend's parts read this profile's plugin data (build history): the hermretro profile's when there is one.
  let target = studio ?? answered
  let plan = await readPlan(target)

  // A profile of the user's own named hermretro with hermretro on in it answers as the studio: none of the reset goes
  // there, but to another profile with hermretro on.
  let foreign = !made && Boolean(named.exists)

  if (studio && !plan.parts.profile?.ours) {
    const other = await statusOn(here, ambient, [STUDIO_PROFILE])

    if (!other) {
      throw new Error('hermretro answers only in a profile named hermretro that it did not make.')
    }

    studio = null
    foreign = true
    ;({ status, answered } = other)
    target = answered
    plan = await readPlan(target)
  }

  // Where Hermes updates hermretro, from the status of the profile the reset runs in.
  const installedIn = status.plugin?.installed_in ?? null
  const installProfile = installedIn?.linked ? null : (installedIn?.profile ?? null)
  const install = installProfile ? await profileOn(installProfile, here) : null

  if (installProfile && !install) {
    throw new Error(`The ${installProfile} profile, where hermretro is installed, cannot be reached right now.`)
  }

  // The studio's chats and the profile itself go only when hermretro made it, and the profile only when deleting it
  // would not take hermretro itself with it and this Hermes can delete a profile from a plugin.
  const ours = studio ? null : foreign ? NOT_OURS : NO_PROFILE
  const holdsPlugin = Boolean(installedIn?.linked) || installedIn?.profile === STUDIO_PROFILE

  return {
    here,
    // The profile the app is on: the restart (which goes to the app's own gateway) checks it is still there.
    ambient,
    target,
    studio,
    install,
    version: status.plugin?.version ?? null,
    parts: plan.parts,
    locked: {
      chats: ours,
      profile: ours ?? (holdsPlugin ? 'hermretro is installed here' : plan.parts.profile?.holds ? 'Holds your games' : typeof host.deleteProfile !== 'function' ? 'Update Hermes to delete it' : null),
      toolchain: plan.parts.toolchain?.custom ? 'A folder you chose' : null
    }
  }
}

/** `phase`: closed, loading, failed (the context could not be read), choose, confirm, running, done. */
export function useReset(ctx) {
  const [state, setState] = useState(() => {
    const summary = pendingReset(ctx)

    return summary ? { phase: 'done', summary } : { phase: 'closed' }
  })
  const [choices, setChoices] = useState(DEFAULT_CHOICES)
  const [restarting, setRestarting] = useState(false)
  // What the user typed to confirm.
  const [typed, setTyped] = useState('')
  const context = state.context ?? null
  const settled = settleChoices(choices, context?.locked)

  useEffect(() => {
    if (state.phase !== 'loading') {
      return
    }

    let live = true

    readContext().then(
      found => live && setState({ phase: 'choose', context: found }),
      error => live && setState({ phase: 'failed', error: String(error?.message ?? error) })
    )

    return () => {
      live = false
    }
  }, [state.phase])

  // After an update, the version this page now runs (the summary knows only the one it started from).
  const updated = state.phase === 'done' && state.summary?.update?.kind === 'updated'

  useEffect(() => {
    if (!updated || state.version) {
      return
    }

    // From the install that was updated, through its own route (the summary keeps it across the page's reload).
    const install = state.summary?.install

    if (!install) {
      return
    }

    requestOn(install, RPC_STATUS, {}, 60_000).then(
      data => data?.plugin?.version && setState(current => ({ ...current, version: data.plugin.version })),
      () => {}
    )
  }, [updated])

  const run = async () => {
    const steps = resetSteps(settled.choices)

    setState(current => ({ ...current, phase: 'running', steps, step: 0 }))
    setUpdating(true)

    let summary

    try {
      summary = await runReset({
        ctx,
        choices: settled.choices,
        ...context,
        onStep: step => setState(current => ({ ...current, step }))
      })
    } finally {
      setUpdating(false)
    }

    setState(current => ({ ...current, phase: 'done', summary }))
  }

  const close = () => {
    if (state.phase === 'running') {
      return
    }

    forgetReset(ctx)
    setChoices(DEFAULT_CHOICES)
    setTyped('')
    setState({ phase: 'closed' })
  }

  const restart = async () => {
    setRestarting(true)

    try {
      // The gateway restarted is the app's current one: not when Hermes has switched to another since the reset.
      // The summary's: it follows Hermes moving the app off a deleted studio profile.
      const here = state.summary?.here ?? state.context?.here
      const ambient = state.summary?.ambient ?? state.context?.ambient

      if ((here && connectionOf({ route: null }) !== here) || (ambient && appProfile() !== ambient)) {
        throw new Error('Hermes is on another connection now.')
      }

      // False when the user said no to Hermes's question, or the restart failed: the done screen stays to try again.
      if ((await host.restartGateway()) !== false) {
        forgetReset(ctx)
        await refreshDesktopHalf()
      }
    } catch (error) {
      host.notify({ kind: 'error', message: `The gateway did not restart: ${String(error?.message ?? error)}` })
    } finally {
      setRestarting(false)
    }
  }

  return {
    ...state,
    choices: settled.choices,
    forced: settled.forced,
    notes: settled.notes,
    typed,
    type: setTyped,
    choose: (id, value) => setChoices(current => ({ ...current, [id]: value })),
    deleteAll: () => setChoices(Object.fromEntries(Object.keys(DEFAULT_CHOICES).map(id => [id, 'delete']))),
    open: () => setState({ phase: 'loading' }),
    confirm: () => setState(current => ({ ...current, phase: 'confirm' })),
    back: () => setState(current => ({ ...current, phase: 'choose' })),
    close,
    run: () => void run(),
    canRestart: typeof host.restartGateway === 'function',
    restarting,
    restart: () => void restart()
  }
}
