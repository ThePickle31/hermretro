// A plain page helper's test (.agents/skills/hermretro-dev-testing/references/testing.md): every helper in page/app/format.js, formatBytes() (the page's one
// bytes formatter) and shortPath() (the last folders of a long path).
import assert from 'node:assert/strict'
import { registerAliases } from './aliases.mjs'
import test from 'node:test'

registerAliases()

const { formatBytes, shortPath } = await import('#app/format.js')

test('formatBytes() picks GB or MB by default, with one decimal below 100 MB and above 1000 MB', () => {
  assert.equal(formatBytes(18_100_000), '18.1 MB')
  assert.equal(formatBytes(551_000_000), '551 MB')
  assert.equal(formatBytes(2_300_000_000), '2.3 GB')
  assert.equal(formatBytes(708_000_000, { approx: true }), '≈ 708 MB')
})

test('formatBytes() answers nothing for what is not a size', () => {
  assert.equal(formatBytes(-1), '')
  assert.equal(formatBytes(undefined), '')
  assert.equal(formatBytes(Number.NaN), '')
})

test("formatBytes() unit 'MB' is whole megabytes with separators, 'KB' whole KiB and at least 1", () => {
  assert.equal(formatBytes(2_400_000_000, { unit: 'MB' }), `${(2400).toLocaleString()} MB`)
  assert.equal(formatBytes(undefined, { unit: 'MB' }), '0 MB', 'the removed size may be missing')
  assert.equal(formatBytes(262_144, { unit: 'KB' }), '256 KB')
  assert.equal(formatBytes(10, { unit: 'KB' }), '1 KB')
})

test('shortPath() keeps the last 4 folders behind …/ by default, and the keep you ask for', () => {
  assert.equal(shortPath('/home/u/.hermes/hermretro/games/pong/build'), '…/hermretro/games/pong/build')
  assert.equal(shortPath('/a/b/c/d/e', 2), '…/d/e')
  assert.equal(shortPath('C:\\x\\a\\b\\c\\d'), '…/a/b/c/d')
})

test('shortPath() leaves a short path as it is and answers null for none', () => {
  assert.equal(shortPath('/a/b/c/d'), '/a/b/c/d')
  assert.equal(shortPath('games/pong'), 'games/pong')
  assert.equal(shortPath(null), null)
  assert.equal(shortPath(''), null)
})
