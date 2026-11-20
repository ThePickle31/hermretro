// The Build page's New Game shelf: the games being worked on stand as cartridges under the form, newest first, each
// opening its own chat; All games opens the games menu. (Order and fit rules: cart-shelf.test.mjs.)
// Run alone: node tests/page/page-build-shelf.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ buildScenario, act, dom, scenario, page, click, tab, settle, mount, check, answered }) => {
  const fire = (node, type) => act(async () => { node.dispatchEvent(new dom.window.MouseEvent(type, { bubbles: true, cancelable: true })) })
  buildScenario()
  // As the games RPC answers: most recently changed first, no updatedAt (it strips it).
  const game = (id, title, extra = {}) => ({ id, title, projectRoot: `/home/u/games/${id}`, kind: 'gbstudio', state: 'ready',
    rom: null, webExport: false, thumb: null, chat: null, error: null, ...extra })
  const library = [
    game('ccc333ccc333', 'Moon Courier'),
    game('bbb222bbb222', 'Frog Post', { session: { storedId: 'st-frog' } }),
    game('aaa111aaa111', 'Comet Drift', { session: { storedId: 'st-comet' }, thumb: 'data:image/png;base64,AAAA', cover: true })
  ]
  scenario.games = answered({ games: library, device: { hardwareEnabled: false, skipped: true } })
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, running: false, messages: [] })
  const view = await mount(page)
  await click('Refresh')
  await tab('Build')
  await settle()
  const shelf = () => view.node.querySelector('nav.cs-b-shelf[aria-label="Your games"]')
  check('New Game shows the games being worked on as cartridges, newest first, under the form', () => {
    assert.ok(shelf(), 'the shelf is there')
    const carts = [...shelf().querySelectorAll('.cs-b-shelf-cart:not(.all)')]
    assert.deepEqual(carts.map(cart => cart.querySelector('b').textContent), ['Frog Post', 'Comet Drift'], 'games with a chat, in the library\'s newest-first order')
    assert.ok(!/Moon Courier/.test(shelf().textContent.replace('All games', '')), 'a game with no chat is not on the shelf')
    assert.equal(carts[1].querySelector('.cs-cart img').getAttribute('alt'), 'Comet Drift cover art', 'the cover is in the label')
    assert.match(carts[0].querySelector('.cs-cart .ph').textContent, /Frog Post/, 'a placeholder label without a picture')
    assert.match(carts[0].querySelector('.cs-cart').getAttribute('aria-label'), /^Frog Post, /, 'each cartridge is named by its game and status')
    assert.equal(shelf().getAttribute('data-at-flat'), '', 'the level keeps the ground under it flat')
    assert.ok(view.node.querySelector('.cs-b-new + .cs-b-shelf'), 'after the form: Tab reaches it after the composer')
  })
  check('the last tile counts the rest of the library', () => {
    const all = shelf().querySelector('.cs-b-shelf-more')
    assert.equal(all.textContent, '+1'); assert.equal(all.getAttribute('aria-label'), 'All games: 1 more')
  })
  await fire(shelf().querySelector('.cs-b-shelf-more'), 'click')
  await settle()
  check('All games opens the games menu at the rest of the library', () => {
    const pop = view.node.querySelector('.cs-b-sw-pop')
    assert.ok(pop, 'the menu is open'); assert.match(pop.textContent, /Moon Courier/)
    assert.ok(pop.querySelector('input[aria-label="Search your games"]'), 'the Edit a game list')
  })
  await fire([...view.node.querySelectorAll('.cs-b-sw-list button')].find(node => node.textContent.includes('Moon Courier')), 'click')
  await settle()
  check('picking from that menu opens the game with the menu closed, and it stays closed', () => {
    assert.equal(view.node.querySelector('.cs-b-sw h2').textContent, 'Moon Courier')
    assert.ok(!view.node.querySelector('.cs-b-sw-pop'), 'no menu in the conversation')
  })
  await fire(view.node.querySelector('.cs-b-sw'), 'click')
  await fire([...view.node.querySelectorAll('.cs-b-sw-pop button')].find(node => /New game/.test(node.textContent)), 'click')
  await settle()
  check('back on New Game the menu does not open again by itself', () => {
    assert.ok(view.node.querySelector('.cs-b-new'), 'New Game is shown')
    assert.ok(!view.node.querySelector('.cs-b-sw-pop'), 'the All games request was used up')
  })
  await fire(shelf().querySelector('.cs-b-shelf-cart .cs-cart'), 'click')
  await settle()
  check('a cartridge opens that game\'s chat', () => {
    assert.equal(view.node.querySelector('.cs-b-sw h2').textContent, 'Frog Post')
    assert.ok(!view.node.querySelector('.cs-b-shelf'), 'the shelf is only on New Game')
  })
  await view.close()
  scenario.games = answered({ games: [library[0]], device: { hardwareEnabled: false, skipped: true } })
  scenario.storage = { setup: { hardwareSkipped: true, onboarded: true }, page: 'build' }
  const empty = await mount(page)
  await settle()
  check('with no game being worked on there is no shelf', () => {
    assert.ok(empty.node.querySelector('.cs-b-new'), 'New Game is shown')
    assert.ok(!empty.node.querySelector('.cs-b-shelf'))
  })
  await empty.close()
})
