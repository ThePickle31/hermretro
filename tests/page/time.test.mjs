// A plain page helper's test, the recipe in docs/dev/TESTING.md: page/shared/ui/time.js's clock() and spanWords().
// Run alone: node tests/page/time.test.mjs
import assert from 'node:assert/strict'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

// The page's aliases (#shared/, #sdk…) resolve only after this; then import() the module.
registerAliases()

const { clock, spanWords } = await import('#shared/ui/time.js')

test('clock() is minutes:seconds, never negative, minutes past an hour kept', () => {
  assert.equal(clock(0), '0:00')
  assert.equal(clock(-5000), '0:00')
  assert.equal(clock(65_999), '1:05', 'a part second is dropped')
  assert.equal(clock(62 * 60_000 + 5000), '62:05')
})

test('spanWords() says seconds, then minutes and padded seconds, then hours and minutes', () => {
  assert.equal(spanWords(0), '0s')
  assert.equal(spanWords(59_400), '59s')
  assert.equal(spanWords(59_600), '1m 00s', 'rounded to the nearest second')
  assert.equal(spanWords(125_000), '2m 05s')
  assert.equal(spanWords(65 * 60_000), '1h 5m', 'minutes are not padded after hours')
  assert.equal(spanWords(60 * 60_000), '1h 0m')
})
