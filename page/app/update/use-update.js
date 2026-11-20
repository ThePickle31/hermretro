// The update state every page shares (shell.pluginUpdate): whether Hermes found a newer hermretro, the Update
// button's progress, and how the last update went (told by the page that loads after it).
import { host, useEffect, useQuery, useQueryClient, useRef, useState } from '#sdk'
import { LINKS } from '#shared/ui/links.js'
import { ID, PLUGINS_HREF } from '#app/ids.js'
import { installTarget, pluginRow, requestOn, runUpdate, studioReloadTarget, UPDATE_MARKER } from './flow.js'

// Hermes checks for plugin updates about once a day; reading its answer is cheap but not free (every plugin's row).
const CHECK_EVERY_MS = 30 * 60_000
// A marker older than this is from an update whose page never came back: not worth announcing.
const MARKER_FRESH_MS = 15 * 60_000
const DONE_SHOWN_MS = 10_000

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
 *  failed, restart (installed, but something only a restart loads), done (just updated), current. */
export function usePluginUpdate({ ctx, status, running }) {
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

    return marker ? { phase: marker.restart ? 'restart' : 'done', step: 0, announce: true } : { phase: 'idle', step: 0 }
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

  const start = async (options = {}) => {
    if (busy.current || !target) {
      return
    }

    busy.current = true
    setOpen(true)
    setState({ phase: 'updating', step: 0 })

    const outcome = await runUpdate({
      install: target,
      studio: await studioReloadTarget(),
      options,
      onStep: step => setState(current => ({ ...current, step })),
      remember: marker => remember(ctx, UPDATE_MARKER, marker)
    })

    busy.current = false
    void queryClient.invalidateQueries({ queryKey: [ID] })

    if (outcome.kind === 'updated') {
      // The app reloads this page with its new copy; until then (or when it cannot), say where things stand.
      setState({ phase: outcome.restart || !outcome.pageRefreshed ? 'restart' : 'done', step: 2 })
    } else if (outcome.kind === 'current') {
      setState({ phase: 'idle', step: 0 })
      setOpen(false)
      host.notify({ kind: 'success', message: 'hermretro is already up to date.' })
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
