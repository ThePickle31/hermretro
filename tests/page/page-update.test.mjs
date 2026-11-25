// Updating hermretro from its own page (app/update/): the header chip when Hermes found a newer version, the Update
// button's steps (Hermes's update where the plugin was installed, the hermretro profile reloaded, the page refreshed),
// what the reloaded page says, the security-check review, a failure, the corner card, the release notes, and the Setup
// page's version row.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, root, render, settle, click, button, check, shows, tab, answered, status, doctor, installAnswer }) => {
  const document = dom.window.document
  scenario.byMethod['plugin.hermretro.install'] = () => installAnswer({ state: 'idle' }).data
  const chip = () => document.querySelector('.cs-upd-chip')
  const scrim = () => document.querySelector('.cs-upd-scrim')
  const popover = () => scrim()?.textContent.replace(/\s+/g, ' ') ?? ''
  // The dialog's own buttons (the corner card and the Setup row have an Update too).
  const inDialog = label => [...(scrim()?.querySelectorAll('button') ?? [])].find(node => node.textContent === label)
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
    scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'games', ...storage }
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
  check('the chip opens the dialog with Update and Later, and What\'s new while there are no notes', () => {
    assert.match(popover(), /A new version is ready/)
    assert.ok(inDialog('Update')); assert.match(popover(), /What's new/); assert.ok(inDialog('Later'))
  })

  // Update now: Hermes's update, the hermretro profile refreshed and reloaded, then the page refreshed.
  await click('Update', scrim())
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
  scenario.storage = { setup: { onboarded: true, hardwareSkipped: true }, page: 'games' }
  scenario.status = answered(elsewhere); calls.length = 0; reconciled.length = 0
  await render()
  await openChip(); await click('Update', scrim()); await settle(40)
  check('an hermretro profile the page never adopted is still found and reloaded through its route', () => {
    assert.deepEqual(viaRoute.filter(([, method]) => method === 'plugins.manage'), [['hermretro', 'plugins.manage', 'toggle', false], ['hermretro', 'plugins.manage', 'toggle', true]])
    assert.equal(calls[0].action, 'update')
  })
  scenario.requestProfileHook = realRequestProfile; scenario.ambient = null; scenario.routes = []

  // The page the app loads next says how it went, once.
  const marker = scenario.storage.update
  await fresh({ update: marker })
  check('the reloaded page opens the dialog on the update and forgets the marker', () => {
    assert.match(popover(), /You’re on 1\.2\.3/); assert.match(popover(), /Ready to use/)
    assert.equal(scenario.notices.length, 0); assert.equal(scenario.storage.update, null)
  })
  await click('Done', scrim())
  check('Done closes it and the chip stops saying Updated', () => { assert.ok(!scrim()); assert.notEqual(chip()?.textContent, 'Updated') })
  await fresh({ update: { result: 'updated', restart: false, at: Date.now() - 60 * 60_000 } })
  check('an old marker is not announced', () => { assert.ok(!scrim()) })

  // Something only a restart loads.
  updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: false, restart_required: true })
  await fresh()
  await openChip(); await click('Update', scrim()); await settle(40)
  check('when Hermes could not load it, the chip asks for a restart of Hermes', () => {
    assert.equal(chip().textContent, 'Restart to finish'); assert.match(popover(), /installed\. Restart Hermes to finish loading it/)
  })

  // Only the page's copy is old (the app cannot refresh it): reopening the app loads it.
  updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true, restart_required: false })
  const reconcile = dom.window.hermesDesktop
  dom.window.hermesDesktop = {}
  await fresh()
  await openChip(); await click('Update', scrim()); await settle(40)
  check('when only the page could not be refreshed, the chip asks to quit and reopen Hermes', () => {
    assert.match(popover(), /installed\. Quit and reopen Hermes to finish loading it/)
  })
  dom.window.hermesDesktop = reconcile

  // The security check wants a yes first: shown with Hermes's findings, retried with force.
  updateAnswer = params => params.force
    ? { ok: true, unchanged: false, gateway_reloaded: true }
    : { ok: false, scan_blocked: true, scan_verdict: 'caution', scan_findings: [{ severity: 'high', file: 'x.yml', line: 3, description: 'something' }] }
  await fresh()
  await openChip(); await click('Update', scrim()); await settle(40)
  check('a caution scan shows the findings and changes nothing yet', () => {
    assert.match(popover(), /Review the new version/); assert.match(popover(), /HIGH x\.yml:3 something/)
    assert.deepEqual(calls.map(call => call.action), ['update'])
  })
  await click('Install anyway'); await settle(40)
  check('Install anyway retries with force', () => { assert.equal(calls.find(call => call.force)?.action, 'update') })

  // A dangerous verdict is never offered.
  updateAnswer = () => ({ ok: false, scan_blocked: true, scan_verdict: 'dangerous', scan_findings: [] })
  await fresh()
  await openChip(); await click('Update', scrim()); await settle(40)
  check('a dangerous verdict fails without an Install anyway', () => {
    assert.equal(chip().textContent, 'Update failed'); assert.ok(!button('Install anyway'))
  })

  // A failure: the reason, Try again, and the way to Hermes's own Plugins page.
  // Hermes's own refusal: a JSON-RPC error with a code (4021, a failed pull).
  updateAnswer = () => { throw Object.assign(new Error('GitHub could not be reached.'), { code: 4021 }) }
  await fresh()
  await openChip(); await click('Update', scrim()); await settle(40)
  check('a failed update says why and that nothing changed', () => {
    assert.match(popover(), /GitHub could not be reached\. Nothing was changed; you are still on 1\.2\.3\./)
    assert.ok(button('Try again'))
  })
  await click('Open Capabilities')
  check('the fallback opens hermretro in Capabilities > Plugins', () => {
    assert.equal(scenario.navigations.at(-1), '/capabilities?tab=plugins&plugin=hermretro')
  })

  // The corner card: once per version. Later, or a click anywhere else, puts it away; the chip stays.
  const card = () => document.querySelector('.cs-upd-card')
  await fresh()
  check('a new version shows the corner card', () => { assert.ok(card()); assert.ok(!scrim()) })
  await click('Later', card())
  check('Later puts the card away for this version and keeps the chip', () => {
    assert.ok(!card()); assert.ok(chip()); assert.equal(scenario.storage.updateLater, 'abc123')
  })
  await fresh({ updateLater: 'abc123' })
  check('a reopened page does not show it again for that version', () => { assert.ok(!card()); assert.ok(chip()) })
  scenario['plugin-update'] = check_({ update_available: true, update_target: 'def456' })
  await fresh({ updateLater: 'abc123' })
  check('a newer version shows the card again', () => { assert.ok(card()) })
  await act(async () => { document.body.dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true })) })
  check('a click anywhere else puts it away like Later', () => { assert.ok(!card()); assert.equal(scenario.storage.updateLater, 'def456') })
  updateAnswer = () => ({ ok: true, unchanged: false, gateway_reloaded: true, restart_required: false })
  await fresh()
  await click('Update', card()); await settle(40)
  check('the card\'s Update runs the update in the full dialog', () => {
    assert.ok(!card()); assert.equal(calls[0]?.action, 'update'); assert.equal(chip().textContent, 'Updated')
  })

  // The releases: what each version newer than the installed one changed, newest first, and the version it goes to.
  const notes = [
    { version: '1.2.5', date: '2026-11-24T00:00:00Z', notes: [{ kind: 'new', text: 'Skins for the player' }, { kind: 'fixed', text: 'Builds keep one ROM' }] },
    { version: '1.2.4', date: '2026-11-20T00:00:00Z', notes: [{ kind: 'fixed', text: 'The player plays the newest build' }] },
    { version: '1.2.3', date: '2026-11-10T00:00:00Z', notes: [{ kind: 'new', text: 'Already installed' }] }
  ]
  scenario.releases = answered({ ok: true, releases: notes })
  scenario['plugin-update'] = check_({ update_available: undefined })
  await fresh()
  check('a release newer than the installed one shows the card even before Hermes\'s own check finds it', () => {
    const text = card().textContent.replace(/\s+/g, ' ')
    assert.match(text, /1\.2\.3.*1\.2\.5/); assert.match(text, /NewSkins for the player/); assert.match(text, /The player plays the newest build/)
    assert.ok(!/Already installed/.test(text))
  })
  check('the releases are asked every 30 minutes', () => {
    const query = scenario.queries.filter(entry => entry.key === 'releases').at(-1)
    assert.equal(query.enabled, true); assert.equal(query.refetchInterval, 30 * 60_000)
  })
  await openChip()
  check('the chip opens the full dialog with the same notes and no What\'s new link', () => {
    assert.ok(!card()); assert.match(popover(), /v1\.2\.5/); assert.match(popover(), /v1\.2\.4/); assert.ok(!/What's new/.test(popover()))
  })
  await fresh({ update: { result: 'updated', restart: false, at: Date.now(), from: '1.2.1' } })
  check('after an update the dialog lists what the releases it brought changed', () => {
    assert.match(popover(), /You’re on 1\.2\.3/); assert.match(popover(), /Already installed/); assert.ok(!/Skins for the player/.test(popover()))
  })
  scenario.releases = undefined

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
