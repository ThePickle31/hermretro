// The play-test checklist ("Try this") for one build. Items come from the build report: what
// HermRetro play-tested (worth trying yourself) and what it did not test (worth trying first). Ticks
// are the user's own and are kept per game and build. A check the user reported as wrong comes back
// on the next build as "fixed, check it again" until it is ticked. Pure; no React, no storage.

/** Builds kept per game; older ticks are dropped. */
const KEPT_BUILDS = 12

const keyOf = text => String(text).trim().toLowerCase()

/** The report's checks, untested first. */
function reportChecks(report) {
  const untested = (report?.untested ?? []).map(text => ({ key: keyOf(text), text, untested: true }))
  const tested = (report?.tested ?? []).map(text => ({ key: keyOf(text), text, untested: false }))
  const seen = new Set()

  return [...untested, ...tested].filter(item => item.key && !seen.has(item.key) && seen.add(item.key))
}

/** One build's saved state: { ticks: {key: true}, reported: {key: text} }. */
const emptyBuild = () => ({ ticks: {}, reported: {} })

/**
 * The list shown for build `n` of a game, given everything saved for that game
 * (`saved = { [n]: { ticks, reported } }`): checks reported wrong on an earlier build and not yet
 * ticked since come first as `fixed`, then this build's report.
 * Each item: { key, text, state: 'todo' | 'untested' | 'done' | 'reported' | 'fixed', from? }.
 */
export function checklist(report, n, saved = {}) {
  const own = saved[n] ?? emptyBuild()
  const items = []
  const keys = new Set()

  for (const [from, entry] of Object.entries(saved)) {
    if (Number(from) >= n) {
      continue
    }

    for (const [key, text] of Object.entries(entry.reported ?? {})) {
      // Ticked after the report (on that build or a later one) and before this one: settled. Ticked on
      // this one: shown done.
      const settled = Object.entries(saved).some(([later, value]) => Number(later) >= Number(from) && Number(later) < n && value.ticks?.[key])

      if (!settled && !keys.has(key)) {
        keys.add(key)
        items.push({ key, text, state: own.ticks[key] ? 'done' : 'fixed', from: Number(from) })
      }
    }
  }

  for (const check of reportChecks(report)) {
    if (keys.has(check.key)) {
      continue
    }

    keys.add(check.key)

    const state = own.ticks[check.key] ? 'done' : own.reported[check.key] ? 'reported' : check.untested ? 'untested' : 'todo'

    items.push({ key: check.key, text: check.text, state })
  }

  return items
}

/** Saved state after ticking (or unticking) `key` on build `n`. */
export function withTick(saved, n, key, ticked) {
  const own = saved[n] ?? emptyBuild()
  const ticks = { ...own.ticks }

  if (ticked) {
    ticks[key] = true
  } else {
    delete ticks[key]
  }

  return trim({ ...saved, [n]: { ...own, ticks } })
}

/** Saved state after reporting `key` (with its words) as wrong on build `n`. */
export function withReport(saved, n, key, text) {
  const own = saved[n] ?? emptyBuild()
  const ticks = { ...own.ticks }

  delete ticks[key]

  return trim({ ...saved, [n]: { ticks, reported: { ...own.reported, [key]: text } } })
}

function trim(saved) {
  const builds = Object.keys(saved)
    .map(Number)
    .sort((a, b) => b - a)

  return Object.fromEntries(builds.slice(0, KEPT_BUILDS).map(n => [n, saved[n]]))
}

/** Counts for the panel's heading and the folded tab: `left` still to try (a reported check waits for
 *  the fix, so it is neither done nor left); `complete` when every check is ticked. */
export function progress(items) {
  const done = items.filter(item => item.state === 'done').length
  const left = items.filter(item => item.state !== 'done' && item.state !== 'reported').length

  return { done, total: items.length, left, complete: items.length > 0 && done === items.length }
}
