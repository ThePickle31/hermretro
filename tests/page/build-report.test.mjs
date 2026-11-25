// The build card's reading of a `chromatic_build_report` (page/pages/build/chat/report.js).
import assert from 'node:assert/strict'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

registerAliases()

const { normalizeReport } = await import('#pages/build/chat/report.js')

test('test-plan checks join the tested lines when they passed and the untested ones otherwise', () => {
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
      { id: 'T4', text: 'Odd result', result: 'maybe' },
      { id: '', text: 'No id', result: 'passed' },
      'T5'
    ],
    difficulty: '  Finished in one run; the last room took 3 tries. '
  })

  assert.deepEqual(report.tested, ['Hop around', 'T1 · Title shows'])
  assert.deepEqual(report.untested, ['Sound', 'T2 · Gate stays shut (failed)', 'T3 · One run to the ending', 'AUD1 · Seed chime (needs review)', 'T4 · Odd result'])
  assert.equal(report.difficulty, 'Finished in one run; the last room took 3 tries.')
})

test('a report without checks or difficulty keeps its own lines', () => {
  const report = normalizeReport({ title: 'Robin', summary: 'It flies.', tested: ['Flap'] })

  assert.deepEqual([report.tested, report.untested, report.difficulty], [['Flap'], [], null])
})
