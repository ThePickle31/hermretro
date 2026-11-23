// Run alone: node tests/page/page-games-unavailable.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ answered, buildScenario, check, hides, mount, page, scenario, shows, tab }) => {
  const id = 'aaa111aaa111'
  const game = { id, state: 'ready', title: 'Comet Drift' }
  const failure = 'Could not read the game library.'
  const method = 'plugin.hermretro.games'
  buildScenario({ selected: id })
  scenario.storage.emulatorGame = id
  scenario.byMethod[method] = { ok: false, games: [], error: failure }
  const studio = await mount(page)
  const result = await scenario.fns.games().catch(error => ({ error, isError: true }))
  scenario.games = result.isError ? result : answered(result)
  await studio.rerender()
  check('the Build page reports a failed library read and keeps the remembered game', () => {
    shows(failure)
    assert.equal(scenario.storage.buildSelected, id)
  })

  await tab('Games')
  check('a failed library read uses the shelf error instead of its empty state', () => {
    shows(failure)
    hides('No games yet')
  })
  await tab('Emulator')
  check('the Emulator reports a library failure while waiting for a remembered game', () => {
    shows(failure)
    assert.equal(scenario.storage.emulatorGame, id)
  })

  const loaded = { ok: true, games: [game], pending: [] }
  scenario.byMethod[method] = loaded
  scenario.games = answered(await scenario.fns.games())
  await tab('Build')
  check('the remembered game opens once the library is readable', () => {
    shows('Comet Drift')
    hides(failure)
    assert.equal(scenario.storage.buildSelected, id)
  })

  scenario.games = { ...result, data: loaded }
  await studio.rerender()
  check('a failed refresh leaves the cached Build game open', () => {
    shows('Comet Drift')
    shows(failure)
    assert.equal(scenario.storage.buildSelected, id)
  })
  await tab('Games')
  check('a failed refresh leaves the cached shelf visible with the error', () => {
    shows('Comet Drift')
    shows(failure)
  })

  scenario.games = answered({ ok: true, games: [], pending: [] })
  await studio.rerender()
  check('a successful empty library shows the empty state', () => { shows('No games yet') })
  await tab('Build')
  check('a successful read confirming removal can reset the selection', () => {
    assert.equal(scenario.storage.buildSelected, 'new')
  })
  await studio.close()
})
