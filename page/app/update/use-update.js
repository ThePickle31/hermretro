// The update state every page shares (shell.pluginUpdate): whether Hermes found a newer hermretro, the Update
// button's progress, and how the last update went (told by the page that loads after it).
import { host, useEffect, useQuery, useQueryClient, useRef, useState } from '#sdk'
import { LINKS } from '#shared/ui/links.js'
import { ID, PLUGINS_HREF } from '#app/ids.js'
import { busyChats, busySentence, installTarget, pluginRow, requestOn, runUpdate, studioReloadTarget, UPDATE_MARKER } from './flow.js'
import { setUpdating } from './lock.js'

// Hermes checks for plugin updates about once a day; reading its answer is cheap but not free (every plugin's row).
const CHECK_EVERY_MS = 30 * 60_000
// A marker older than this is from an update whose page never came back: not worth announcing.
const MARKER_FRESH_MS = 15 * 60_000
const DONE_SHOWN_MS = 10_000
// While an update is ready, how often the hermretro profile's chats are checked for a build under way.
const BUSY_EVERY_MS = 5_000
const INSTALLING = 'The game tools are being installed. You can update when that finishes.'
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

/** `phase`: idle (the chip shows only when an update is ready), updating, review (Hermes wants a yes first),
 *  failed (nothing changed), partial (installed, but the hermretro profile or the page is not done: Finish update
 *  runs the rest), restart (installed, but something only a restart loads), done (just updated), current.
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
      return { phase: marker.restart ? 'restart' : 'done', step: 0, announce: true }
    }

    const pending = pendingUpdate(ctx)

    return pending ? { phase: 'partial', step: 0, error: pending.error ?? null } : { phase: 'idle', step: 0 }
  })
  const [open, setOpen] = useState(false)
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
        ? { kind: 'warning', message: 'hermretro was updated. Quit and reopen Hermes to finish loading it.' }
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
    enabled: running && ((ready && state.phase === 'idle') || state.phase === 'partial'),
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
  const blocked = installing ? INSTALLING : chats.length ? busySentence(chats) : null

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
      setState({ phase: outcome.restart || !outcome.pageRefreshed ? 'restart' : 'done', step: 2 })
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
