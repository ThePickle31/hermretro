// The Games shelf shows completed cards and opens a cover art draft on Build.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'
import { frogPost } from './frog-post-fixture.mjs'

await runScenario(async ({ act, answered, buildScenario, check, click, dom, mount, page, scenario, settle }) => {
  buildScenario()
  // The game card on the Games page: cover art, tagline and genres; a game without one offers to make it.
  scenario.games = answered({ games: [
    frogPost({ session: null, card: null, cover: false }),
    { id: 'ccc333ccc333', title: 'Comet', displayTitle: 'Comet Drift', projectRoot: '/home/u/games/Comet', kind: 'gbstudio', state: 'ready',
      rom: { sha256: 'r1' }, webExport: true, thumb: 'data:image/png;base64,COVER', cover: true, chat: null, error: null, session: null,
      card: { title: 'Comet Drift', tagline: 'Dodge comets in a tiny ship.', description: 'Fly through three comet belts.', genres: ['Arcade', 'Action'],
        tags: [], controls: {}, complete: true, missing: [], hasCover: true } }], device: { hardwareEnabled: false, skipped: true } })
  scenario.storage.page = 'games'
  const shelf = await mount(page)
  await settle()
  const cards = () => [...shelf.node.querySelectorAll('.cs-gcard')]
  check('a game with a card shows its cover, display title, tagline and genres, and no Make cover art', () => {
    const comet = cards().find(node => /Comet Drift/.test(node.textContent))
    assert.equal(comet.querySelector('.cs-cart img').getAttribute('alt'), 'Comet Drift cover art')
    assert.equal(comet.querySelector('.cs-gtag').textContent, 'Dodge comets in a tiny ship.')
    assert.match(comet.querySelector('.cs-gtag').getAttribute('title'), /Arcade · Action/)
    assert.ok(!comet.querySelector('.nocover'))
  })
  {
    const comet = cards().find(node => /Comet Drift/.test(node.textContent))
    await act(async () => { comet.querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    check('a game with a complete card has no Make cover art in its menu', () => { assert.ok(!/Make cover art/.test(comet.querySelector('.cs-gmenu').textContent)) })
    await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape' })) })
  }
  const frog = () => cards().find(node => /Frog Post/.test(node.textContent))
  await act(async () => { frog().querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  check('a game without a card offers Make cover art in its menu', () => { assert.ok(/Make cover art/.test(frog().querySelector('.cs-gmenu').textContent)) })
  await click('Make cover art', frog().querySelector('.cs-gmenu'))
  await settle()
  check('Make cover art opens that game on Build with the request in its message box, not sent', () => {
    assert.equal(shelf.node.querySelector('.cs-b-sw h2')?.textContent, 'Frog Post')
    assert.match(shelf.node.querySelector('textarea[aria-label="Message Hermes"]').value, /160x144 pixel-art cover.*chromatic_game_info/)
  })
  await shelf.close()
})
