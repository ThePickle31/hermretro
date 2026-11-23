// Run alone: node tests/page/page-games-unavailable.test.mjs [path to a node_modules folder]
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ answered, buildScenario, check, hides, mount, notLoaded, page, scenario, shows, tab }) => {
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

  const loaded = { ok: true, games: [game], unavailable: [], pending: [] }
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

  const partial = { ok: true, games: [], unavailable: [id], pending: [] }
  scenario.games = answered(partial)
  await studio.rerender()
  check('an unavailable game on a successful shelf keeps its Build selection and shows an error', () => {
    shows('Could not read the selected game.')
    hides('Reading your games')
    assert.equal(scenario.storage.buildSelected, id)
  })

  scenario.games = answered({ ok: true, games: [], pending: [] })
  await studio.rerender()
  check('Build checks the missing game separately when an older shelf omits availability', () => {
    shows('Reading your games')
    assert.equal(scenario.queries.filter(query => query.key === 'buildSelectionStatus').at(-1).enabled, true)
    assert.equal(scenario.storage.buildSelected, id)
  })
  scenario.byMethod['plugin.hermretro.game_build_status'] = () => { throw notLoaded.error }
  scenario.buildSelectionStatus = await scenario.fns.buildSelectionStatus().catch(error => ({ isError: true, error }))
  await studio.rerender()
  check('an older backend without the individual check keeps the selection and reports the error', () => {
    shows('Could not read the selected game.')
    hides('Reading your games')
    assert.equal(scenario.storage.buildSelected, id)
  })
  scenario.games = answered(loaded)
  await studio.rerender()
  check('the selected game reopens when the shelf recovers', () => {
    shows('Comet Drift')
    hides('Could not read the selected game.')
    assert.equal(scenario.storage.buildSelected, id)
  })

  scenario.games = { ...result, data: loaded }
  await tab('Games')
  check('a failed refresh leaves the cached shelf visible with the error', () => {
    shows('Comet Drift')
    shows(failure)
  })

  const partialFailure = 'Some games could not be read.'
  scenario.games = answered({ ...loaded, unavailable: ['bbb222bbb222'] })
  await studio.rerender()
  check('a partial shelf read keeps the available cards and shows the read error', () => {
    shows('Comet Drift')
    shows(partialFailure)
    assert.equal(studio.node.querySelector('[role="alert"]')?.textContent, partialFailure)
  })
  scenario.games = answered(partial)
  await studio.rerender()
  check('a shelf of unreadable games shows the read error instead of the empty state', () => {
    shows(partialFailure)
    hides('No games yet')
  })

  scenario.games = answered({ ok: true, games: [], unavailable: [], pending: [] })
  await studio.rerender()
  check('a successful empty library shows the empty state', () => {
    shows('No games yet')
    hides(partialFailure)
  })
  await tab('Build')
  check('a successful read confirming removal can reset the selection', () => {
    assert.equal(scenario.storage.buildSelected, 'new')
  })
  await studio.close()

  buildScenario({ selected: id })
  scenario.games = answered({ ok: true, games: [], pending: [] })
  const older = await mount(page)
  scenario.byMethod['plugin.hermretro.game_build_status'] = { ok: false, code: 'NO_GAME' }
  scenario.buildSelectionStatus = answered(await scenario.fns.buildSelectionStatus())
  await older.rerender()
  check('an older shelf clears the missing selection after the separate check confirms removal', () => {
    assert.equal(scenario.storage.buildSelected, 'new')
  })
  await older.close()
})
