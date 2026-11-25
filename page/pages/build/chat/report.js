// The build report (`chromatic_build_report`).
import { REPORT_TOOL } from '#app/tools.js'

const REPORT_KINDS = new Set(['added', 'changed', 'removed'])
const CHECK_RESULTS = new Set(['passed', 'failed', 'not run', 'blocked', 'needs review'])

/** The build card a turn reported (`chromatic_build_report` arguments or its result's `report`), trimmed
 *  to what the card shows; null when it has no title or summary. Test-plan checks join the tested lines when
 *  they passed and the untested ones otherwise, with their result unless it is "not run". */
export function normalizeReport(value) {
  if (!value || typeof value !== 'object') {
    return null
  }

  const line = (text, max) => (typeof text === 'string' && text.trim() ? text.trim().slice(0, max) : null)
  const lines = (list, count, max) => (Array.isArray(list) ? list.map(item => line(item, max)).filter(Boolean).slice(0, count) : [])
  const title = line(value.title, 60)
  const summary = line(value.summary, 400)

  if (!title && !summary) {
    return null
  }

  const checks = (Array.isArray(value.checks) ? value.checks : [])
    .map(check => ({ id: line(check?.id, 8), text: line(check?.text, 100), result: CHECK_RESULTS.has(check?.result) ? check.result : 'not run' }))
    .filter(check => check.id && check.text)
    .slice(0, 30)
  const checkLines = passed => checks
    .filter(check => (check.result === 'passed') === passed)
    .map(check => `${check.id} \u00B7 ${check.text}${passed || check.result === 'not run' ? '' : ` (${check.result})`}`)

  return {
    title,
    summary,
    changes: (Array.isArray(value.changes) ? value.changes : [])
      .map(change => ({
        kind: REPORT_KINDS.has(change?.kind) ? change.kind : 'changed',
        text: line(change?.text, 140),
        asset: line(change?.asset, 4096)
      }))
      .filter(change => change.text)
      .slice(0, 8),
    tested: [...lines(value.tested, 6, 100), ...checkLines(true)],
    untested: [...lines(value.untested, 6, 100), ...checkLines(false)],
    difficulty: line(value.difficulty, 240),
    notes: lines(value.notes, 3, 200),
    suggestions: lines(value.suggestions, 4, 60)
  }
}

export const reportOf = (name, args) => (String(name ?? '') === REPORT_TOOL ? normalizeReport(args) : null)
