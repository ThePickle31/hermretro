// The page tests' text assertions (harness.mjs): a failure shows the part of the page near the closest match.
//   node --test tests/page/harness-text.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'

import { assertHides, assertShows, nearest } from './harness.mjs'

const page = 'x'.repeat(50_000) + ' Node.js 26.13.0 (from Hermes) ' + 'y'.repeat(50_000)

test('the closest match is the longest leading part of a string or a RegExp the page has', () => {
  assert.deepEqual(nearest(page, 'Node.js 26.13.0 (from Python)'), { at: 50_001, matched: 'Node.js 26.13.0 (from ' })
  assert.equal(nearest(page, /Node\.js 26\.13\.0 \(from Python\)/).matched, 'Node.js 26.13.0 (from ')
  assert.equal(nearest(page, 'Nothing like it').matched, '')
})

test('a failure shows about 300 characters around the closest match, not the whole page', () => {
  const failure = (fn) => { try { fn() } catch (error) { return error.message } assert.fail('it passed') }
  for (const message of [
    failure(() => assertShows(page, /from Python/, 'the source')),
    failure(() => assertShows(page, 'Nothing like it')),
    failure(() => assertHides(page, 'from Hermes'))
  ]) {
    assert.ok(message.length < 500, `${message.length} chars`)
  }
  assert.match(failure(() => assertShows(page, /from Python/, 'the source')), /^the source: .*closest: "from " at 50018[^]*\(from Hermes\)/)
})

test('a passing assertion says nothing', () => {
  assertShows(page, /from Hermes/)
  assertShows(page, 'Node.js 26.13.0')
  assertHides(page, 'from Python')
  assertHides(page, /Step \d of/)
})
