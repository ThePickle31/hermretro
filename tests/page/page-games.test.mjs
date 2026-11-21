// The Games shelf fed by the games RPC (the shared starting state is games-fixture.mjs).
// Run alone: node tests/page/page-games.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { gamesStudio } from './games-fixture.mjs'
import { runScenario } from './harness.mjs'

await runScenario(async helpers => {
  const { act, ctx, dom, scenario, text, heading, click, tab, currentTab, settle, button, key, typeInto, check, answered, complete, notLoaded } = helpers
  const { games, studio } = await gamesStudio(helpers)
  await tab('Games')
  // A game's card by its title (games-fixture.mjs: the fixture's orders differ, so never by position).
  const cards = () => [...dom.window.document.querySelectorAll('.cs-gcard')]
  const cardFor = title => cards().find(card => card.textContent.includes(title)) ?? assert.fail(`no card for ${title}`)
  check('Games shows each game as the real cartridge with its title screen, state and meta, plus a blank cartridge last', () => {
    assert.equal(cards().length, 5, 'four games and the blank cartridge')
    const comet = cardFor('Comet Drift'), robo = cardFor('Robo Run')
    assert.equal(comet.querySelector('.cs-cart .slot img').getAttribute('src'), 'data:image/png;base64,AAAA')
    assert.match(comet.textContent, /Ready/); assert.doesNotMatch(comet.textContent, /GB Studio/)
    assert.match(comet.querySelector('.cs-gline').getAttribute('title'), /256 KB/)
    assert.match(comet.querySelector('.cs-split .main').textContent, /^Play$/)
    assert.match(robo.textContent, /Build failed/); assert.match(robo.querySelector('.cs-split .main').textContent, /Fix in chat/)
    assert.match(robo.textContent, /212 tiles/)
    assert.equal(comet.querySelectorAll('.cs-split > button, .cs-split > span > button').length, 2, 'one split control per card')
    assert.ok(!dom.window.document.querySelector('.cs-dev'), 'no hardware strip above a full shelf')
    assert.match(cardFor('Ace Arena').textContent, /never built/)
    assert.ok(cardFor('Old Orbit'))
    assert.match(cards().at(-1).textContent, /Blank cartridge/)
    assert.doesNotMatch(text(), /in your studio|Games showcase/)
  })
  const opensNewGame = async (label, scope, name) => {
    scenario.storage.buildSelected = games[0].id
    scenario.calls.length = 0; scenario.inserted.length = 0
    await click(label, scope)
    check(`${name} opens Build's New Game form without starting a chat`, () => {
      assert.equal(currentTab(), 'Build')
      assert.equal(scenario.storage.buildSelected, 'new')
      const form = dom.window.document.querySelector('.cs-b-new')
      assert.ok(form?.querySelector('textarea[aria-label="Your game idea"]'), 'the new idea box is shown')
      assert.deepEqual([...form.querySelectorAll('[role="radio"] b')].map(mode => mode.textContent), ['Build it', 'Plan first'])
      assert.ok(!scenario.calls.flat().some(value => ['newChat', 'session.create', 'session.load', 'prompt.submit'].includes(value)))
      assert.equal(scenario.inserted.length, 0)
    })
    await tab('Games')
  }
  await opensNewGame('New game', dom.window.document.querySelector('.cs-page-head'), 'The shelf header')
  await opensNewGame('New game', dom.window.document.querySelector('.cs-shelf'), 'The blank cartridge')
  {
    const initialStatus = scenario.status
    const initialGames = scenario.games
    const pending = { storedId: 'stored-from-shelf', name: 'Shelf game', exists: true }
    const idea = 'A frog runs a post office'
    scenario.byMethod['session.create'] = { session_id: 'runtime-from-shelf', stored_session_id: pending.storedId }
    scenario.byMethod['plugin.hermretro.build'] = () => {
      scenario.games = answered({ ...initialGames.data, pending: [pending] })
      return { ok: true }
    }
    scenario.byMethod['prompt.submit'] = { ok: true }
    scenario.byMethod['session.resume'] = { running: true, open_requests: [] }
    await click('New game', dom.window.document.querySelector('.cs-shelf'))
    await typeInto(dom.window.document.querySelector('.cs-b-new textarea'), idea)
    await act(async () => { dom.window.document.querySelector('.cs-b-new .cs-b-send').click() })
    await settle()
    check('a game started from the shelf is selected as its pending conversation', () => {
      assert.equal(scenario.storage.buildSelected, `pending:${pending.storedId}`)
      assert.equal(dom.window.document.querySelector('.cs-b-user')?.textContent, idea)
    })
    scenario.status = notLoaded
    await studio.rerender()
    check('losing the backend unmounts the current Build conversation, without leaving Build', () => {
      assert.equal(currentTab(), 'Build')
      assert.equal(dom.window.document.querySelector('.cs-b-user'), null)
    })
    scenario.status = initialStatus
    await studio.rerender()
    check('the pending conversation returns after reconnect rather than replaying New Game', () => {
      assert.equal(currentTab(), 'Build')
      assert.equal(dom.window.document.querySelector('.cs-b-user')?.textContent, idea)
      assert.equal(scenario.storage.buildSelected, `pending:${pending.storedId}`)
    })
    const store = ctx.storage.set
    scenario.storage.buildSelected = games[0].id
    ctx.storage.set = (key, value) => {
      if (key === 'buildSelected') throw new Error('storage is read-only')
      store(key, value)
    }
    try {
      await tab('Build') // Re-selecting the active tab is not a new visit.
      scenario.status = notLoaded
      await studio.rerender()
      scenario.status = initialStatus
      await studio.rerender()
      check('reconnect keeps the current conversation even when storage still names a different game', () => {
        assert.equal(scenario.storage.buildSelected, games[0].id)
        assert.equal(dom.window.document.querySelector('.cs-b-user')?.textContent, idea)
      })
    } finally {
      ctx.storage.set = store
    }
    await act(async () => { helpers.emit({ type: 'message.complete', session_id: 'runtime-from-shelf', payload: { text: 'Done.' } }) })
    scenario.games = initialGames
    for (const method of ['session.create', 'plugin.hermretro.build', 'prompt.submit', 'session.resume']) delete scenario.byMethod[method]
    await tab('Games')
  }
  {
    const store = ctx.storage.set
    let attempted = false
    ctx.storage.set = (key, value) => {
      if (key === 'buildSelected') {
        attempted = true
        throw new Error('storage is read-only')
      }
      store(key, value)
    }
    try {
      scenario.storage.buildSelected = games[0].id
      await click('New game', dom.window.document.querySelector('.cs-shelf'))
      check('the blank cartridge still opens New Game when the previous selection cannot be overwritten', () => {
        assert.ok(attempted, 'the attempt to persist was made')
        assert.equal(scenario.storage.buildSelected, games[0].id)
        assert.equal(currentTab(), 'Build')
        assert.ok(dom.window.document.querySelector('.cs-b-new textarea'))
      })
    } finally {
      ctx.storage.set = store
    }
    await tab('Games')
  }
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
  const cometCard = () => cardFor('Comet Drift')
  check('the split arrow is closed until pressed', () => { assert.ok(!cometCard().querySelector('.cs-gmenu')) })
  {
    const menu = await openGameMenu(cometCard())
    check('without hardware tools Install is locked in the menu and the header chip offers to set up the Chromatic', () => {
      const install = [...menu.querySelectorAll('button')].find(node => /Install on Chromatic/.test(node.textContent))
      assert.ok(install.disabled); assert.match(install.textContent, /Needs your Chromatic/)
      assert.match(menu.textContent, /Open its chat/); assert.match(menu.textContent, /Show in folder/)
      assert.match(text(), /Emulator only · Set up my Chromatic/)
    })
    await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape' })) })
    check('Escape closes the game menu', () => { assert.ok(!cometCard().querySelector('.cs-gmenu')) })
  }
  {
    // A menu item's effect is checked here, in the host page's scenario: scenario.clipboard and scenario.notices
    // record what it copied and said (docs/dev/STUDIO-PAGES.md, "A contribution to a slot").
    const reveal = ctx.os.revealPath
    ctx.os.revealPath = async () => false
    scenario.clipboard.length = 0; scenario.notices.length = 0
    await click('Show in folder', await openGameMenu(cometCard()))
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
  await click('Install on Chromatic', await openGameMenu(cometCard()))
  await settle()
  check("Install sends the flash prompt, naming the game, to that game's own chat (the chat's approval gate applies)", () => {
    assert.deepEqual(scenario.calls[0], ['openSession', 'stored-comet', null])
    const [, value] = scenario.inserted.at(-1)
    assert.match(value, /^Flash the built ROM of "Comet Drift" \(\/home\/u\/ChromaticGames\/CometDrift\) to the connected Chromatic cartridge/)
  })
  scenario.games = { isError: true, isFetching: false, error: Object.assign(new Error('unknown method'), { code: -32601 }) }
  await studio.rerender()
  check('a backend without the games RPC is reported honestly', () => { assert.match(text(), /cannot list your games yet/) })
  await opensNewGame('New game', dom.window.document, 'The library error action')
  scenario.games = answered({ games: [], device: { hardwareEnabled: true, skipped: false } })
  await studio.rerender()
  check('the empty library drops the example prompt shortcut', () => { assert.equal(heading(), 'No games yet'); assert.doesNotMatch(text(), /Remix Wrecklight/) })
  await opensNewGame('Create a new game', dom.window.document, 'The empty library action')
  await studio.close()
})
