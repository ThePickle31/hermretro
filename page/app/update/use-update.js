// The update state every page shares (shell.pluginUpdate): whether a newer hermretro is out and what it changes, the
// corner card that says so once per version, the dialog's progress, and how the last update went (told by the page
// that loads after it). An update made outside this page (a terminal, Capabilities > Plugins) is loaded by itself.
import { host, useEffect, useQuery, useQueryClient, useRef, useState } from '#sdk'
import { LINKS } from '#shared/ui/links.js'
import { callBackend } from '#app/backend.js'
import { ID, PLUGINS_HREF, STUDIO_PROFILE } from '#app/ids.js'
import { RPC_RELEASES } from '#app/rpc.js'
import { routing } from '#app/routing.js'
import { busyChats, busySentence, installTarget, pluginRow, requestOn, runReload, runUpdate, studioReloadTarget, UPDATE_MARKER } from './flow.js'
import { setUpdating } from './lock.js'
import { releasesBetween } from './versions.js'

// Hermes checks for plugin updates about once a day; reading its answer is cheap but not free (every plugin's row).
// The releases (and their notes) are read from GitHub on the same clock.
const CHECK_EVERY_MS = 30 * 60_000
// A marker older than this is from an update whose page never came back: not worth announcing.
const MARKER_FRESH_MS = 15 * 60_000
// While an update is ready, how often the hermretro profile's chats are checked for a build under way.
const BUSY_EVERY_MS = 5_000
const installingSentence = verb => `The game tools are being installed. You can ${verb} when that finishes.`
// The new version whose corner card was put away (Later, or a click beside it): `{ version, target }`, the release and
// Hermes's update target it was known by; the card does not come back for either.
const SEEN = 'updateLater'
// Hermes installed the new version but the rest (the hermretro profile, the page) did not finish: { at, error }. Kept
// until a run finishes, so Finish update resumes it even though Hermes now answers "unchanged".
const PENDING = 'updatePending'

function stored(ctx, key) {
  try {
    return ctx.storage.get(key, null)
  } catch {
    return null
  }
}

function pendingUpdate(ctx) {
  const pending = stored(ctx, PENDING)

  return pending && typeof pending === 'object' ? pending : null
}

function takeMarker(ctx) {
  const marker = stored(ctx, UPDATE_MARKER)

  if (marker) {
    remember(ctx, UPDATE_MARKER, null)
  }

  return marker && Date.now() - Number(marker.at ?? 0) < MARKER_FRESH_MS ? marker : null
}

function remember(ctx, key, value) {
  try {
    ctx.storage.set(key, value)
  } catch {
    // for this visit only
  }
}

/** What waits for the user's Update once they asked: a build, or the toolchain install. */
function queuedSentence(chats, installing) {
  if (installing) {
    return 'The game tools are being installed. The update starts as soon as that finishes.'
  }

  return chats.length === 1
    ? `"${chats[0]}" is building. The update starts as soon as it finishes.`
    : `Games are being built in ${chats.length} chats. The update starts as soon as they finish.`
}

/** What a 'restart' phase asks for: the Hermes gateway did not load the new code, or only the page's copy is old
 *  (the app reloads it when reopened). */
const RESTART_ADVICE = { hermes: 'Restart Hermes', app: 'Quit and reopen Hermes' }

/** `phase`: idle (the chip shows only when an update is ready), updating, review (Hermes wants a yes first),
 *  failed (nothing changed), partial (installed, but the hermretro profile or the page is not done: Finish update
 *  runs the rest), restart (installed, but something only a restart loads), done (just updated).
 *  `installing`: the page's toolchain install is running. While it is, or while a chat in the hermretro profile is
 *  building (`blocked` says which), an update waits (`queued`): it must never swap the plugin under a build. */
export function usePluginUpdate({ ctx, status, running, installing = false, installError = null, confirmInstallIdle }) {
  const queryClient = useQueryClient()
  const installedIn = status.data?.plugin?.installed_in ?? null
  const profile = installedIn && !installedIn.linked ? (installedIn.profile ?? null) : null
  const version = status.data?.plugin?.version ?? null
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
  const releases = useQuery({
    queryKey: [ID, 'releases'],
    queryFn: async () => (await callBackend(RPC_RELEASES, {}, 30_000)).data,
    enabled: running && Boolean(profile),
    refetchInterval: CHECK_EVERY_MS,
    staleTime: CHECK_EVERY_MS / 2,
    refetchOnWindowFocus: false,
    retry: false
  })
  const [state, setState] = useState(() => {
    const marker = takeMarker(ctx)

    if (marker) {
      return { phase: marker.restart ? 'restart' : 'done', step: 0, announce: Boolean(marker.restart), restartFor: 'hermes', from: marker.from ?? null }
    }

    const pending = pendingUpdate(ctx)

    return pending ? { phase: 'partial', step: 0, error: pending.error ?? null } : { phase: 'idle', step: 0 }
  })
  // The page that loads after an update opens the dialog on how it went.
  const [open, setOpen] = useState(() => state.phase === 'done')
  const [seen, setSeen] = useState(() => stored(ctx, SEEN))
  const stale = Boolean(status.data?.restart_needed)
  const busy = useRef(false)
  // The outside update this page is loading or loaded (`tried`), and the busy check a build refused it after (`after`):
  // it is tried again only on a newer idle answer, never in a loop.
  const auto = useRef({ tried: false, after: -1 })
  // The status says the hermretro profile was made: not finding it is then an error, never "there is none".
  const studioExists = Boolean(status.data?.profile?.is_studio || status.data?.profile?.studio?.exists)

  useEffect(() => {
    if (state.announce) {
      host.notify({ kind: 'warning', message: `hermretro was updated. ${RESTART_ADVICE.hermes} to finish loading it.` })
    }
  }, [])

  const row = check.data?.row ?? null
  const target = check.data?.target ?? null
  const published = releases.data?.ok ? releases.data.releases : []
  const notes = releasesBetween(published, version)
  const latest = notes[0]?.version ?? null
  // A published release counts only for an install Hermes would update (not one pinned to a commit).
  const ready = Boolean(target) && (row?.update_available === true || (notes.length > 0 && Boolean(row) && !row.pinned_sha))
  const updateTarget = row?.update_target ?? null
  const putAway = Boolean(seen && ((latest && seen.version === latest) || (updateTarget && seen.target === updateTarget) || (!latest && !updateTarget && seen.version === null)))
  // Files on disk newer than what Hermes runs, in a copy Hermes installed (a linked checkout has the dev loop).
  const outside = running && stale && Boolean(installedIn) && !installedIn.linked
  const building = useQuery({
    queryKey: [ID, 'update-busy'],
    queryFn: async () => busyChats(await studioReloadTarget(studioExists)),
    enabled: running && ((ready && state.phase === 'idle') || state.phase === 'partial' || outside),
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
  const blockedFor = verb => (installing ? installingSentence(verb) : installError || (chats.length ? busySentence(chats, verb) : null))
  const blocked = blockedFor('update')

  const later = () => {
    const value = { version: latest, target: updateTarget }

    setSeen(value)
    remember(ctx, SEEN, value)
  }

  const start = async (options = {}) => {
    if (busy.current || !target) {
      return
    }

    setOpen(true)

    if (blocked) {
      // A build or the toolchain install finishes by itself: the update waits for it. An install error does not.
      if (!installError) {
        setState(current => ({ ...current, queued: options }))
      }

      return
    }

    busy.current = true
    setUpdating(true)
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
        busy: () => busyChats(studio),
        confirmInstallIdle,
        onStep: step => setState(current => ({ ...current, step })),
        onWaiting: waiting => setState(current => ({ ...current, waiting })),
        installed: () => remember(ctx, PENDING, { at: Date.now(), error: null }),
        refused: () => remember(ctx, PENDING, null),
        remember: marker => {
          remember(ctx, PENDING, null)
          remember(ctx, UPDATE_MARKER, { ...marker, from: version })
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
      setState({ phase: outcome.restart || !outcome.pageRefreshed ? 'restart' : 'done', step: 2, restartFor: outcome.restart ? 'hermes' : 'app', from: version })
    } else if (outcome.kind === 'current') {
      setState({ phase: 'idle', step: 0 })
      setOpen(false)
      later()
      host.notify({ kind: 'success', message: 'hermretro is already up to date.' })
    } else if (outcome.kind === 'busy') {
      // A build started after the last check: the update waits for it, said until the next check answers.
      setState(current => ({
        phase: resume ? 'partial' : 'idle',
        step: 0,
        error: resume ? (current.error ?? null) : null,
        queued: resume ? false : options,
        raced: outcome.chats,
        racedAt: building.dataUpdatedAt ?? 0
      }))
    } else if (outcome.kind === 'review') {
      setState({ phase: 'review', step: 0, review: outcome })
    } else {
      setState({ phase: 'failed', step: 0, error: outcome.error })
    }
  }

  // Load what is on disk into the profile that runs hermretro for the page (the hermretro profile, else the one that
  // answered status), with the same lock and build checks as an update: an update made outside this page.
  const reload = async () => {
    if (busy.current) {
      return
    }

    busy.current = true
    setUpdating(true)
    setState({ phase: 'updating', step: 1 })
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
        busy: () => busyChats(studio),
        confirmInstallIdle,
        // The app may reload this page before runReload answers.
        loadedNow: () => remember(ctx, UPDATE_MARKER, { result: 'updated', restart: false, at: Date.now(), from: version })
      })
    } finally {
      busy.current = false
      setUpdating(false)
    }

    if (outcome.kind !== 'reloaded' || !outcome.pageRefreshed) {
      remember(ctx, UPDATE_MARKER, null)
    }

    if (outcome.kind === 'busy') {
      // A build started meanwhile: tried again once a newer check says nothing is building.
      auto.current = { tried: false, after: Date.now() }
      setState({ phase: 'idle', step: 0 })
    } else if (outcome.kind === 'failed') {
      setState({ phase: 'partial', step: 0, error: outcome.error, reloadOnly: true })
    } else {
      setState({ phase: outcome.kind === 'reloaded' && outcome.pageRefreshed ? 'done' : 'restart', step: 2, restartFor: outcome.kind === 'restart' ? 'hermes' : 'app', from: version })
    }

    void queryClient.invalidateQueries({ queryKey: [ID] })
  }

  // An update made outside this page: loaded as soon as nothing is being built, once per update (a later one, after
  // Hermes caught up with the last, is loaded again). Not over an update of this page's own under way or asking.
  const canLoad =
    outside && ['idle', 'failed'].includes(state.phase) && Array.isArray(building.data) && (building.dataUpdatedAt ?? 0) > auto.current.after && !blockedFor('reload')

  useEffect(() => {
    if (!stale) {
      auto.current = { tried: false, after: -1 }
    }
  }, [stale])

  useEffect(() => {
    if (canLoad && !auto.current.tried && !busy.current) {
      auto.current = { ...auto.current, tried: true }
      void reload()
    }
  }, [canLoad])

  // The user asked to update while a build ran: it starts once nothing is.
  useEffect(() => {
    if (state.queued && state.phase === 'idle' && !blocked && !busy.current) {
      void start(state.queued)
    }
  }, [state.queued, state.phase, blocked])

  const phase = state.phase
  const finished = () => setState(current => (current.phase === 'done' ? { phase: 'idle', step: 0 } : current))

  return {
    visible: phase !== 'idle' || ready,
    ready,
    // the corner card: a new version the user has not put away yet
    card: ready && phase === 'idle' && !state.queued && !open && !putAway,
    // Hermes answered for this install (so "up to date" can be said), and whether it is a linked checkout
    checked: Boolean(row),
    linked: Boolean(installedIn?.linked),
    phase,
    step: state.step,
    // why Update waits or is refused right now (a build under way, the toolchain installing), or null
    blocked: state.queued && blocked && !installError ? queuedSentence(chats, installing) : blocked,
    // the user asked for the update; it starts once nothing is being built
    queued: Boolean(state.queued),
    // whether what blocks it finishes by itself, so Update may wait for it
    queueable: !installError,
    // the chats a running update waits for before it reloads the hermretro profile, or null
    waiting: state.waiting ?? null,
    error: state.error ?? null,
    review: state.review ?? null,
    version,
    // the newest published version and what every release newer than the installed one changed (newest first)
    latest,
    notes,
    // what the releases this update brought changed (the dialog after it)
    installedNotes: state.from ? releasesBetween(published, state.from, version) : published.filter(release => release.version === version),
    // what the 'restart' phase asks the user to do
    restartAdvice: RESTART_ADVICE[state.restartFor] ?? RESTART_ADVICE.hermes,
    open,
    setOpen: value => {
      setOpen(value)

      if (!value) {
        finished()
      }
    },
    start: () => void start(),
    // Finish update: the rest of a half-done update, or the load of an outside one again
    finish: () => void (state.reloadOnly ? reload() : start()),
    agree: () => void start(state.review?.retry ?? {}),
    cancel: () => {
      setState({ phase: 'idle', step: 0 })
      setOpen(false)
    },
    later,
    whatsNew: () => void ctx.os?.openExternal?.(LINKS.releases),
    openPlugins: () => host.navigate(PLUGINS_HREF)
  }
}
