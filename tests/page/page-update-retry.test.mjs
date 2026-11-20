// What happens when an update needs another go (app/update/): every yes the user gave Hermes is kept for the next try,
// a check that fails after Hermes installed the new version is never read as "nothing is building", and an update that
// installed but did not finish is shown as such (never "nothing was changed") and finishes with Finish update even
// though Hermes then answers "unchanged".
// Run alone: node tests/page/page-update-retry.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, root, render, settle, click, button, check, holdTimers, answered, status, doctor, installAnswer }) => {
  const document = dom.window.document
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
    scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'home', ...storage }
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
