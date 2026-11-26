// The factory reset's state for its dialog: what each part holds (read when the dialog opens), the user's choices,
// the run's progress and its summary, and restarting Hermes's gateway afterwards.
import { host, useEffect, useState } from '#sdk'
import { callBackend } from '#app/backend.js'
import { STUDIO_PROFILE } from '#app/ids.js'
import { routeProfile, routing } from '#app/routing.js'
import { RPC_RESET_PLAN, RPC_STATUS } from '#app/rpc.js'
import { refreshDesktopHalf, requestOn } from '#app/update/flow.js'
import { setUpdating } from '#app/update/lock.js'
import { appProfile, connectionOf, DEFAULT_CHOICES, forgetReset, pendingReset, resetSteps, runReset, settleChoices } from './reset-steps.js'

const NO_PROFILE = 'No studio profile'

/** `profile` on the Hermes connection `here`: the app itself when it is on that profile there, else that profile's
 *  route there; null when there is none. A profile of the same name on another connection is never picked. */
async function profileOn(profile, here) {
  if (appProfile() === profile && connectionOf({ route: null }) === here) {
    return { route: null, profile }
  }

  const routes = typeof host.profileRoutes === 'function' ? ((await host.profileRoutes()) ?? []) : []
  const route = routes.find(candidate => routeProfile(candidate) === profile && (candidate.connectionId || 'local') === here)

  return route ? { route, profile } : null
}

/** Everything the dialog needs before anything is deleted: where each call goes (all on the Hermes connection that
 *  answered), and what each part holds. A profile the status says is there but that cannot be reached is an error,
 *  never read as "none". */
async function readContext() {
  const { data: status } = await callBackend(RPC_STATUS)

  if (!status?.ok) {
    throw new Error(status?.error || 'hermretro did not answer.')
  }

  const here = connectionOf({ route: routing.route })
  const installedIn = status.plugin?.installed_in ?? null
  const studio = status.profile?.is_studio || status.profile?.studio?.exists ? await profileOn(STUDIO_PROFILE, here) : null
  const installProfile = installedIn?.linked ? null : (installedIn?.profile ?? null)
  const install = installProfile ? await profileOn(installProfile, here) : null

  if ((status.profile?.is_studio || status.profile?.studio?.exists) && !studio) {
    throw new Error('The hermretro profile cannot be reached right now.')
  }

  if (installProfile && !install) {
    throw new Error(`The ${installProfile} profile, where hermretro is installed, cannot be reached right now.`)
  }

  // The backend's parts read this profile's plugin data (build history): the hermretro profile's when there is one.
  const target = studio ?? { route: routing.route, profile: routing.profile }
  const plan = await requestOn(target, RPC_RESET_PLAN, {}, 120_000)

  if (!plan?.ok) {
    throw new Error(plan?.error || 'What hermretro keeps could not be read.')
  }

  // The studio's chats and the profile itself go only when hermretro made it, and the profile only when deleting it
  // would not take hermretro itself with it and this Hermes can delete a profile from a plugin.
  const ours = studio ? (plan.parts.profile?.ours ? null : 'Not made by hermretro') : NO_PROFILE
  const holdsPlugin = Boolean(installedIn?.linked) || installedIn?.profile === STUDIO_PROFILE

  return {
    here,
    // The profile the app is on: a call without a route goes there, so the reset stops if the app moves.
    ambient: appProfile(),
    target,
    studio,
    install,
    version: status.plugin?.version ?? null,
    parts: plan.parts,
    locked: {
      chats: ours,
      profile: ours ?? (holdsPlugin ? 'hermretro is installed here' : typeof host.deleteProfile !== 'function' ? 'Update Hermes to delete it' : null),
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

    callBackend(RPC_STATUS).then(
      ({ data }) => data?.plugin?.version && setState(current => ({ ...current, version: data.plugin.version })),
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
      const here = state.context?.here ?? state.summary?.here

      if (here && connectionOf({ route: null }) !== here) {
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
