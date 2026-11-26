// The factory reset's state for its dialog: what each part holds (read when the dialog opens), the user's choices,
// the run's progress and its summary, and restarting Hermes's gateway afterwards.
import { host, useEffect, useState } from '#sdk'
import { callBackend } from '#app/backend.js'
import { STUDIO_PROFILE } from '#app/ids.js'
import { routing } from '#app/routing.js'
import { RPC_RESET_PLAN, RPC_STATUS } from '#app/rpc.js'
import { installTarget, refreshDesktopHalf, requestOn, studioReloadTarget } from '#app/update/flow.js'
import { setUpdating } from '#app/update/lock.js'
import { DEFAULT_CHOICES, forgetReset, pendingReset, resetSteps, runReset, settleChoices } from './reset-steps.js'

const NO_PROFILE = 'No studio profile'

/** Everything the dialog needs before anything is deleted: where each call goes, and what each part holds. */
async function readContext() {
  const { data: status } = await callBackend(RPC_STATUS)

  if (!status?.ok) {
    throw new Error(status?.error || 'hermretro did not answer.')
  }

  const installedIn = status.plugin?.installed_in ?? null
  const studio = await studioReloadTarget(Boolean(status.profile?.is_studio || status.profile?.studio?.exists))
  // The backend's parts read this profile's plugin data (build history): the hermretro profile's when there is one.
  const target = studio ?? { route: routing.route, profile: routing.profile }
  const plan = await requestOn(target, RPC_RESET_PLAN, {}, 120_000)

  if (!plan?.ok) {
    throw new Error(plan?.error || 'What hermretro keeps could not be read.')
  }

  // Deleting the studio profile would take hermretro itself with it when that is where it is installed.
  const holdsPlugin = Boolean(installedIn?.linked) || installedIn?.profile === STUDIO_PROFILE

  return {
    target,
    studio,
    install: await installTarget(installedIn),
    version: status.plugin?.version ?? null,
    parts: plan.parts,
    locked: {
      chats: studio ? null : NO_PROFILE,
      profile: studio ? (holdsPlugin ? 'hermretro is installed here' : null) : NO_PROFILE,
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
      await host.restartGateway()
      forgetReset(ctx)
      await refreshDesktopHalf()
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
