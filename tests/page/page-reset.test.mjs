// The factory reset on hermretro's settings page (Settings → Plugins → hermretro): choose what to keep, confirm by
// typing "reset", then the steps in order (the backend's parts, the studio profile through Hermes, the update) and how it ended; Reload & restart gateway afterwards. Nothing is deleted while a game is being built, and
// the studio profile stays when hermretro is installed in it.
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, settingsPages, mount, settle, click, check, typeInto }) => {
  const document = dom.window.document
  const STUDIO = { connectionId: 'local', profile: 'hermretro', targetProfile: 'hermretro' }
  const log = []
  let active = []
  let installedIn = { profile: 'default', linked: false }
  const plan = {
    ok: true,
    parts: {
      games: { bytes: 130e6, count: 14 }, history: { bytes: 31e6 }, chats: { count: 2 }, settings: {},
      toolchain: { bytes: 2.4e9, custom: false }, logs: { bytes: 15e6 }
    }
  }
  scenario.routes = [STUDIO]
  scenario.byMethod['plugin.hermretro.status'] = () => ({ ok: true, plugin: { version: '1.2.3', installed_in: installedIn }, profile: { studio: { exists: true } } })
  scenario.byMethod['plugins.manage'] = params => { log.push(`update:${params.action}`); return { ok: true, unchanged: true } }
  scenario.requestProfileHook = (route, method, params) => {
    if (method === 'plugin.hermretro.reset_plan') return plan
    if (method === 'plugin.hermretro.reset') { log.push(params.part); return { ok: true, removed_bytes: 1e6 } }
    if (method === 'session.active_list') return { sessions: active }
    throw new Error(`unexpected ${method}`)
  }
  const dialog = () => document.querySelector('[role=dialog]')
  const said = () => dialog()?.textContent.replace(/\s+/g, ' ') ?? ''
  const choice = label => [...document.querySelectorAll('[data-segmented]')].find(node => node.getAttribute('aria-label') === label)
  const chosen = label => choice(label).querySelector('[aria-pressed=true]').textContent
  const pick = async (label, value) => {
    const button = [...choice(label).querySelectorAll('button')].find(node => node.textContent === value)
    await act(async () => { button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  }
  const open = async () => {
    await click('Factory reset…'); await settle(40)
  }
  const confirm = async () => {
    await click('Continue', dialog())
    await typeInto(dialog().querySelector('input'), 'reset')
    await click('Reset', dialog()); await settle(60)
  }

  check('hermretro adds one settings page', () => { assert.equal(settingsPages.length, 1) })
  const page = await mount(settingsPages[0])
  await open()
  check('the dialog lists every part with what it holds; only Games is kept at first', () => {
    assert.match(said(), /Games14 games · 130 MB/)
    assert.match(said(), /Studio chats2 chats · Deleted with the studio profile/)
    assert.match(said(), /Toolchain & engine2\.4 GB/)
    assert.deepEqual(['Games', 'Build history', 'Toolchain & engine'].map(chosen), ['Keep', 'Delete', 'Delete'])
  })
  await pick('Studio profile', 'Keep'); await pick('Games', 'Delete')
  check('deleting Games takes build history with it', () => {
    assert.match(said(), /Build history31\.0 MB · Deleted with Games/)
    assert.ok(choice('Build history').querySelector('button').disabled)
  })
  await pick('Games', 'Keep')
  await click('Continue', dialog())
  check('the confirm step says what goes and what stays, and waits for the word', () => {
    assert.match(said(), /Delete.*Build history.*Studio chats.*Toolchain & engine/)
    assert.match(said(), /Keep.*Games.*Studio profile/)
    assert.ok([...dialog().querySelectorAll('button')].find(node => node.textContent === 'Reset').disabled)
  })
  await typeInto(dialog().querySelector('input'), 'reset')
  await click('Reset', dialog()); await settle(60)
  check('the backend parts go first, in order, then the update', () => {
    assert.deepEqual(log, ['stop', 'history', 'chats', 'settings', 'toolchain', 'logs', 'update:update'])
    assert.ok(!scenario.calls.some(call => call[0] === 'deleteProfile'))
  })
  check('the done screen says what was deleted, kept and the version', () => {
    assert.match(said(), /hermretro is reset/)
    assert.match(said(), /Deleted5\.0 MB/)
    assert.match(said(), /KeptGames, Studio profile/)
    assert.match(said(), /Version1\.2\.3, up to date/)
  })
  await click('Reload & restart gateway', dialog()); await settle()
  check('Reload & restart gateway restarts Hermes\'s gateway', () => { assert.ok(scenario.calls.some(call => call[0] === 'restartGateway')) })
  await click('Close', dialog())

  log.length = 0
  await open()
  check('deleting the studio profile takes its chats and build history', () => {
    assert.equal(chosen('Studio profile'), 'Delete')
    assert.match(said(), /Build history31\.0 MB · Deleted with the studio profile/)
  })
  await confirm()
  check('the profile is deleted through Hermes after the backend parts, taking its chats with it', () => {
    assert.deepEqual(log, ['stop', 'history', 'settings', 'toolchain', 'logs', 'update:update'])
    assert.deepEqual(scenario.calls.filter(call => call[0] === 'deleteProfile'), [['deleteProfile', 'hermretro']])
  })
  await click('Close', dialog())

  log.length = 0; active = [{ status: 'working', title: 'Frog Post' }]
  await open(); await confirm()
  check('nothing is deleted while a game is being built', () => {
    assert.deepEqual(log, [])
    assert.match(said(), /The reset stopped/)
    assert.match(said(), /Stopped atStopping the studio: A game is being built in "Frog Post"/)
    assert.match(said(), /KeptGames, Build history, Studio chats, Studio profile, Plugin settings, Toolchain & engine, Logs & captures/)
  })
  await click('Close', dialog())

  active = []; installedIn = { profile: 'hermretro', linked: false }
  await open()
  check('the studio profile stays when hermretro is installed in it', () => {
    assert.match(said(), /Studio profileModel, sign-in, SOUL · hermretro is installed here/)
    assert.equal(chosen('Studio profile'), 'Keep')
    assert.ok(choice('Studio profile').querySelector('button').disabled)
  })
  await page.close()
})
