// The build card's reading of a `chromatic_build_report` (page/pages/build/chat/report.js).
import assert from 'node:assert/strict'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

registerAliases()

const { normalizeReport, reportLines } = await import('#pages/build/chat/report.js')

test('test-plan checks stay structured; the card lists passed, failed and untested ones apart', () => {
  const report = normalizeReport({
    title: 'Seeds and gates',
    summary: 'The gate opens with three seeds.',
    tested: ['Hop around'],
    untested: ['Sound'],
    checks: [
      { id: 'T1', text: 'Title shows', result: 'passed' },
      { id: 'T2', text: 'Gate stays shut', result: 'failed' },
      { id: 'T3', text: 'One run to the ending', result: 'not run' },
      { id: 'AUD1', text: 'Seed chime', result: 'needs review' },
      { id: 'GATE-12B', text: 'Gate key', result: 'blocked' },
      { id: 'T4', text: 'Odd result', result: 'maybe' },
      { id: '', text: 'No id', result: 'passed' },
      'T5'
    ],
    difficulty: '  Finished in one run; the last room took 3 tries. '
  })

  assert.deepEqual([report.tested, report.untested], [['Hop around'], ['Sound']])
  assert.deepEqual(report.checks.map(check => [check.id, check.result]), [['T1', 'passed'], ['T2', 'failed'], ['T3', 'not run'], ['AUD1', 'needs review'], ['GATE-12B', 'blocked'], ['T4', 'not run']])
  assert.deepEqual(reportLines(report), {
    tested: ['Hop around', 'T1 · Title shows'],
    failed: ['T2 · Gate stays shut'],
    untested: ['Sound', 'T3 · One run to the ending', 'AUD1 · Seed chime (needs review)', 'GATE-12B · Gate key (blocked)', 'T4 · Odd result']
  })
  assert.equal(report.difficulty, 'Finished in one run; the last room took 3 tries.')
})

test('a report holds as many checks as the backend allows', () => {
  const checks = Array.from({ length: 120 }, (_, index) => ({ id: `T${index + 1}`, text: 'Step', result: 'passed' }))

  assert.equal(normalizeReport({ title: 'Long', summary: 'Many checks.', checks }).checks.length, 100)
})

test('a report without checks or difficulty keeps its own lines', () => {
  const report = normalizeReport({ title: 'Robin', summary: 'It flies.', tested: ['Flap'] })

  assert.deepEqual([report.tested, report.untested, report.checks, report.difficulty], [['Flap'], [], [], null])
  assert.deepEqual(reportLines(report), { tested: ['Flap'], failed: [], untested: [] })
})
