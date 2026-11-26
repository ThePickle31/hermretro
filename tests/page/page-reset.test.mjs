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
      games: { bytes: 130e6, count: 14 }, history: { bytes: 31e6 }, chats: { count: 2 }, profile: { ours: true }, settings: {},
      toolchain: { bytes: 2.4e9, custom: false }, logs: { bytes: 15e6 }
    }
  }
  // Every profile on this connection has a route (Hermes lists the app's own too); the reset uses only routes.
  const HOME = { connectionId: 'local', profile: 'default', targetProfile: 'default' }
  scenario.routes = [STUDIO, HOME]
  let version = '1.2.3'
  let updated = false
  let named = { exists: true, ours: true, installed: true }
  scenario.byMethod['plugin.hermretro.status'] = () => ({ ok: true, plugin: { version, installed_in: installedIn }, profile: { studio: named } })
  scenario.byMethod['plugins.manage'] = params => { log.push(`update:${params.action}`); return updated ? { ok: true } : { ok: true, unchanged: true } }
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => ({ ok: true })
  scenario.requestProfileHook = (route, method, params) => {
    // The profile hermretro is installed in answers as the app's own does.
    if ((route.profile === 'default' || route.profile === 'work') && method === 'plugin.hermretro.reset') {
      log.push(`${params.part}@${route.profile}`); return { ok: true, removed_bytes: 0 }
    }
    if (route.profile === 'default' || route.profile === 'work') {
      const answer = scenario.byMethod[method]
      if (!answer) throw Object.assign(new Error('unknown method'), { code: -32601 })
      return typeof answer === 'function' ? answer(params) : answer
    }
    // The hermretro profile answers as itself, when hermretro is set up there.
    if (method === 'plugin.hermretro.status') {
      if (!named.installed) throw Object.assign(new Error('unknown method'), { code: -32601 })
      return { ...scenario.byMethod['plugin.hermretro.status'](), profile: { is_studio: true } }
    }
    if (method === 'plugin.hermretro.reset_plan') return plan
    if (method === 'plugin.hermretro.reset') { log.push(params.part); return { ok: true, removed_bytes: 1e6 } }
    if (method === 'session.active_list') return { sessions: active }
    if (method === 'plugins.manage') { log.push(`studio:${params.action}`); return { ok: true, gateway_reloaded: true } }
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
    assert.match(said(), /Plugin settingsDeleted with the studio profile/)
    assert.match(said(), /Toolchain & engine2\.4 GB/)
    assert.deepEqual(['Games', 'Build history', 'Toolchain & engine'].map(chosen), ['Keep', 'Delete', 'Delete'])
    assert.deepEqual([...dialog().querySelectorAll('[role=group]')].map(node => node.getAttribute('aria-label')).slice(0, 2), ['Games', 'Build history'], 'each Keep/Delete pair is named for its part')
  })
  await pick('Studio profile', 'Keep'); await pick('Studio chats', 'Keep'); await pick('Games', 'Delete'); await pick('Logs & captures', 'Keep')
  check('deleting Games takes build history with it', () => {
    assert.match(said(), /Build history31\.0 MB · Deleted with Games/)
    assert.match(said(), /Logs & captures15\.0 MB · Game captures go with Games/)
    assert.ok(choice('Build history').querySelector('button').disabled)
  })
  await pick('Logs & captures', 'Delete')
  check('Logs & captures stays free to choose while Games is deleted', () => { assert.equal(chosen('Logs & captures'), 'Delete') })
  await pick('Logs & captures', 'Keep'); await click('Continue', dialog())
  check('the confirm step carries the note where the kept size would be', () => { assert.match(said(), /Keep.*Logs & capturesGame captures go with Games/) })
  await typeInto(dialog().querySelector('input'), 'reset')
  await click('Back', dialog())
  await click('Continue', dialog())
  check('going back to the choices asks for the word again', () => {
    assert.equal(dialog().querySelector('input').value, '')
    assert.ok([...dialog().querySelectorAll('button')].find(node => node.textContent === 'Reset').disabled)
  })
  await click('Back', dialog())
  await pick('Games', 'Keep'); await pick('Logs & captures', 'Delete'); await pick('Studio chats', 'Delete')
  await pick('Build history', 'Keep')
  check('keeping build history while the chats go is allowed, and says what it loses', () => {
    assert.equal(chosen('Build history'), 'Keep')
    assert.match(said(), /Build history31\.0 MB · Numbered builds go with the chats/)
  })
  await pick('Build history', 'Delete')
  await click('Continue', dialog())
  check('the confirm step says what goes and what stays, and waits for the word', () => {
    assert.match(said(), /Delete.*Build history.*Studio chats.*Toolchain & engine/)
    assert.match(said(), /Keep.*Games.*Studio profile/)
    assert.ok([...dialog().querySelectorAll('button')].find(node => node.textContent === 'Reset').disabled)
  })
  await typeInto(dialog().querySelector('input'), 'reset')
  await click('Reset', dialog()); await settle(60)
  check('the backend parts go first, in order, then the update', () => {
    assert.deepEqual(log, ['stop', 'history', 'logs', 'chats', 'settings', 'toolchain', 'update:update'])
    assert.ok(!scenario.calls.some(call => call[0] === 'deleteProfile'))
  })
  check('the done screen says what was deleted, kept and the version', () => {
    assert.match(said(), /hermretro is reset/)
    assert.match(said(), /Deleted5\.0 MB/)
    assert.match(said(), /KeptGames, Studio profile/)
    assert.match(said(), /Version1\.2\.3, up to date/)
  })
  scenario.restartAnswer = false
  await click('Reload & restart gateway', dialog()); await settle()
  check('a restart the user says no to keeps the done screen and its summary', () => {
    assert.ok(scenario.calls.some(call => call[0] === 'restartGateway'))
    assert.match(said(), /hermretro is reset/)
    assert.equal(typeof scenario.storage.resetDone, 'object'); assert.ok(scenario.storage.resetDone)
  })
  scenario.restartAnswer = true
  await click('Reload & restart gateway', dialog()); await settle()
  check('a restart that goes ahead forgets the summary', () => { assert.equal(scenario.storage.resetDone ?? null, null) })
  await click('Close', dialog())

  log.length = 0
  await open()
  check('deleting the studio profile takes its chats and build history', () => {
    assert.equal(chosen('Studio profile'), 'Delete')
    assert.match(said(), /Build history31\.0 MB · Deleted with the studio profile/)
  })
  await confirm()
  check('the profile is deleted whole through Hermes after the backend parts, then no game points at its chats', () => {
    assert.deepEqual(log, ['stop', 'history', 'logs', 'settings', 'toolchain', 'links@default', 'update:update'])
    assert.deepEqual(scenario.calls.filter(call => call[0] === 'deleteProfile'), [['deleteProfile', 'hermretro', 'local']])
  })
  await click('Close', dialog())

  log.length = 0; updated = true
  await open(); await pick('Studio profile', 'Keep'); await confirm()
  check('a newer version is installed and loaded into the hermretro profile last', () => {
    assert.deepEqual(log.slice(-3), ['update:update', 'studio:toggle', 'studio:toggle'])
    assert.equal(scenario.storage.resetDone.update.kind, 'updated')
  })
  await page.close()
  version = '1.2.4'
  const reloaded = await mount(settingsPages[0]); await settle(40)
  check('the settings page the app loads next opens on how the reset ended, on the new version', () => {
    assert.match(said(), /hermretro is reset/)
    assert.match(said(), /Version1\.2\.3 → 1\.2\.4/)
  })
  await click('Close', dialog())
  check('closing it forgets the summary', () => { assert.equal(scenario.storage.resetDone ?? null, null) })
  updated = false; version = '1.2.3'

  log.length = 0; scenario.storage.updatePending = { at: 1, error: 'the hermretro profile did not reload' }
  await open(); await pick('Studio profile', 'Keep'); await confirm()
  check('an update that installed but did not finish loading is finished, not read as up to date', () => {
    assert.equal(scenario.storage.resetDone.update.kind, 'updated')
    assert.equal(scenario.storage.updatePending, null)
    assert.ok(log.includes('studio:toggle'))
  })
  await click('Close', dialog())

  plan.parts.profile = { ours: true, holds: true }
  await open()
  check('a studio profile that holds the games stays', () => {
    assert.match(said(), /Studio profileModel, sign-in, SOUL · Holds your games/)
    assert.equal(chosen('Studio profile'), 'Keep')
  })
  await click('Cancel', dialog())
  plan.parts.profile = { ours: true }

  log.length = 0
  const restarts = scenario.calls.filter(call => call[0] === 'restartGateway').length
  await open(); await pick('Studio profile', 'Keep')
  const step = scenario.requestProfileHook
  scenario.requestProfileHook = (route, method, params) => {
    if (method === 'plugin.hermretro.reset' && params.part === 'stop') scenario.appProfile = 'work'
    return step(route, method, params)
  }
  await confirm()
  check('the app switching profile partway moves nothing: every call keeps its own route, the update too', () => {
    assert.deepEqual(log, ['stop', 'history', 'logs', 'chats', 'settings', 'toolchain', 'update:update'])
    assert.ok(scenario.calls.some(call => call[0] === 'requestProfile' && call[1] === 'default' && call[2] === 'plugins.manage'))
    assert.ok(!scenario.calls.some(call => call[0] === 'request' && call[1] === 'plugins.manage'), 'never through the app\'s own connection')
    assert.match(said(), /hermretro is reset/)
  })
  scenario.requestProfileHook = step
  await click('Reload & restart gateway', dialog()); await settle()
  check('the restart is refused once the app is on another profile than the reset ran on', () => {
    assert.equal(scenario.calls.filter(call => call[0] === 'restartGateway').length, restarts)
  })
  scenario.appProfile = undefined
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

  log.length = 0; active = []
  const answer = scenario.requestProfileHook
  scenario.requestProfileHook = (route, method, params) => {
    if (method === 'plugin.hermretro.reset' && params.part === 'stop') active = [{ status: 'working', title: 'Owl' }]
    return answer(route, method, params)
  }
  await open(); await confirm()
  check('a build started after the first check stops the reset at the next step', () => {
    assert.deepEqual(log, ['stop'])
    assert.match(said(), /Stopped atBuild history: A game is being built in "Owl"/)
  })
  scenario.requestProfileHook = answer
  await click('Close', dialog())

  active = []; installedIn = { profile: 'hermretro', linked: false }
  await open()
  check('the studio profile stays when hermretro is installed in it', () => {
    assert.match(said(), /Studio profileModel, sign-in, SOUL · hermretro is installed here/)
    assert.equal(chosen('Studio profile'), 'Keep')
    assert.ok(choice('Studio profile').querySelector('button').disabled)
  })
  await click('Cancel', dialog())

  // hermretro's agent half off in the profile it is installed in: the studio profile cannot be deleted from here.
  installedIn = { profile: 'default', linked: false }
  const before15 = scenario.requestProfileHook
  scenario.requestProfileHook = (route, method, params) => {
    if (route.profile === 'default' && method === 'plugin.hermretro.status') throw Object.assign(new Error('unknown method'), { code: -32601 })
    return before15(route, method, params)
  }
  await open()
  check('the studio profile stays while hermretro is off where it is installed', () => {
    assert.match(said(), /Studio profileModel, sign-in, SOUL · Turn hermretro on in default/)
    assert.equal(chosen('Studio profile'), 'Keep')
  })
  await click('Cancel', dialog())
  scenario.requestProfileHook = (route, method, params) => {
    if (route.profile === 'default' && method === 'plugin.hermretro.reset' && params.part === 'links') throw new Error('unknown method')
    return before15(route, method, params)
  }
  await open(); await confirm()
  check('a profile deleted before its clean-up failed is said to be gone', () => {
    assert.match(said(), /Stopped atStudio profile: unknown method/)
    assert.doesNotMatch(said(), /Kept[^V]*Studio profile/)
  })
  await click('Close', dialog())
  scenario.requestProfileHook = before15

  // hermretro off (or older) in the studio profile: the error names it.
  const before11 = scenario.requestProfileHook
  scenario.requestProfileHook = (route, method, params) => {
    if (route.profile === 'hermretro' && method === 'plugin.hermretro.reset_plan') throw Object.assign(new Error('unknown method'), { code: -32601 })
    return before11(route, method, params)
  }
  await open()
  check('a studio profile with hermretro off is named', () => { assert.match(said(), /Turn hermretro on in the hermretro profile/) })
  await click('Close', dialog())
  scenario.requestProfileHook = before11

  installedIn = { profile: 'default', linked: false }; named = { exists: true, ours: false, installed: false }
  const plans = () => scenario.calls.filter(call => call[0] === 'requestProfile' && call[1] === 'hermretro' && call[2] === 'plugin.hermretro.reset_plan').length
  const asked = plans()
  scenario.byMethod['plugin.hermretro.reset_plan'] = plan
  await open()
  check('a profile of the user\'s own named hermretro is never asked or touched', () => {
    assert.equal(plans(), asked)
    assert.match(said(), /Studio chats2 chats · Not made by hermretro/)
    assert.equal(chosen('Studio profile'), 'Keep')
  })
  await click('Cancel', dialog())
  named = { exists: true, ours: true, installed: true }

  log.length = 0; scenario.storage.updatePending = { at: 1, error: null, connectionId: 'vps', profile: 'default' }
  await open(); await pick('Studio profile', 'Keep'); await confirm()
  check('an update left unfinished on another Hermes is neither finished nor forgotten here', () => {
    assert.ok(!log.includes('update:update'))
    assert.match(said(), /Stopped atUpdating hermretro: Another hermretro update is unfinished/)
    assert.equal(scenario.storage.updatePending.connectionId, 'vps')
  })
  await click('Close', dialog())
  scenario.storage.updatePending = null

  scenario.appProfile = 'hermretro'
  const before = scenario.calls.filter(call => call[0] === 'restartGateway').length
  await open(); await confirm()
  check('after deleting the studio profile the app was on, the app is on its default profile', () => {
    assert.equal(scenario.appProfile, 'default')
    assert.match(said(), /hermretro is reset/)
  })
  scenario.restartAnswer = false
  await click('Reload & restart gateway', dialog()); await settle()
  check('and Reload & restart gateway still restarts it there', () => {
    assert.equal(scenario.calls.filter(call => call[0] === 'restartGateway').length, before + 1)
  })
  await click('Close', dialog())
  scenario.appProfile = undefined

  installedIn = { profile: 'default', linked: false }; plan.parts.profile = { ours: false }
  await open()
  check('a hermretro profile hermretro did not make keeps its chats and itself', () => {
    assert.match(said(), /Studio chats2 chats · Not made by hermretro/)
    assert.equal(chosen('Studio chats'), 'Keep'); assert.equal(chosen('Studio profile'), 'Keep')
  })
  await click('Cancel', dialog())
  plan.parts.profile = { ours: true }

  log.length = 0
  const whole = scenario.requestProfileHook
  scenario.requestProfileHook = (route, method, params) => {
    if (method === 'plugin.hermretro.reset' && params.part === 'logs') {
      log.push('logs'); return { ok: false, code: 'PARTLY_REMOVED', error: '1 of its files or folders could not be deleted', removed_bytes: 2e6 }
    }
    return whole(route, method, params)
  }
  await open(); await pick('Studio profile', 'Keep'); await confirm()
  check('a part deleted only in part counts what went and is not listed as kept', () => {
    assert.deepEqual(log, ['stop', 'history', 'logs'])
    assert.match(said(), /Stopped atLogs & captures: 1 of its files/)
    assert.match(said(), /Deleted3\.0 MB/)
    assert.match(said(), /KeptGames, Studio chats, Studio profile, Plugin settings, Toolchain & engine/)
  })
  scenario.requestProfileHook = whole
  await click('Close', dialog())

  // hermretro installed in a profile of its own, no studio yet, the app on its default profile where hermretro is off.
  const WORK = { connectionId: 'local', profile: 'work', targetProfile: 'work' }
  installedIn = { profile: 'work', linked: false }; named = { exists: false }
  scenario.routes = [WORK, HOME]
  const off = scenario.requestProfileHook
  scenario.requestProfileHook = (route, method, params) => {
    if (route.profile === 'default' && method === 'plugin.hermretro.status') throw Object.assign(new Error('unknown method'), { code: -32601 })
    return off(route, method, params)
  }
  await open()
  check('hermretro installed in a profile the app is not on is found there', () => {
    assert.match(said(), /Studio profileModel, sign-in, SOUL · No studio profile/)
    assert.ok(scenario.calls.some(call => call[0] === 'requestProfile' && call[1] === 'work' && call[2] === 'plugin.hermretro.reset_plan'))
  })
  await click('Cancel', dialog())
  scenario.requestProfileHook = off; named = { exists: true, ours: true, installed: true }

  installedIn = { profile: 'default', linked: false }; scenario.routes = [{ ...STUDIO, connectionId: 'vps' }, HOME]
  scenario.byMethod['plugin.hermretro.reset_plan'] = plan
  await open()
  check('a hermretro profile only on another Hermes connection stops the reset before anything is chosen', () => {
    assert.match(said(), /The hermretro profile cannot be reached right now/)
    assert.ok(!dialog().querySelector('[data-segmented]'))
  })
  await reloaded.close()
})
