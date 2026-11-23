import { useEffect, useState } from '#sdk'

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
