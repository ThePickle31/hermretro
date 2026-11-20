// The New Game shelf's order and fit (page/pages/build/cart-shelf.js), and the flat ground the level keeps under it
// (page/pages/build/attract/level.js), without a browser.
// Run alone: node tests/page/cart-shelf.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'
import { registerAliases } from './aliases.mjs'

registerAliases()
const { shelfFit, shelfOrder } = await import('../../page/pages/build/cart-shelf.js')
const { World } = await import('../../page/pages/build/attract/world.js')
const { T } = await import('../../page/pages/build/attract/physics.js')

const game = (key, updatedAt, state = null) => ({ key, title: key, game: { id: key, updatedAt }, state })

test('newest work first: waiting for an answer, then games being set up, then by last change or last reply', () => {
  const entries = [
    game('old', 100),
    game('new', 300),
    { key: 'pending:s1', title: 'New game', game: null, pending: { storedId: 's1' }, state: null },
    game('replied', 50, { last: 400 * 1000 }),
    game('waiting', 10, { waiting: true })
  ]
  assert.deepEqual(shelfOrder(entries).map(entry => entry.key), ['waiting', 'pending:s1', 'replied', 'new', 'old'])
})

test('as many cartridges as fit, keeping a place for All games when anything is left over', () => {
  assert.equal(shelfFit(630, 4, false), 4, 'four fit in five places')
  assert.equal(shelfFit(630, 4, true), 4, 'four and the All games tile fill five places')
  assert.equal(shelfFit(630, 7, false), 4, 'seven do not fit: four and the tile')
  assert.equal(shelfFit(630, 5, false), 5, 'exactly five fit with nothing left over')
  assert.equal(shelfFit(200, 3, true), 0, 'one place: only the All games tile')
})

test('the ground under the shelf stays flat and whole: no pit, pipe, stairs or tower there', () => {
  for (const [W, H] of [[857, 520], [755, 490], [639, 379]]) {
    for (const seed of [3, 5, 11, 29]) {
      const mid = Math.round(W / 2), flat = [[mid - 190, mid + 190]]
      const world = new World(seed)
      world.build(W, H, { flat })
      const { at, gTop } = world.L
      for (let c = Math.floor(flat[0][0] / T); c <= Math.ceil(flat[0][1] / T) - 1; c++) {
        assert.equal(at(c, gTop), 1, `${W}x${H} seed ${seed}: column ${c} has no ground top (a pit)`)
        assert.equal(at(c, gTop - 1), 0, `${W}x${H} seed ${seed}: column ${c} has a pipe, stairs or a tower on it`)
      }
    }
  }
})
