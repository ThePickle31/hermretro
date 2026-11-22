// Text about one game reaches only that game's own conversation: its Build conversation first, else the chat that
// last worked on it, else a new chat; never the chat the user happens to be in (starting state: games-fixture.mjs).
// Run alone: node tests/page/page-game-chat.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { gamesStudio } from './games-fixture.mjs'
import { runScenario } from './harness.mjs'

await runScenario(async helpers => {
  const { act, dom, scenario, click, tab, settle, check, answered } = helpers
  const { games, studio } = await gamesStudio(helpers)
  const library = list => { scenario.games = answered({ games: list, device: { hardwareEnabled: true, skipped: false } }) }
  const session = { storedId: 'st-comet-build', createdAt: 1, thisProfile: true, profileName: null, exists: true }
  // Comet Drift has a Build conversation and a different chat that last touched it; Ace Arena has neither.
  const robo = { ...session, storedId: 'st-robo-build' }
  library([{ ...games[0], session }, { ...games[1], session: robo }, games[2], games[3]])
  await studio.rerender()
  await tab('Games')

  const card = title => [...dom.window.document.querySelectorAll('.cs-gcard')].find(node => node.textContent.includes(title))
  const menu = async title => {
    await act(async () => { card(title).querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    return card(title).querySelector('.cs-gmenu')
  }
  scenario.calls.length = 0
  await click('Open its chat', await menu('Comet Drift'))
  await settle()
  check("Open its chat opens the game's Build conversation, not the chat that last touched it", () => {
    assert.deepEqual(scenario.calls.find(call => call[0] === 'openSession'), ['openSession', 'st-comet-build', null])
  })

  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Fix in chat', card('Robo Run'))
  await settle()
  check("a game's prompt goes into that game's own composer by its id, never the active one", () => {
    assert.deepEqual(scenario.calls.find(call => call[0] === 'openSession'), ['openSession', 'st-robo-build', null])
    assert.equal(scenario.inserted.at(-1)?.[0], 'st-robo-build')
  })

  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Build in chat', card('Ace Arena')) // unbuilt, with no chat of its own
  await settle()
  check("a prompt for a game without a chat goes to a new chat, never the focused one (it may be another game's)", () => {
    assert.ok(scenario.calls.some(call => call[0] === 'newChat'), 'a new chat is started')
    assert.ok(!scenario.calls.some(call => call[0] === 'insert' && (call[1] === null || call[1] === 'rt-1')), 'nothing is put into the chat in view')
    assert.equal(scenario.inserted.at(-1)?.[0], 'new')
  })
  await studio.close()
})
