// The play-test checklist of one build, with the user's ticks and reports kept in the page's storage
// per game (see checks.js for the rules).
import { useCallback, useMemo, useState } from '../sdk.js'
import { checklist, progress, withReport, withTick } from './checks.js'

const KEY = 'playtest'
// Games remembered; the one played longest ago is forgotten first (a removed game's ticks go too).
const KEPT_GAMES = 40

const readAll = ctx => {
  const value = ctx.storage.get(KEY, null)

  return value && typeof value === 'object' ? value : {}
}

/** { items, counts, tick(key, on), report(key, text) } for build `n` of `gameId`. */
export function usePlaytest(ctx, gameId, n, report) {
  const [saved, setSaved] = useState(() => readAll(ctx)[gameId] ?? {})

  // Storage is the source of truth (the same game may be open in another surface): change what it holds,
  // write it back with this game last, so the games played longest ago are the ones dropped, then show it.
  const write = useCallback(
    change => {
      const all = readAll(ctx)
      const next = change(all[gameId] ?? {})
      const others = Object.entries(all).filter(([id]) => id !== gameId)

      ctx.storage.set(KEY, Object.fromEntries([...others.slice(-(KEPT_GAMES - 1)), [gameId, next]]))
      setSaved(next)
    },
    [gameId]
  )

  const items = useMemo(() => (n ? checklist(report, n, saved) : []), [report, n, saved])

  return {
    items,
    counts: progress(items),
    tick: useCallback((key, on) => write(current => withTick(current, n, key, on)), [write, n]),
    report: useCallback((key, text) => write(current => withReport(current, n, key, text)), [write, n])
  }
}
