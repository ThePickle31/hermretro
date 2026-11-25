// No update while something is being built (app/update/): a chat in the hermretro profile with a turn under way, or the
// page's toolchain install, makes Update wait for it; a build that starts after the last check is caught right before anything
// changes; one that starts while Hermes updates is waited for before the hermretro profile reloads; and nothing new is
// sent from the Build page while an update runs.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, root, render, settle, click, button, check, shows, tab, typeInto, answered, status, doctor, installAnswer, holdTimers }) => {
  const document = dom.window.document
  scenario.byMethod['plugin.hermretro.install'] = () => installAnswer({ state: 'idle' }).data
  const chip = () => document.querySelector('.cs-upd-chip')
  const scrim = () => document.querySelector('.cs-upd-scrim')
  const popover = () => scrim()?.textContent.replace(/\s+/g, ' ') ?? ''
  // The dialog's own buttons (the corner card and the Setup row have an Update too).
  const inDialog = label => [...(scrim()?.querySelectorAll('button') ?? [])].find(node => node.textContent === label)
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
  const fresh = async ({ busy = [], install = 'idle', page = 'games' } = {}) => {
    await act(async () => { root.render(null) })
    scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page }
    scenario.status = answered(base()); scenario.doctor = answered(doctor([])); scenario.install = installAnswer({ state: install, run_id: install === 'running' ? 'run-a' : null })
    scenario['update-busy'] = answered(busy)
    log.length = 0
    await render()
  }

  // A chat is building: Update waits for it, and says where.
  await fresh({ busy: ['Comet Drift'] })
  await openChip()
  check('while a chat builds, the dialog says which', () => {
    assert.match(popover(), /A game is being built in "Comet Drift"\. You can update when it finishes\./)
  })
  await click('Update', scrim()); await settle(40)
  check('Update then waits for the build, changing nothing yet', () => {
    assert.match(popover(), /"Comet Drift" is building\. The update starts as soon as it finishes\./)
    assert.equal(inDialog('Waiting…').disabled, true); assert.ok(inDialog('Cancel'))
    assert.ok(!log.includes('update'))
  })
  scenario['update-busy'] = answered([])
  await render(); await settle(40)
  check('once the build finishes, the update starts by itself', () => {
    assert.ok(log.includes('update')); assert.equal(chip().textContent, 'Updated')
  })
  await fresh({ busy: ['Comet Drift'] })
  await openChip(); await click('Update', scrim()); await click('Cancel', scrim())
  scenario['update-busy'] = answered([])
  await render(); await settle(40)
  check('Cancel forgets the waiting update', () => { assert.ok(!log.includes('update')) })
  await fresh({ busy: ['Comet Drift'] })
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
  check('while the game tools install, the dialog says so and Update would wait for it', () => {
    assert.match(popover(), /The game tools are being installed/); assert.equal(inDialog('Update').disabled, false)
  })

  // A build started after the last check: caught right before anything changes.
  sessions = () => [building()]
  await fresh()
  await openChip(); await click('Update', scrim()); await settle(40)
  check('a build that started since the last check holds the update before Hermes changes anything', () => {
    assert.deepEqual(log, ['busy'])
    assert.match(popover(), /"Comet Drift" is building\. The update starts as soon as it finishes/); assert.equal(inDialog('Waiting…').disabled, true)
  })

  // The check itself fails: no update on a guess.
  scenario.byMethod['session.active_list'] = () => { log.push('busy'); throw new Error('profile not reachable') }
  await fresh()
  await openChip(); await click('Update', scrim()); await settle(40)
  check('when the chats cannot be checked, nothing is updated', () => {
    assert.deepEqual(log, ['busy']); assert.equal(chip().textContent, 'Update failed')
    assert.match(popover(), /Could not check whether a game is being built \(profile not reachable\)/)
  })
  scenario.byMethod['session.active_list'] = () => { log.push('busy'); return { sessions: sessions() } }

  // A build started while Hermes updated: the hermretro profile reloads only after it finishes.
  let looks = 0
  sessions = () => { looks += 1; return looks === 2 || looks === 3 ? [building('Moon Maze')] : [] }
  const clock = holdTimers()  // the update's wait for the build to finish, on the fake clock
  await fresh()
  await openChip(); await click('Update', scrim()); await settle(300)
  check('a build started during the update is waited for, and the popover says so', () => {
    assert.match(popover(), /Waiting for "Moon Maze" to finish building/)
    assert.ok(!log.includes('toggle:false'), 'not reloaded while it builds')
  })
  for (let round = 0; round < 8 && !log.includes('toggle:true'); round++) await clock.fire()
  check('once it finishes, the hermretro profile reloads', () => {
    assert.deepEqual(log, ['busy', 'update', 'finish', 'busy', 'busy', 'busy', 'toggle:false', 'toggle:true'])
    assert.equal(chip().textContent, 'Updated')
  })

  // First-time setup: an update started first keeps the toolchain install (and the profile setup) from starting.
  sessions = () => []
  let release
  updateAnswer = () => new Promise(resolve => { release = resolve })
  await act(async () => { root.render(null) })
  scenario.storage = { setup: { onboardStarted: true } }
  scenario.status = answered(base()); scenario.doctor = answered(doctor(['cli'])); scenario.install = installAnswer({ state: 'idle' })
  scenario['update-busy'] = answered([])
  const installs = []
  scenario.byMethod['plugin.hermretro.install'] = params => { installs.push(params.action); return { ok: true, install: { state: 'idle' } } }
  await render()
  const download = () => button('Download and install')
  check('the install screen offers Download and install before an update', () => { assert.ok(download()); assert.equal(download().disabled, false) })
  await openChip(); await click('Update', scrim()); await settle(40)
  check('while the update runs, Download and install is disabled', () => { assert.equal(download().disabled, true) })
  download().click(); await settle(40)
  check('and pressing it starts no install', () => { assert.ok(!installs.includes('prepare_start')) })
  await act(async () => { release({ ok: true, unchanged: true }) }); await settle(40)
  check('after the update the install can start again', () => { assert.equal(download().disabled, false) })
  updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true, restart_required: false })

  // Nothing new starts from the Build page while an update runs.
  sessions = () => []
  let finish
  updateAnswer = () => new Promise(resolve => { finish = resolve })
  scenario.games = answered({ games: [] })
  await fresh({ page: 'build' })
  const send = () => document.querySelector('.cs-b-new .cs-b-send')
  await typeInto(document.querySelector('.cs-b-new textarea'), 'A lighthouse game')
  check('with an idea typed, New Game can start', () => { assert.equal(send().disabled, false) })
  await openChip(); await click('Update', scrim()); await settle(40)
  await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true })) })
  await act(async () => { scrim().dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true })) })
  check('while updating, neither Escape nor a click beside the dialog closes it', () => { assert.ok(scrim()); assert.match(popover(), /Updating/) })
  check('while updating, New Game cannot start a game', () => {
    assert.ok(send(), 'the New Game composer is shown'); assert.equal(send().disabled, true)
    assert.match(send().getAttribute('title'), /hermretro is updating/)
  })
  await act(async () => { finish({ ok: true, unchanged: true }) }); await settle(40)
  check('afterwards it starts games again', () => {
    assert.equal(send().disabled, false); assert.match(send().getAttribute('title'), /Start (building|planning)/)
  })
  await tab('Games')
})
