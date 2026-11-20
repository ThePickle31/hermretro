// The New Game shelf's order and fit (page/pages/build/cart-shelf.js), and the flat ground the level keeps under it
// (page/pages/build/attract/level.js), without a browser.
// Run alone: node tests/page/cart-shelf.test.mjs
import assert from 'node:assert/strict'
import test from 'node:test'
import { registerAliases } from './aliases.mjs'

registerAliases()
const { shelfFit, shelfOrder } = await import('../../page/pages/build/cart-shelf.js')
const { CART_SHELF_CSS } = await import('../../page/pages/build/cart-shelf.css.js')
const { NEW_GAME_CSS } = await import('../../page/pages/build/new-game.css.js')
const { World } = await import('../../page/pages/build/attract/world.js')
const { T } = await import('../../page/pages/build/attract/physics.js')

const game = (key, state = null) => ({ key, title: key, game: { id: key }, state })

test('newest work first: waiting for an answer, then games being set up, then the library\'s own order', () => {
  // as the games RPC sends them: most recently changed first, with no timestamp (it strips updatedAt)
  const entries = [
    game('newest'),
    game('replied', { unread: true }),
    { key: 'pending:s1', title: 'New game', game: null, pending: { storedId: 's1' }, state: null },
    game('older'),
    game('waiting', { waiting: true })
  ]
  assert.deepEqual(shelfOrder(entries).map(entry => entry.key), ['waiting', 'pending:s1', 'newest', 'replied', 'older'])
})

test('New Game chats being set up: the latest started first, so a full shelf keeps the newest', () => {
  const pending = (id, createdAt) => ({ key: `pending:${id}`, title: 'New game', game: null, pending: { storedId: id, createdAt }, state: null })
  // as the library lists them (oldest first), then one started this visit that it does not know yet
  const entries = [pending('a', 100), pending('b', 200), pending('c', 300), game('done'), pending('local', undefined)]
  const order = shelfOrder(entries).map(entry => entry.key)
  assert.deepEqual(order, ['pending:local', 'pending:c', 'pending:b', 'pending:a', 'done'])
  assert.deepEqual(order.slice(0, shelfFit(3 * 126, order.length, false)), ['pending:local', 'pending:c'], 'two places and the All games tile')
})

test('the cartridges stand on the ground and their captions hang below it at a fixed height', () => {
  const rule = sel => CART_SHELF_CSS.split('\n').find(line => line.startsWith(`${sel} {`)) ?? ''
  assert.match(rule('.cs-b-shelf'), /bottom: calc\(var\(--cs-at-ground, 48px\) - var\(--cs-b-cap\)\)/, 'the shelf drops by the caption height')
  assert.match(rule('.cs-b-shelf-cart .cap'), /height: var\(--cs-b-cap\)/, 'so the caption is exactly that tall')
  assert.match(rule('.cs-b-shelf'), /align-items: flex-end/, 'and every column ends on the same line')
})

test('the form above the shelf is centred only while it fits, so a tall form scrolls back to its title', () => {
  // with plain centring, a form taller than the room left above the shelf (a narrow pane, a long idea) overflows
  // above the top of its scroll box, where scrolling cannot reach (measured in Chromium: the title 9-121 px out)
  const rule = NEW_GAME_CSS.split('\n').find(line => line.startsWith('.cs-b-new {')) ?? ''
  assert.match(rule, /justify-content: safe center;/)
  assert.match(rule, /overflow: auto;/)
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
