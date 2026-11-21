// Updating hermretro from its own page (app/update/): the header chip when Hermes found a newer version, the Update
// button's steps (Hermes's update where the plugin was installed, the hermretro profile reloaded, the page refreshed),
// what the reloaded page says, the security-check review, a failure, Later, and the Setup page's version row.
// Run alone: node tests/page/page-update.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, root, render, settle, click, button, check, shows, tab, answered, status, doctor, installAnswer }) => {
  const document = dom.window.document
  const chip = () => document.querySelector('.cs-upd-chip')
  const popover = () => document.querySelector('.cs-upd-pop')?.textContent.replace(/\s+/g, ' ') ?? ''
  const openChip = async () => { await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) }) }
  // The app on the default profile, where the plugin was installed; the hermretro profile answers the page.
  const installed = { profile: 'default', linked: false }
  const base = (extra = {}) => ({ ...status(), plugin: { version: '1.2.3', installed_in: installed }, ...extra })
  const check_ = (row, target = { route: null, profile: 'default' }) => answered({ target, row: { name: 'hermretro', key: 'hermretro', ...row } })
  const calls = []
  let updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true, restart_required: false })
  scenario.byMethod['plugins.manage'] = params => {
    calls.push(params)
    if (params.action === 'update') return updateAnswer(params)
    if (params.action === 'toggle') return { ok: true, unchanged: false, gateway_reloaded: true, restart_required: false }
    return { plugins: [] }
  }
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => { calls.push({ action: 'finish' }); return { ok: true } }
  scenario.byMethod['session.active_list'] = () => ({ sessions: [] })  // nothing is being built (page-update-busy covers that)
  const reconciled = []
  dom.window.hermesDesktop = { reconcileDesktopPlugins: async () => { reconciled.push(true); return [] } }
  const fresh = async (storage = {}) => {
    await act(async () => { root.render(null) })
    scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'prompts', ...storage }
    scenario.status = answered(base()); scenario.doctor = answered(doctor([])); scenario.install = installAnswer({ state: 'idle' })
    scenario.notices.length = 0; calls.length = 0; reconciled.length = 0
    await render()
  }

  // Nothing new: no chip, and the Setup page says the version is current.
  scenario['plugin-update'] = check_({ update_available: undefined })
  await fresh()
  check('no chip while Hermes has no newer version', () => { assert.ok(!chip()) })
  check('the update check asks the profile the plugin was installed into, every 30 minutes', () => {
    const query = scenario.queries.filter(entry => entry.key === 'plugin-update').at(-1)
    assert.deepEqual(query.queryKey, ['hermretro', 'plugin-update', 'default']); assert.equal(query.enabled, true)
    assert.equal(query.refetchInterval, 30 * 60_000)
  })
  await tab('Setup')
  check('Setup lists the hermretro version as up to date', () => { shows(/hermretro1\.2\.3 · up to date/) })

  // A newer version: the chip, then the popover.
  scenario['plugin-update'] = check_({ update_available: true, update_target: 'abc123' })
  await fresh({ page: 'setup' })
  check('Setup offers the update in the hermretro row', () => { shows(/1\.2\.3 · a new version is ready/); assert.ok(button('Update')) })
  check('the header shows an "Update ready" chip', () => { assert.ok(chip()); assert.equal(chip().textContent, 'Update ready') })
  await openChip()
  check('the chip opens the popover with Update now, What\'s new and Later', () => {
    assert.match(popover(), /A new version is ready/); assert.match(popover(), /Installed1\.2\.3/)
    assert.ok(button('Update now')); assert.ok(button("What's new")); assert.ok(button('Later'))
  })

  // Update now: Hermes's update, the hermretro profile refreshed and reloaded, then the page refreshed.
  await click('Update now')
  await settle(40)
  check('Update runs Hermes\'s update, refreshes the hermretro profile, then switches the plugin off and on there', () => {
    assert.deepEqual(calls.map(call => call.action === 'toggle' ? `toggle:${call.enable}` : call.action), ['update', 'finish', 'toggle:false', 'toggle:true'])
    assert.equal(calls[0].name, 'hermretro')
  })
  check('it asks the app to refresh the page\'s own copy, and remembers the update for the reloaded page', () => {
    assert.equal(reconciled.length, 1)
    assert.equal(scenario.storage.update.result, 'updated'); assert.equal(scenario.storage.update.restart, false)
  })
  check('until the app reloads the page, the chip says it is updated', () => { assert.equal(chip().textContent, 'Updated') })

  // The page has not adopted the hermretro profile (the app is on another profile that answers): the profile is
  // still found among the app's routes and reloaded there.
  const elsewhere = { ...base(), profile: { name: 'default', is_studio: false, studio: { name: 'hermretro', exists: true, installed: false, ours: false } } }
  scenario.ambient = elsewhere
  scenario.routes = [{ profile: 'default', connectionId: 'local' }, { profile: 'hermretro', connectionId: 'local' }]
  const viaRoute = []
  const realRequestProfile = scenario.requestProfileHook
  scenario.requestProfileHook = (route, method, params) => { viaRoute.push([route.profile, method, params?.action, params?.enable]); return { ok: true, gateway_reloaded: true } }
  await act(async () => { root.render(null) })
  scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'prompts' }
  scenario.status = answered(elsewhere); calls.length = 0; reconciled.length = 0
  await render()
  await openChip(); await click('Update now'); await settle(40)
  check('an hermretro profile the page never adopted is still found and reloaded through its route', () => {
    assert.deepEqual(viaRoute.filter(([, method]) => method === 'plugins.manage'), [['hermretro', 'plugins.manage', 'toggle', false], ['hermretro', 'plugins.manage', 'toggle', true]])
    assert.equal(calls[0].action, 'update')
  })
  scenario.requestProfileHook = realRequestProfile; scenario.ambient = null; scenario.routes = []

  // The page the app loads next says how it went, once.
  const marker = scenario.storage.update
  await fresh({ update: marker })
  check('the reloaded page announces the update and forgets the marker', () => {
    assert.deepEqual(scenario.notices.at(-1), { kind: 'success', message: 'hermretro is up to date. Your games and chats are kept.' })
    assert.equal(scenario.storage.update, null)
  })
  await fresh({ update: { result: 'updated', restart: false, at: Date.now() - 60 * 60_000 } })
  check('an old marker is not announced', () => { assert.equal(scenario.notices.length, 0) })

  // Something only a restart loads.
  updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: false, restart_required: true })
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  check('when Hermes could not load it, the chip asks for a restart', () => {
    assert.equal(chip().textContent, 'Restart to finish'); assert.match(popover(), /Quit and reopen Hermes/)
  })

  // The security check wants a yes first: shown with Hermes's findings, retried with force.
  updateAnswer = params => params.force
    ? { ok: true, unchanged: false, gateway_reloaded: true }
    : { ok: false, scan_blocked: true, scan_verdict: 'caution', scan_findings: [{ severity: 'high', file: 'x.yml', line: 3, description: 'something' }] }
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  check('a caution scan shows the findings and changes nothing yet', () => {
    assert.match(popover(), /Review the new version/); assert.match(popover(), /HIGH x\.yml:3 something/)
    assert.deepEqual(calls.map(call => call.action), ['update'])
  })
  await click('Install anyway'); await settle(40)
  check('Install anyway retries with force', () => { assert.equal(calls.find(call => call.force)?.action, 'update') })

  // A dangerous verdict is never offered.
  updateAnswer = () => ({ ok: false, scan_blocked: true, scan_verdict: 'dangerous', scan_findings: [] })
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  check('a dangerous verdict fails without an Install anyway', () => {
    assert.equal(chip().textContent, 'Update failed'); assert.ok(!button('Install anyway'))
  })

  // A failure: the reason, Try again, and the way to Hermes's own Plugins page.
  // Hermes's own refusal: a JSON-RPC error with a code (4021, a failed pull).
  updateAnswer = () => { throw Object.assign(new Error('GitHub could not be reached.'), { code: 4021 }) }
  await fresh()
  await openChip(); await click('Update now'); await settle(40)
  check('a failed update says why and that nothing changed', () => {
    assert.match(popover(), /GitHub could not be reached\. Nothing was changed; you are still on 1\.2\.3\./)
    assert.ok(button('Try again'))
  })
  await click('Open Capabilities')
  check('the fallback opens hermretro in Capabilities > Plugins', () => {
    assert.equal(scenario.navigations.at(-1), '/capabilities?tab=plugins&plugin=hermretro')
  })

  // Later hides the chip for this version only.
  await fresh()
  await openChip(); await click('Later')
  check('Later hides the chip and remembers which version it was', () => { assert.ok(!chip()); assert.equal(scenario.storage.updateLater, 'abc123') })
  scenario['plugin-update'] = check_({ update_available: true, update_target: 'def456' })
  await fresh({ updateLater: 'abc123' })
  check('a newer version after Later shows the chip again', () => { assert.ok(chip()) })

  // First-time setup has its own header: the chip is there too (a release may fix the install itself).
  scenario['plugin-update'] = check_({ update_available: true, update_target: 'def456' })
  await act(async () => { root.render(null) })
  scenario.storage = {}
  scenario.status = answered(base({ profile: { name: 'default', is_studio: false, studio: { name: 'hermretro', exists: false, installed: false, ours: false } } }))
  scenario.doctor = answered(doctor(['cli']))
  await render()
  check('the first-time setup header shows the update chip too', () => {
    assert.ok(document.querySelector('.cs-onb-steps')); assert.equal(chip()?.textContent, 'Update ready')
  })

  // A linked development checkout: Hermes does not update it, so there is no check and no chip.
  await act(async () => { root.render(null) })
  scenario['plugin-update'] = undefined
  scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'setup' }
  scenario.status = answered(base({ plugin: { version: '1.2.3', installed_in: { profile: null, linked: true } } }))
  scenario.doctor = answered(doctor([]))
  await render()
  check('a linked checkout gets no update check and says how it is updated', () => {
    assert.equal(scenario.queries.filter(entry => entry.key === 'plugin-update').at(-1).enabled, false)
    shows(/a linked checkout: update it with git/); assert.ok(!chip())
  })
})
