// Home and the Games shelf fed by the games RPC (the shared starting state is games-fixture.mjs; Prompts,
// the Emulator and the emulator beside the chat are page-prompts, page-emulator and page-emulator-side .test.mjs).
// Run alone: node tests/page/page-games.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { gamesStudio } from './games-fixture.mjs'
import { runScenario } from './harness.mjs'

await runScenario(async helpers => {
  const { act, ctx, dom, scenario, text, heading, HOME, click, tab, settle, button, key, check, answered, complete } = helpers
  const { games, studio } = await gamesStudio(helpers)
  check('Home continues with the most recently built game from the games RPC', () => {
    assert.equal(heading(), HOME)
    assert.equal(dom.window.document.querySelector('.cs-cont .name').textContent, 'Comet Drift')
    assert.match(text(), /Chat: Comet Drift — first level/)
  })
  await tab('Games')
  check('Games shows each game as the real cartridge with its title screen, state and meta, plus a blank cartridge', () => {
    const cards = [...dom.window.document.querySelectorAll('.cs-gcard')]
    assert.equal(cards.length, 4)
    assert.equal(cards[0].querySelector('.cs-cart .slot img').getAttribute('src'), 'data:image/png;base64,AAAA')
    assert.match(cards[0].textContent, /Ready/); assert.doesNotMatch(cards[0].textContent, /GB Studio/)
    assert.match(cards[0].querySelector('.cs-gline').getAttribute('title'), /256 KB/)
    assert.match(cards[0].querySelector('.cs-split .main').textContent, /^Play$/)
    assert.match(cards[1].textContent, /Build failed/); assert.match(cards[1].querySelector('.cs-split .main').textContent, /Fix in chat/)
    assert.match(cards[1].textContent, /212 tiles/)
    assert.equal(cards[0].querySelectorAll('.cs-split > button, .cs-split > span > button').length, 2, 'one split control per card')
    assert.ok(!dom.window.document.querySelector('.cs-dev'), 'no hardware strip above a full shelf')
    assert.match(cards[2].textContent, /Old Orbit/)
    assert.match(cards[3].textContent, /Blank cartridge/)
    assert.doesNotMatch(text(), /in your studio|Games showcase/)
  })
  scenario.revealed = null
  await click('Open games folder')
  check('the shelf shows the games folder and opens it', () => {
    assert.match(dom.window.document.querySelector('.cs-gfolder').textContent, /\/home\/u\/\.hermes\/hermretro\/games/)
    assert.equal(scenario.revealed, '/home/u/.hermes/hermretro/games')
  })
  const openGameMenu = async card => {
    await act(async () => { card.querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    return card.querySelector('.cs-gmenu')
  }
  const firstCard = () => dom.window.document.querySelectorAll('.cs-gcard')[0]
  check('the split arrow is closed until pressed', () => { assert.ok(!firstCard().querySelector('.cs-gmenu')) })
  {
    const menu = await openGameMenu(firstCard())
    check('without hardware tools Install is locked in the menu and the header chip offers to set up the Chromatic', () => {
      const install = [...menu.querySelectorAll('button')].find(node => /Install on Chromatic/.test(node.textContent))
      assert.ok(install.disabled); assert.match(install.textContent, /Needs your Chromatic/)
      assert.match(menu.textContent, /Open its chat/); assert.match(menu.textContent, /Show in folder/)
      assert.match(text(), /Emulator only · Set up my Chromatic/)
    })
    await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape' })) })
    check('Escape closes the game menu', () => { assert.ok(!firstCard().querySelector('.cs-gmenu')) })
  }
  {
    // A menu item's effect is checked here, in the host page's scenario: scenario.clipboard and scenario.notices
    // record what it copied and said (docs/dev/STUDIO-PAGES.md, "A contribution to a slot").
    const reveal = ctx.os.revealPath
    ctx.os.revealPath = async () => false
    scenario.clipboard.length = 0; scenario.notices.length = 0
    await click('Show in folder', await openGameMenu(firstCard()))
    await settle()
    ctx.os.revealPath = reveal
    check('Show in folder on a remote Hermes copies the folder path and says so', () => {
      assert.deepEqual(scenario.clipboard, ['/home/u/ChromaticGames/CometDrift'])
      assert.ok(scenario.notices.some(notice => /Its folder path is copied/.test(notice.message)))
    })
  }
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Fix in chat')
  await settle()
  check('Fix in chat puts the build error into a chat, not sent', () => {
    assert.ok(scenario.inserted.some(([, value]) => /212 tiles/.test(value) && /Robo Run/.test(value)))
    assert.ok(!scenario.calls.some(call => /send|submit/i.test(call[0])))
  })
  scenario.status = answered({ ...complete, hardware_enabled: true })
  await studio.rerender()
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Install on Chromatic', await openGameMenu(firstCard()))
  await settle()
  check("Install sends the flash prompt, naming the game, to that game's own chat (the chat's approval gate applies)", () => {
    assert.deepEqual(scenario.calls[0], ['openSession', 'stored-comet', null])
    const [, value] = scenario.inserted.at(-1)
    assert.match(value, /^Flash the built ROM of "Comet Drift" \(\/home\/u\/ChromaticGames\/CometDrift\) to the connected Chromatic cartridge/)
  })
  scenario.games = { isError: true, isFetching: false, error: Object.assign(new Error('unknown method'), { code: -32601 }) }
  await studio.rerender()
  check('a backend without the games RPC is reported honestly', () => { assert.match(text(), /cannot list your games yet/) })
  scenario.games = answered({ games: [], device: { hardwareEnabled: true, skipped: false } })
  await studio.rerender()
  check('an empty library offers a new game and the remix', () => { assert.equal(heading(), 'No games yet'); assert.match(text(), /Remix Wrecklight/) })
  await studio.close()
})
