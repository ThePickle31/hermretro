// The update state every page shares (shell.pluginUpdate): whether Hermes found a newer hermretro, the Update
// button's progress, and how the last update went (told by the page that loads after it).
import { host, useEffect, useQuery, useQueryClient, useRef, useState } from '#sdk'
import { LINKS } from '#shared/ui/links.js'
import { ID, PLUGINS_HREF, STUDIO_PROFILE } from '#app/ids.js'
import { routing } from '#app/routing.js'
import { busyChats, busySentence, installTarget, pluginRow, requestOn, runReload, runUpdate, studioReloadTarget, UPDATE_MARKER } from './flow.js'
import { setUpdating } from './lock.js'

// Hermes checks for plugin updates about once a day; reading its answer is cheap but not free (every plugin's row).
const CHECK_EVERY_MS = 30 * 60_000
// A marker older than this is from an update whose page never came back: not worth announcing.
const MARKER_FRESH_MS = 15 * 60_000
const DONE_SHOWN_MS = 10_000
// While an update is ready, how often the hermretro profile's chats are checked for a build under way.
const BUSY_EVERY_MS = 5_000
const installingSentence = verb => `The game tools are being installed. You can ${verb} when that finishes.`
// Hermes installed the new version but the rest (the hermretro profile, the page) did not finish: { at, error }. Kept
// until a run finishes, so Finish update resumes it even though Hermes now answers "unchanged".
const PENDING = 'updatePending'

function pendingUpdate(ctx) {
  try {
    const pending = ctx.storage.get(PENDING, null)

    return pending && typeof pending === 'object' ? pending : null
  } catch {
    return null
  }
}

function takeMarker(ctx) {
  try {
    const marker = ctx.storage.get(UPDATE_MARKER, null)

    if (marker) {
      ctx.storage.set(UPDATE_MARKER, null)
    }

    return marker && Date.now() - Number(marker.at ?? 0) < MARKER_FRESH_MS ? marker : null
  } catch {
    return null
  }
}

function remember(ctx, key, value) {
  try {
    ctx.storage.set(key, value)
  } catch {
    // for this visit only
  }
}

/** What a 'restart' phase asks for: the Hermes gateway did not load the new code, or only the page's copy is old
 *  (the app reloads it when reopened). */
const RESTART_ADVICE = { hermes: 'Restart Hermes', app: 'Quit and reopen Hermes' }

/** `phase`: idle (the chip shows only when an update is ready), updating, review (Hermes wants a yes first),
 *  failed (nothing changed), partial (installed, but the hermretro profile or the page is not done: Finish update
 *  runs the rest), restart (installed, but something only a restart loads), done (just updated), current.
 *  `reload` is the banner's Reload, for files updated outside this page while Hermes runs the old code (status
 *  `restart_needed`): its phase is idle, reloading, restart (only a restart of Hermes, or of the app for the page's
 *  copy, loads it; `advice` says which) or failed.
 *  `installing`: the page's toolchain install is running. While it is, or while a chat in the hermretro profile is
 *  building (`blocked` says which), Update is refused: an update must never swap the plugin under a build. */
export function usePluginUpdate({ ctx, status, running, installing = false }) {
  const queryClient = useQueryClient()
  const installedIn = status.data?.plugin?.installed_in ?? null
  const profile = installedIn && !installedIn.linked ? (installedIn.profile ?? null) : null
  const check = useQuery({
    queryKey: [ID, 'plugin-update', profile],
    queryFn: async () => {
      const target = await installTarget(installedIn)

      return target ? { target, row: pluginRow(await requestOn(target, 'plugins.manage', { action: 'list' }, 60_000)) } : { target: null, row: null }
    },
    enabled: running && Boolean(profile),
    refetchInterval: CHECK_EVERY_MS,
    staleTime: CHECK_EVERY_MS / 2,
    refetchOnWindowFocus: false,
    retry: false
  })
  const [state, setState] = useState(() => {
    const marker = takeMarker(ctx)

    if (marker) {
      return { phase: marker.restart ? 'restart' : 'done', step: 0, announce: true, restartFor: 'hermes' }
    }

    const pending = pendingUpdate(ctx)

    return pending ? { phase: 'partial', step: 0, error: pending.error ?? null } : { phase: 'idle', step: 0 }
  })
  const [open, setOpen] = useState(false)
  const [reloadState, setReloadState] = useState({ phase: 'idle', error: null })
  const stale = Boolean(status.data?.restart_needed)
  const [dismissed, setDismissed] = useState(() => {
    try {
      return ctx.storage.get('updateLater', null)
    } catch {
      return null
    }
  })
  const busy = useRef(false)
  // The install's latest state, read by a running update before it reloads (an install started meanwhile is waited for).
  const installingNow = useRef(installing)

  installingNow.current = installing
  // The status says the hermretro profile was made: not finding it is then an error, never "there is none".
  const studioExists = Boolean(status.data?.profile?.is_studio || status.data?.profile?.studio?.exists)

  // The page that loads after an update says how it went, once.
  useEffect(() => {
    if (!state.announce) {
      return undefined
    }

    host.notify(
      state.phase === 'restart'
        ? { kind: 'warning', message: `hermretro was updated. ${RESTART_ADVICE.hermes} to finish loading it.` }
        : { kind: 'success', message: 'hermretro is up to date. Your games and chats are kept.' }
    )

    if (state.phase !== 'done') {
      return undefined
    }

    // ctx timers end with the plugin, so a page closed meanwhile leaves nothing behind.
    ctx.setTimeout?.(() => setState(current => (current.phase === 'done' ? { phase: 'idle', step: 0 } : current)), DONE_SHOWN_MS)

    return undefined
  }, [])

  const row = check.data?.row ?? null
  const target = check.data?.target ?? null
  const ready = row?.update_available === true && Boolean(target)
  const later = ready && dismissed && dismissed === (row.update_target ?? 'ready')
  const building = useQuery({
    queryKey: [ID, 'update-busy'],
    queryFn: async () => busyChats(await studioReloadTarget(studioExists)),
    enabled: running && ((ready && state.phase === 'idle') || state.phase === 'partial' || stale),
    refetchInterval: BUSY_EVERY_MS,
    retry: false
  })
  const fresher = state.raced && (building.dataUpdatedAt ?? 0) > state.racedAt
  const chats = (!fresher && state.raced) || (Array.isArray(building.data) ? building.data : [])

  useEffect(() => {
    if (fresher) {
      setState(current => ({ ...current, raced: undefined, racedAt: undefined }))
    }
  }, [fresher])
  const blockedFor = verb => (installing ? installingSentence(verb) : chats.length ? busySentence(chats, verb) : null)
  const blocked = blockedFor('update')

  const start = async (options = {}) => {
    if (busy.current || !target) {
      return
    }

    if (blocked) {
      setOpen(true)

      return
    }

    busy.current = true
    setUpdating(true)
    setOpen(true)
    setState({ phase: 'updating', step: 0 })

    const resume = Boolean(pendingUpdate(ctx))
    let outcome

    try {
      let studio = null

      try {
        studio = await studioReloadTarget(studioExists)
      } catch (error) {
        outcome = { kind: 'failed', error: `Could not reach the hermretro profile (${String(error?.message ?? error)})` }
      }

      outcome ??= await runUpdate({
        install: target,
        studio,
        options,
        resume,
        busy: () => (installingNow.current ? Promise.resolve(['the game tools install']) : busyChats(studio)),
        onStep: step => setState(current => ({ ...current, step })),
        onWaiting: waiting => setState(current => ({ ...current, waiting })),
        installed: () => remember(ctx, PENDING, { at: Date.now(), error: null }),
        refused: () => remember(ctx, PENDING, null),
        remember: marker => {
          remember(ctx, PENDING, null)
          remember(ctx, UPDATE_MARKER, marker)
        }
      })
    } finally {
      busy.current = false
      setUpdating(false)
    }

    void queryClient.invalidateQueries({ queryKey: [ID] })
    // Installed but not finished (now or by an earlier run): what is left is shown as a half-done update, never as
    // "nothing was changed".
    const half = outcome.kind === 'partial' || (pendingUpdate(ctx) && ['failed', 'blocked'].includes(outcome.kind))

    if (half) {
      remember(ctx, PENDING, { at: Date.now(), error: outcome.error ?? null })
      setState({ phase: 'partial', step: 0, error: outcome.error ?? null })
    } else if (outcome.kind === 'updated') {
      // The app reloads this page with its new copy; until then (or when it cannot), say where things stand.
      setState({ phase: outcome.restart || !outcome.pageRefreshed ? 'restart' : 'done', step: 2, restartFor: outcome.restart ? 'hermes' : 'app' })
    } else if (outcome.kind === 'current') {
      setState({ phase: 'idle', step: 0 })
      setOpen(false)
      host.notify({ kind: 'success', message: 'hermretro is already up to date.' })
    } else if (outcome.kind === 'busy') {
      // A build started after the last check: say so until the next check answers (it then says the same, or not).
      setState(current => ({
        phase: resume ? 'partial' : 'idle',
        step: 0,
        error: resume ? (current.error ?? null) : null,
        raced: outcome.chats,
        racedAt: building.dataUpdatedAt ?? 0
      }))
    } else if (outcome.kind === 'review') {
      setState({ phase: 'review', step: 0, review: outcome })
    } else {
      setState({ phase: 'failed', step: 0, error: outcome.error })
    }
  }

  // The banner's Reload: what is on disk loaded into the profile that runs hermretro for the page (the hermretro
  // profile, else the one that answered status), with the same lock and build checks as an update.
  const reload = async () => {
    if (busy.current || blockedFor('reload')) {
      return
    }

    busy.current = true
    setUpdating(true)
    setReloadState({ phase: 'reloading', error: null })

    let outcome

    try {
      let studio = null

      try {
        studio = (await studioReloadTarget(studioExists)) ?? { route: routing.route ?? null, profile: routing.profile ?? null }
      } catch (error) {
        outcome = { kind: 'failed', error: `Could not reach the hermretro profile (${String(error?.message ?? error)})` }
      }

      const install = await installTarget(installedIn)

      // Installed into another profile than hermretro: its settings come from there, so that profile must be reached.
      if (!outcome && !install && profile && profile !== STUDIO_PROFILE) {
        outcome = { kind: 'failed', error: `Could not reach the ${profile} profile, where hermretro is installed` }
      }

      outcome ??= await runReload({
        install,
        studio,
        busy: () => (installingNow.current ? Promise.resolve(['the game tools install']) : busyChats(studio))
      })
    } finally {
      busy.current = false
      setUpdating(false)
    }

    setReloadState(
      outcome.kind === 'failed'
        ? { phase: 'failed', error: outcome.error }
        : outcome.kind === 'restart'
          ? { phase: 'restart', error: null, restartFor: 'hermes' }
          : outcome.kind === 'reloaded' && !outcome.pageRefreshed
            ? { phase: 'restart', error: null, restartFor: 'app' }
            : { phase: 'idle', error: null }
    )
    void queryClient.invalidateQueries({ queryKey: [ID] })
  }

  const phase = state.phase
  const visible = phase !== 'idle' || (ready && !later)

  return {
    visible,
    ready,
    // Hermes answered for this install (so "up to date" can be said), and whether it is a linked checkout
    checked: Boolean(row),
    linked: Boolean(installedIn?.linked),
    phase,
    step: state.step,
    // why Update is refused right now (a build under way, the toolchain installing), or null
    blocked,
    // the chats a running update waits for before it reloads the hermretro profile, or null
    waiting: state.waiting ?? null,
    error: state.error ?? null,
    review: state.review ?? null,
    version: status.data?.plugin?.version ?? null,
    // what the 'restart' phase asks the user to do
    restartAdvice: RESTART_ADVICE[state.restartFor] ?? RESTART_ADVICE.hermes,
    // Hermes runs older code than is on disk (status restart_needed), and the banner's Reload
    stale,
    reload: { ...reloadState, advice: RESTART_ADVICE[reloadState.restartFor] ?? RESTART_ADVICE.hermes, blocked: blockedFor('reload'), start: () => void reload() },
    open,
    setOpen,
    start: () => void start(),
    agree: () => void start(state.review?.retry ?? {}),
    cancel: () => {
      setState({ phase: 'idle', step: 0 })
      setOpen(false)
    },
    later: () => {
      const key = row?.update_target ?? 'ready'

      setDismissed(key)
      remember(ctx, 'updateLater', key)
      setOpen(false)
    },
    whatsNew: () => void ctx.os?.openExternal?.(LINKS.releases),
    openPlugins: () => host.navigate(PLUGINS_HREF)
  }
}
