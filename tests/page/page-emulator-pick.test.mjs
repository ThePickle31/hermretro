// The Emulator page plays only the game the user picked on the Games page, remembered across visits; with none
// picked it plays the demo cartridge. A game a chat builds never loads there by itself.
import assert from 'node:assert/strict'

import { gamesStudio } from './games-fixture.mjs'
import { runScenario } from './harness.mjs'

await runScenario(async helpers => {
  const { act, emit, scenario, page, mount, click, tab, currentTab, settle, check, answered } = helpers
  const { games, now2, studio } = await gamesStudio(helpers)
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/x/index.html', romSha256: 'sha', title: 'x' })
  // The page's own player query (the tab beside the chat asks with 'side' in the same place).
  const playing = () => scenario.queries.filter(query => query.key === 'player' && query.queryKey[2] !== 'side').at(-1)?.queryKey[2]
  const library = list => { scenario.games = answered({ games: list, device: { hardwareEnabled: true, skipped: false } }) }
  const rebuilt = (list, id, builtAt) => list.map(game => (game.id === id ? { ...game, rom: { ...game.rom, sha256: `sha-${builtAt}`, builtAt } } : game))

  await tab('Emulator')
  check('with nothing picked, the page plays the demo cartridge, not the newest game in the library', () => {
    assert.equal(playing(), 'demo')
  })
  library(rebuilt(games, 'ccc333ccc333', now2 + 60))
  await studio.rerender()
  check('a chat building a game does not load it here', () => { assert.equal(playing(), 'demo') })

  await tab('Games')
  await click('Play')
  check('Play on the Games page loads that game here and remembers it', () => {
    assert.equal(currentTab(), 'Emulator')
    assert.equal(playing(), 'aaa111aaa111')
    assert.equal(scenario.storage.emulatorGame, 'aaa111aaa111')
  })
  library(rebuilt(games, 'ccc333ccc333', now2 + 120))
  await studio.rerender()
  check('another game rebuilt in its chat leaves the picked game playing', () => { assert.equal(playing(), 'aaa111aaa111') })

  // A chat presents another game: it opens beside the chat; bringing the player back plays the picked game here.
  const presented = { ok: true, studio: { gameId: 'ccc333ccc333', playerUrl: 'http://127.0.0.1:4567/tok/ccc333ccc333/index.html', title: 'Old Orbit', note: null, presentedAt: 7 } }
  await act(async () => { emit({ type: 'tool.complete', session_id: 'rt-orbit', payload: { tool_id: 't-present', name: 'chromatic_present_game', args: {}, result: presented } }) })
  await settle()
  const side = await mount({ render: scenario.workspaces.at(-1).options.render })
  await studio.rerender()
  await click('Bring it here', studio.node)
  check('Bring it here after a chat presented another game plays the picked game on the page', () => {
    assert.equal(playing(), 'aaa111aaa111')
    assert.ok(studio.node.querySelector('.cs-rp-stage iframe'), 'the page runs the player again')
  })
  await side.close()
  await studio.close()

  const again = await mount(page)
  await tab('Emulator')
  check('the pick is remembered when the page is opened again', () => { assert.equal(playing(), 'aaa111aaa111') })
  await again.close()

  scenario.games = { isError: true, isFetching: false, error: new Error('gateway timed out') }
  const before = scenario.queries.length
  const failing = await mount(page)
  await tab('Emulator')
  check('while the library cannot be read, the remembered game is waited for: the demo does not flash first', () => {
    const asked = scenario.queries.slice(before).filter(query => query.key === 'player' && query.queryKey[2] !== 'side')
    assert.ok(asked.length > 0, 'the page set up its player')
    assert.ok(asked.every(query => query.queryKey[2] !== 'demo'), 'the demo was never asked for')
    assert.equal(scenario.storage.emulatorGame, 'aaa111aaa111', 'and the pick is kept')
  })
  library(games)
  await failing.rerender()
  check('once the library answers, the remembered game plays', () => { assert.equal(playing(), 'aaa111aaa111') })
  await failing.close()

  scenario.storage.emulatorGame = 'fff999fff999' // a game since removed from the library
  scenario.gameBuildStatus = { isError: true, isFetching: false, error: new Error('Project is unavailable') }
  const later = await mount(page)
  await tab('Emulator')
  check('a successful shelf refresh that omits an unavailable project keeps the remembered pick', () => {
    assert.equal(playing(), null)
    assert.equal(scenario.storage.emulatorGame, 'fff999fff999')
  })
  scenario.gameBuildStatus = answered({ ok: false, code: 'NO_GAME' })
  await later.rerender()
  check('a remembered game no longer in the library falls back to the demo cartridge and is forgotten', () => {
    assert.equal(playing(), 'demo')
    assert.equal(scenario.storage.emulatorGame, null, 'a new game later made in its folder is not played without Play')
  })
  await later.close()
})
