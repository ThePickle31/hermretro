// The Reload banner (app/update/reload-banner.js): Hermes runs older hermretro code than is on disk (an update made
// outside the page), and Reload loads it without a restart: the hermretro profile's settings refreshed, the plugin
// switched off and on there once nothing is being built, the page refreshed. A build refuses it; Hermes asking for a
// restart and a failed reload are both said in the banner.
// Run alone: node tests/page/page-update-reload.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, root, render, settle, click, button, check, answered, status, doctor, installAnswer }) => {
  const document = dom.window.document
  const banner = () => document.querySelector('.cs-repair')?.textContent.replace(/\s+/g, ' ') ?? ''
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
    await render()
  }

  await fresh()
  check('the banner says Hermes runs the old version and offers Reload, not a restart', () => {
    assert.equal(banner(), 'hermretro was updated, but Hermes is still running the old version.Reload')
    assert.ok(button('Reload') && !button('Reload').disabled)
  })
  await click('Reload'); await settle(40)
  check('Reload refreshes the hermretro profile from where hermretro is installed, then switches it off and on there', () => {
    assert.deepEqual(log, ['busy', 'finish', 'busy', 'toggle:false', 'toggle:true'])
  })
  check('then the app refreshes the page', () => { assert.equal(reconciled.length, 1) })

  // A linked checkout: Hermes does not install it, so there are no settings to refresh; the reload is the same.
  await fresh({ installedIn: { profile: null, linked: true } })
  await click('Reload'); await settle(40)
  check('a linked checkout is reloaded without the settings refresh', () => {
    assert.deepEqual(log, ['busy', 'busy', 'toggle:false', 'toggle:true'])
  })

  await fresh({ busy: ['Comet Drift'] })
  check('while a game is being built, Reload waits and says why', () => {
    assert.match(banner(), /A game is being built in "Comet Drift"\. You can reload when it finishes\./)
    assert.equal(button('Reload').disabled, true)
  })

  toggleAnswer = () => ({ ok: true, gateway_reloaded: false, restart_required: true })
  await fresh()
  await click('Reload'); await settle(40)
  check('when Hermes can load it only on a restart, the banner says to restart Hermes', () => {
    assert.equal(banner(), 'hermretro was updated. Restart Hermes to finish loading it.')
    assert.ok(!button('Reload'))
  })

  toggleAnswer = params => (params.enable ? { ok: false, error: 'no' } : { ok: true })
  await fresh()
  await click('Reload'); await settle(40)
  check('a plugin left switched off is said, with Try again', () => {
    assert.match(banner(), /Reload did not finish: hermretro could not be switched back on in the hermretro profile\./)
    assert.ok(document.querySelector('.cs-repair.bad')); assert.ok(button('Try again'))
  })
  toggleAnswer = () => ({ ok: true, gateway_reloaded: true, restart_required: false })
  log.length = 0
  await click('Try again'); await settle(40)
  check('Try again reloads again', () => { assert.deepEqual(log.slice(-2), ['toggle:false', 'toggle:true']) })
})
