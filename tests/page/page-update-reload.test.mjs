// An update made outside the page (a terminal, Capabilities > Plugins): Hermes runs older hermretro code than is on
// disk, and the page loads it by itself, once, without a restart: the hermretro profile's settings refreshed, the
// plugin switched off and on there once nothing is being built, the page refreshed. A linked checkout is left to the
// dev loop; a build makes it wait; Hermes asking for a restart and a failed load are said by the chip and its dialog.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, root, render, settle, click, check, answered, notLoaded, status, doctor, installAnswer }) => {
  const document = dom.window.document
  scenario.byMethod['plugin.hermretro.install'] = () => installAnswer({ state: 'idle' }).data
  const chip = () => document.querySelector('.cs-upd-chip')?.textContent ?? null
  const dialog = () => document.querySelector('.cs-upd-scrim')?.textContent.replace(/\s+/g, ' ') ?? ''
  const openDialog = async () => { await act(async () => { document.querySelector('.cs-upd-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) }) }
  const log = []
  let toggleAnswer = () => ({ ok: true, gateway_reloaded: true, restart_required: false })
  scenario.byMethod['session.active_list'] = () => { log.push('busy'); return { sessions: [] } }
  scenario.byMethod['plugins.manage'] = params => {
    log.push(params.action === 'toggle' ? `toggle:${params.enable}` : params.action)
    return params.action === 'toggle' ? toggleAnswer(params) : { plugins: [] }
  }
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => { log.push('finish'); return { ok: true } }
  const reconciled = []
  dom.window.hermesDesktop = { reconcileDesktopPlugins: async () => { reconciled.push(true); return [] } }
  const stale = (installedIn = { profile: 'default', linked: false }) =>
    answered({ ...status(), plugin: { version: '1.2.3', installed_in: installedIn }, restart_needed: true })
  const fresh = async ({ busy = [], installedIn } = {}) => {
    await act(async () => { root.render(null) })
    scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'games' }
    scenario.status = stale(installedIn); scenario.doctor = answered(doctor([])); scenario.install = installAnswer({ state: 'idle' })
    scenario['update-busy'] = answered(busy)
    log.length = 0; reconciled.length = 0
    await render(); await settle(40)
  }

  await fresh()
  check('the page loads it by itself: the hermretro profile refreshed from where hermretro is installed, then switched off and on there', () => {
    assert.deepEqual(log, ['busy', 'finish', 'busy', 'toggle:false', 'toggle:true'])
  })
  check('then the app refreshes the page, which is told how it went', () => {
    assert.equal(reconciled.length, 1)
    assert.equal(scenario.storage.update.result, 'updated'); assert.equal(scenario.storage.update.from, '1.2.3')
  })
  check('no banner says Hermes runs the old version', () => { assert.ok(!document.querySelector('.cs-repair')) })
  log.length = 0
  await render(); await settle(40)
  check('it is loaded once, never again in a loop', () => { assert.deepEqual(log, []) })

  // A linked checkout: the dev loop reloads it.
  await fresh({ installedIn: { profile: null, linked: true } })
  check('a linked checkout is left alone', () => { assert.deepEqual(log, []); assert.equal(chip(), null) })

  await fresh({ busy: ['Comet Drift'] })
  check('while a game is being built, nothing is loaded', () => { assert.ok(!log.some(entry => entry.startsWith('toggle'))) })
  scenario['update-busy'] = answered([])
  await render(); await settle(40)
  check('once the build finishes, it is loaded', () => { assert.deepEqual(log.slice(-2), ['toggle:false', 'toggle:true']) })

  toggleAnswer = () => ({ ok: true, gateway_reloaded: false, restart_required: true })
  await fresh()
  check('when Hermes can load it only on a restart, the chip and its dialog say to restart Hermes', () => {
    assert.equal(chip(), 'Restart to finish')
  })
  await openDialog()
  check('the dialog says what to do', () => { assert.match(dialog(), /The new version is installed\. Restart Hermes to finish loading it/) })

  toggleAnswer = params => (params.enable ? { ok: false, error: 'no' } : { ok: true })
  await fresh()
  check('a plugin left switched off is said by the chip', () => { assert.equal(chip(), 'Finish update') })
  scenario.status = notLoaded
  await render()
  check('the failure stays said once hermretro stops answering', () => { assert.equal(chip(), 'Finish update') })
  scenario.status = stale()
  await render()
  await openDialog()
  check('its dialog names what failed', () => { assert.match(dialog(), /hermretro could not be switched back on in the hermretro profile/) })
  toggleAnswer = () => ({ ok: true, gateway_reloaded: true, restart_required: false })
  log.length = 0
  await click('Finish update', document.querySelector('.cs-upd-scrim')); await settle(40)
  check('Finish update loads it again', () => { assert.deepEqual(log.slice(-2), ['toggle:false', 'toggle:true']) })

  // Installed into a profile the app cannot reach: its settings cannot be refreshed, so nothing is reloaded.
  await fresh({ installedIn: { profile: 'work', linked: false } })
  await openDialog()
  check('an install profile that cannot be reached fails the load before anything changes', () => {
    assert.match(dialog(), /Could not reach the work profile, where hermretro is installed/)
    assert.ok(!log.some(entry => entry.startsWith('toggle')))
    assert.equal(scenario.storage.update ?? null, null)
  })

  // The app cannot refresh the page's copy: reopening it does.
  dom.window.hermesDesktop = {}
  await fresh()
  await openDialog()
  check('when the page could not be refreshed, the dialog asks to quit and reopen Hermes', () => {
    assert.match(dialog(), /Quit and reopen Hermes to finish loading it/)
  })
  dom.window.hermesDesktop = { reconcileDesktopPlugins: async () => { reconciled.push(true); return [] } }

  // The app on the profile hermretro was installed into, the hermretro profile reached through its route: the
  // settings refresh goes to the install profile, the build checks and the switch off and on to the hermretro profile.
  const elsewhere = { ...stale().data, profile: { name: 'default', is_studio: false, studio: { name: 'hermretro', exists: true, installed: false, ours: false } } }
  const routed = []
  scenario.ambient = elsewhere
  scenario.routes = [{ profile: 'default', connectionId: 'local' }, { profile: 'hermretro', connectionId: 'local' }]
  scenario.requestProfileHook = (route, method, params) => {
    routed.push(`${route.profile}:${method === 'plugins.manage' ? `toggle:${params.enable}` : method}`)
    return method === 'session.active_list' ? { sessions: [] } : { ok: true, gateway_reloaded: true, restart_required: false }
  }
  await act(async () => { root.render(null) })
  scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'games' }
  scenario.status = answered(elsewhere); log.length = 0
  await render(); await settle(40)
  check('each step goes to its profile', () => {
    assert.deepEqual(log, ['finish'])
    assert.deepEqual(routed, ['hermretro:session.active_list', 'hermretro:session.active_list', 'hermretro:toggle:false', 'hermretro:toggle:true'])
  })
})
