import { useEffect, useQuery, useState } from '#sdk'
import { callStudio } from '#app/backend.js'
import { ID } from '#app/ids.js'
import { readGameBuildStatus } from '#app/player/build-status.js'

/** The shell owns the active selection across remounts. Storage remembers it for the next visit. */
export function useBuildSelection(ctx, selection, select) {
  const [remembered] = useState(() => {
    if (selection !== null) {
      return selection
    }
    try {
      return ctx.storage.get('buildSelected', 'new') || 'new'
    } catch {
      return 'new'
    }
  })
  const selected = selection ?? remembered

  useEffect(() => {
    if (selection === null) {
      select(selected)
      return
    }
    try {
      ctx.storage.set('buildSelected', selection)
    } catch {
      // This visit only.
    }
  }, [ctx, select, selected, selection])

  return selected
}

/** Older shelves omit unreadable games without identifying them. Confirm removal separately. */
export function useMissingBuildGame(id, unavailable) {
  const hasMembership = Array.isArray(unavailable)
  const status = useQuery({
    queryKey: [ID, 'buildSelectionStatus', id],
    queryFn: () => readGameBuildStatus(callStudio, id),
    enabled: Boolean(id) && !hasMembership,
    retry: false
  })

  if (!id) {
    return { removed: false, error: null }
  }

  const removed = hasMembership ? !unavailable.includes(id) : status.data?.code === 'NO_GAME' && !status.isError && !status.isFetching
  const settled = hasMembership || status.isError || Boolean(status.data) && !status.isFetching

  return { removed, error: settled && !removed ? 'Could not read the selected game.' : null }
}
