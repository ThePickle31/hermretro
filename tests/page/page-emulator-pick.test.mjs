// The Emulator page plays only the game the user picked on the Games page, remembered across visits; with none
// picked it plays the demo cartridge. A game a chat builds never loads there by itself.
// Run alone: node tests/page/page-emulator-pick.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { gamesStudio } from './games-fixture.mjs'
import { runScenario } from './harness.mjs'

await runScenario(async helpers => {
  const { scenario, page, mount, click, tab, currentTab, check, answered } = helpers
  const { games, now2, studio } = await gamesStudio(helpers)
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/x/index.html', romSha256: 'sha', title: 'x' })
  const playing = () => scenario.queries.filter(query => query.key === 'player').at(-1)?.queryKey[2]
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
  await studio.close()

  const again = await mount(page)
  await tab('Emulator')
  check('the pick is remembered when the page is opened again', () => { assert.equal(playing(), 'aaa111aaa111') })
  await again.close()

  scenario.storage.emulatorGame = 'fff999fff999' // a game since removed from the library
  const later = await mount(page)
  await tab('Emulator')
  check('a remembered game no longer in the library falls back to the demo cartridge', () => { assert.equal(playing(), 'demo') })
  await later.close()
})
