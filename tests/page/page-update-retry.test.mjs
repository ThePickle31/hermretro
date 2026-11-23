// What happens when an update needs another go (app/update/): every yes the user gave Hermes is kept for the next try,
// a check that fails after Hermes installed the new version is never read as "nothing is building", and an update that
// installed but did not finish is shown as such (never "nothing was changed") and finishes with Finish update even
// though Hermes then answers "unchanged".
// Run alone: node tests/page/page-update-retry.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, root, render, settle, click, button, check, holdTimers, answered, status, doctor, installAnswer }) => {
  const document = dom.window.document
  scenario.byMethod['plugin.hermretro.install'] = () => installAnswer({ state: 'idle' }).data
  const chip = () => document.querySelector('.cs-upd-chip')
  const popover = () => document.querySelector('.cs-upd-pop')?.textContent.replace(/\s+/g, ' ') ?? ''
  const openChip = async () => { await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) }) }
  const log = []
  const updates = []
  let sessions = () => []
  let updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true })
  let toggleOn = () => ({ ok: true, gateway_reloaded: true })
  scenario.byMethod['session.active_list'] = () => { log.push('busy'); return { sessions: sessions() } }
  scenario.byMethod['plugins.manage'] = params => {
    log.push(params.action === 'toggle' ? `toggle:${params.enable}` : params.action)
    if (params.action === 'update') { updates.push(params); return updateAnswer(params) }
    if (params.action === 'toggle' && params.enable) return toggleOn()
    return { ok: true, gateway_reloaded: true }
  }
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => { log.push('finish'); return { ok: true } }
  dom.window.hermesDesktop = { reconcileDesktopPlugins: async () => [] }
  const row = available => answered({ target: { route: null, profile: 'default' }, row: { name: 'hermretro', update_available: available, update_target: 'abc' } })
  const fresh = async (storage = {}, available = true) => {
    await act(async () => { root.render(null) })
    scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'games', ...storage }
    scenario.status = answered({ ...status(), plugin: { version: '1.2.3', installed_in: { profile: 'default', linked: false } } })
    scenario.doctor = answered(doctor([])); scenario.install = installAnswer({ state: 'idle' })
    scenario['plugin-update'] = row(available); scenario['update-busy'] = answered([])
    log.length = 0; updates.length = 0
    await render()
  }

  // Both of Hermes's questions in one update: each yes is kept for the next try.
  updateAnswer = params => !params.force
    ? { ok: false, scan_blocked: true, scan_verdict: 'caution', scan_findings: [{ severity: 'high', file: 'a.yml', line: 1, description: 'x' }] }
    : !params.accept_capabilities
      ? { ok: false, consent_required: true, delta_lines: ['+ tool chromatic_new'] }
      : { ok: true, unchanged: false, gateway_reloaded: true }
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  await click('Install anyway'); await settle(40)
  check('after the scan review, Hermes asks about the widened plugin', () => { assert.match(popover(), /adds to what hermretro can do/); assert.match(popover(), /\+ tool chromatic_new/) })
  await click('Install anyway'); await settle(40)
  check('the last try carries both answers, so the update goes through', () => {
    assert.deepEqual(updates.map(params => [Boolean(params.force), Boolean(params.accept_capabilities)]), [[false, false], [true, false], [true, true]])
    assert.equal(chip().textContent, 'Updated')
  })

  // Switching hermretro back on in the hermretro profile fails: installed, not finished.
  updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true })
  toggleOn = () => ({ ok: false })
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  check('an update that installed but could not finish says so, never "nothing was changed"', () => {
    assert.equal(chip().textContent, 'Finish update')
    assert.match(popover(), /The new version is installed, but hermretro could not be switched back on in the hermretro profile/)
    assert.ok(!/Nothing was changed/.test(popover())); assert.ok(scenario.storage.updatePending)
  })
  // The page is reopened: Hermes no longer offers an update (it is installed), the half-done one is still shown.
  await fresh({ updatePending: scenario.storage.updatePending }, undefined)
  check('a reopened page still shows the unfinished update', () => { assert.equal(chip()?.textContent, 'Finish update') })
  updateAnswer = () => ({ ok: true, unchanged: true })
  toggleOn = () => ({ ok: true, gateway_reloaded: true })
  await openChip(); await click('Finish update', document.querySelector('.cs-upd-pop')); await settle(40)
  check('Finish update runs the remaining steps although Hermes answers "unchanged"', () => {
    assert.deepEqual(log, ['busy', 'update', 'finish', 'busy', 'toggle:false', 'toggle:true'])
    assert.equal(chip().textContent, 'Updated'); assert.equal(scenario.storage.updatePending, null)
  })

  // The profile settings step fails, by an error or by its answer: installed, not finished; Finish update redoes it.
  updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true })
  for (const [form, answer] of [['an error', () => { throw new Error('backend gone') }], ['ok: false', () => ({ ok: false, error: 'profile locked' })]]) {
    scenario.byMethod['plugin.hermretro.studio_profile'] = () => { log.push('finish'); return answer() }
    await fresh()
    await openChip(); await click('Update now'); await settle(40)
    check(`a profile settings step that fails with ${form} leaves the update unfinished and reloads nothing`, () => {
      assert.equal(chip().textContent, 'Finish update'); assert.match(popover(), /the hermretro profile's settings were not updated/)
      assert.ok(!log.includes('toggle:false')); assert.ok(scenario.storage.updatePending)
    })
  }
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => { log.push('finish'); return { ok: true } }
  updateAnswer = () => ({ ok: true, unchanged: true })
  if (!document.querySelector('.cs-upd-pop')) await openChip()
  log.length = 0
  await click('Finish update', document.querySelector('.cs-upd-pop')); await settle(40)
  check('Finish update redoes the profile settings step, then reloads', () => {
    assert.deepEqual(log, ['busy', 'update', 'finish', 'busy', 'toggle:false', 'toggle:true']); assert.equal(chip().textContent, 'Updated')
  })

  // Hermes installs the new version but its answer is lost (no JSON-RPC code: a timeout or a dropped connection).
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => { log.push('finish'); return { ok: true } }
  updateAnswer = () => { throw new Error('request timed out') }
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  check('a lost answer from Hermes leaves the update unfinished, never "nothing was changed"', () => {
    assert.equal(chip().textContent, 'Finish update'); assert.match(popover(), /Hermes's answer was lost \(request timed out\)/)
    assert.ok(scenario.storage.updatePending); assert.ok(!/Nothing was changed/.test(popover()))
  })
  updateAnswer = () => ({ ok: true, unchanged: true })
  log.length = 0
  if (!document.querySelector('.cs-upd-pop')) await openChip()
  await click('Finish update', document.querySelector('.cs-upd-pop')); await settle(40)
  check('the retry finds it installed ("unchanged") and still finishes every step', () => {
    assert.deepEqual(log, ['busy', 'update', 'finish', 'busy', 'toggle:false', 'toggle:true']); assert.equal(chip().textContent, 'Updated')
  })
  // A Hermes refusal (with a code) changed nothing: a plain failure that forgets the marker.
  updateAnswer = () => { throw Object.assign(new Error('Plugin is being updated by another process'), { code: 4021 }) }
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  check('a refusal from Hermes is a plain failure and leaves nothing pending', () => {
    assert.equal(chip().textContent, 'Update failed'); assert.equal(scenario.storage.updatePending, null)
  })
  // The Setup row says where the update stands, never "up to date" while one is outstanding.
  scenario.storage.page = 'setup'
  await act(async () => { root.render(null) }); scenario['plugin-update'] = row(true); await render()
  await openChip(); await click('Update now'); await settle(40)
  check('after a failed update the Setup row does not say "up to date"', () => {
    assert.match(document.querySelector('.cs-facts').textContent, /the update did not go through/)
    assert.ok(!/up to date/.test(document.querySelector('.cs-facts').textContent))
  })
  updateAnswer = () => ({ ok: false, scan_blocked: true, scan_verdict: 'caution', scan_findings: [] })
  await fresh({ page: 'setup' })
  await openChip(); await click('Update now', document.querySelector('.cs-upd-pop')); await settle(40)
  check('while Hermes waits for an answer the Setup row says so', () => {
    assert.match(document.querySelector('.cs-facts').textContent, /the update waits for your answer in the header/)
  })

  // The app cannot list its profiles while the status says the hermretro profile exists: not read as "no profile".
  updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true })
  await fresh()
  scenario.status = answered({ ...status(), plugin: { version: '1.2.3', installed_in: { profile: 'default', linked: false } },
    profile: { name: 'default', is_studio: false, studio: { name: 'hermretro', exists: true, installed: true, ours: true } } })
  scenario.ambient = null
  scenario.routesError = new Error('connection registry unavailable')
  await act(async () => { root.render(null) }); await render()
  await openChip(); await click('Update now'); await settle(40)
  check('a failed profile lookup stops the update before anything changes', () => {
    assert.ok(!log.includes('update'), log.join(', ')); assert.equal(chip().textContent, 'Update failed')
    assert.match(popover(), /Could not reach the hermretro profile \(connection registry unavailable\)/)
  })
  scenario.routesError = null
  // The lookup works but lists no hermretro profile although the status says there is one.
  scenario.routes = [{ profile: 'default', connectionId: 'local' }]
  log.length = 0
  await act(async () => { root.render(null) }); await render()
  await openChip(); await click('Update now'); await settle(40)
  check('a hermretro profile the status reports but the app does not list stops the update too', () => {
    assert.ok(!log.includes('update'), log.join(', ')); assert.match(popover(), /the hermretro profile is not reachable right now/)
  })
  scenario.routes = []

  // A build starts during the download, then the check fails: never read as idle, so no reload.
  updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true })
  let looks = 0
  sessions = () => {
    looks += 1
    if (looks === 1) return []
    if (looks === 2) return [{ title: 'Comet Drift', status: 'working' }]
    throw new Error('profile not reachable')
  }
  await fresh()
  const clock = holdTimers()
  await openChip(); await click('Update now'); await settle(40)
  for (let round = 0; round < 8 && log.filter(entry => entry === 'busy').length < 7; round++) await clock.fire()
  check('a failed check after a busy one never reloads the hermretro profile', () => {
    assert.ok(!log.includes('toggle:false'), `no reload: ${log.join(', ')}`)
    assert.equal(chip().textContent, 'Finish update', log.join(',')); assert.match(popover(), /Could not check whether a game is being built/)
  })
})
