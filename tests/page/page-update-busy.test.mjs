// No update while something is being built (app/update/): a chat in the hermretro profile with a turn under way, or the
// page's toolchain install, refuses Update; a build that starts after the last check is caught right before anything
// changes; one that starts while Hermes updates is waited for before the hermretro profile reloads; and nothing new is
// sent from the Build page while an update runs.
// Run alone: node tests/page/page-update-busy.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, root, render, settle, click, button, check, shows, tab, typeInto, answered, status, doctor, installAnswer }) => {
  const document = dom.window.document
  const chip = () => document.querySelector('.cs-upd-chip')
  const popover = () => document.querySelector('.cs-upd-pop')?.textContent.replace(/\s+/g, ' ') ?? ''
  const openChip = async () => { await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) }) }
  const base = () => ({ ...status(), plugin: { version: '1.2.3', installed_in: { profile: 'default', linked: false } } })
  // Everything the update asks Hermes, in order: 'busy' for each look at the hermretro profile's chats.
  const log = []
  let sessions = () => []
  let updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true, restart_required: false })
  scenario.byMethod['session.active_list'] = () => { log.push('busy'); return { sessions: sessions() } }
  scenario.byMethod['plugins.manage'] = params => {
    log.push(params.action === 'toggle' ? `toggle:${params.enable}` : params.action)
    if (params.action === 'update') return updateAnswer(params)
    return { ok: true, unchanged: false, gateway_reloaded: true, restart_required: false }
  }
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => { log.push('finish'); return { ok: true } }
  dom.window.hermesDesktop = { reconcileDesktopPlugins: async () => [] }
  const building = (title = 'Comet Drift') => ({ id: 's1', title, status: 'working' })
  scenario['plugin-update'] = answered({ target: { route: null, profile: 'default' }, row: { name: 'hermretro', update_available: true, update_target: 'abc' } })
  const fresh = async ({ busy = [], install = 'idle', page = 'home' } = {}) => {
    await act(async () => { root.render(null) })
    scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page }
    scenario.status = answered(base()); scenario.doctor = answered(doctor([])); scenario.install = installAnswer({ state: install })
    scenario['update-busy'] = answered(busy)
    log.length = 0
    await render()
  }

  // A chat is building: Update is refused, and says where.
  await fresh({ busy: ['Comet Drift'] })
  await openChip()
  check('while a chat builds, the popover says which and Update now is disabled', () => {
    assert.match(popover(), /A game is being built in "Comet Drift"\. You can update when it finishes\./)
    assert.equal(button('Update now').disabled, true)
  })
  check('the busy check runs every 5 seconds while an update is ready', () => {
    const query = scenario.queries.filter(entry => entry.key === 'update-busy').at(-1)
    assert.equal(query.enabled, true); assert.equal(query.refetchInterval, 5_000)
  })
  await fresh({ busy: ['Comet Drift', 'Moon Maze', 'Third'], page: 'setup' })
  check('the Setup row\'s Update is disabled too, naming the chats', () => {
    shows(/Games are being built in 3 chats \("Comet Drift" and "Moon Maze"…\)/)
    const update = [...document.querySelectorAll('.cs-facts button')].find(node => node.textContent === 'Update')
    assert.ok(update, 'the row has an Update button'); assert.equal(update.disabled, true)
  })

  // The toolchain install is running.
  await fresh({ install: 'running' })
  await openChip()
  check('while the game tools install, Update now is disabled', () => {
    assert.match(popover(), /The game tools are being installed/); assert.equal(button('Update now').disabled, true)
  })

  // A build started after the last check: caught right before anything changes.
  sessions = () => [building()]
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  check('a build that started since the last check stops the update before Hermes changes anything', () => {
    assert.deepEqual(log, ['busy'])
    assert.match(popover(), /A game is being built in "Comet Drift"/); assert.equal(button('Update now').disabled, true)
  })

  // The check itself fails: no update on a guess.
  scenario.byMethod['session.active_list'] = () => { log.push('busy'); throw new Error('profile not reachable') }
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  check('when the chats cannot be checked, nothing is updated', () => {
    assert.deepEqual(log, ['busy']); assert.equal(chip().textContent, 'Update failed')
    assert.match(popover(), /Could not check whether a game is being built \(profile not reachable\)/)
  })
  scenario.byMethod['session.active_list'] = () => { log.push('busy'); return { sessions: sessions() } }

  // A build started while Hermes updated: the hermretro profile reloads only after it finishes.
  let looks = 0
  sessions = () => { looks += 1; return looks === 2 || looks === 3 ? [building('Moon Maze')] : [] }
  await fresh()
  await openChip(); await click('Update now'); await settle(300)
  check('a build started during the update is waited for, and the popover says so', () => {
    assert.match(popover(), /Waiting for "Moon Maze" to finish building/)
    assert.ok(!log.includes('toggle:false'), 'not reloaded while it builds')
  })
  await settle(4_500)
  check('once it finishes, the hermretro profile reloads', () => {
    assert.deepEqual(log, ['busy', 'update', 'finish', 'busy', 'busy', 'busy', 'toggle:false', 'toggle:true'])
    assert.equal(chip().textContent, 'Updated')
  })

  // Nothing new starts from the Build page while an update runs.
  sessions = () => []
  let finish
  updateAnswer = () => new Promise(resolve => { finish = resolve })
  scenario.games = answered({ games: [] })
  await fresh({ page: 'build' })
  const send = () => document.querySelector('.cs-b-new .cs-b-send')
  await typeInto(document.querySelector('.cs-b-new textarea'), 'A lighthouse game')
  check('with an idea typed, New Game can start', () => { assert.equal(send().disabled, false) })
  await openChip(); await click('Update now'); await settle(40)
  check('while updating, New Game cannot start a game', () => {
    assert.ok(send(), 'the New Game composer is shown'); assert.equal(send().disabled, true)
    assert.match(send().getAttribute('title'), /hermretro is updating/)
  })
  await act(async () => { finish({ ok: true, unchanged: true }) }); await settle(40)
  check('afterwards it starts games again', () => {
    assert.equal(send().disabled, false); assert.match(send().getAttribute('title'), /Start (building|planning)/)
  })
  await tab('Home')
})
