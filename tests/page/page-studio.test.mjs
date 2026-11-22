// The studio around the wizard: no panes, a fresh user without a Chromatic, the page's stylesheet and artwork,
// and the dedicated hermretro profile the first step creates.
// Run alone: node tests/page/page-studio.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, dom, scenario, registrations, page, text, heading, click, tab, currentTab, mount, check, answered, status, doctor, installAnswer, complete }) => {
  // Where the setup scenarios leave the app: onboarded with the Chromatic set up, on a profile that has the
  // plugin, tools verified.
  scenario.storage = { setup: { onboarded: true, hardwareSkipped: false, hardwareWanted: true, firmwareDone: true, devmodeDone: true }, page: 'build' }
  scenario.ambient = complete
  scenario.install = installAnswer({ state: 'idle' })

  check('the Desktop sidebar shows HermRetro and opens the existing route', () => {
    const nav = registrations.find(entry => entry.area === 'sidebar.nav' && entry.id === 'nav')
    assert.equal(nav?.data.label, 'HermRetro')
    assert.equal(nav?.data.path, '/hermretro')
  })

  // 9. No panes beside the chat: the agent's work and the game live on the Build page.
  check('the plugin contributes no panes (closing a plugin\'s only pane would switch it off)', () => {
    assert.equal(registrations.filter(entry => entry.area === 'panes').length, 0)
  })
  // 8b. Someone without a Chromatic: one click from the choice page to the studio.
  const kept = scenario.storage
  scenario.storage = {}
  scenario.status = answered(status()); scenario.doctor = answered(doctor([]))
  const fresh = await mount(page)
  check('a fresh user starts on Build', () => { assert.equal(currentTab(), 'Build') })
  await tab('Setup')
  check('a fresh user lands on the choice once the game steps are done', () => { assert.equal(heading(), 'Ready to make games') })
  await click('Start making games')
  check('"Start making games" skips every hardware step and the studio is in emulator mode', () => {
    assert.equal(heading(), 'Setup is complete'); assert.match(text(), /emulator only/)
    assert.equal(scenario.storage.setup.hardwareSkipped, true)
  })
  check('the skipped Chromatic steps stay visible in the step list', () => {
    const rail = dom.window.document.querySelector('nav[aria-label="Setup steps"]').textContent
    assert.match(rail, /Your Chromatic/); assert.match(rail, /optional/); assert.match(rail, /emulator only/)
    assert.equal(dom.window.document.querySelectorAll('.cs-rail-item[data-state="skipped"]').length, 4)
  })
  check('every Setup page shows the flying Chromatic: a body and two wings, still under reduced motion', () => {
    const flyer = dom.window.document.querySelector('.cs-flyer')
    assert.ok(flyer, 'flyer drawn'); assert.equal(flyer.querySelectorAll('.wing').length, 2); assert.ok(flyer.querySelector('.body .ink'))
    const css = dom.window.document.querySelector('style').textContent
    assert.match(css, /prefers-reduced-motion: reduce\) \{[^}]*\.cs-flyer \* \{ animation: none/)
  })
  const flyerNode = dom.window.document.querySelector('.cs-flyer')
  await click('Studio profile')
  check('moving between steps keeps the same flyer element, so its animation does not restart', () => {
    assert.ok(dom.window.document.querySelector('.cs-flyer') === flyerNode, 'the flyer element is retained')
  })
  await click('Continue')
  scenario.games = answered({ games: [] })
  await tab('Games')
  check('the page carries its stylesheet and artwork', () => {
    const css = dom.window.document.querySelector('style')?.textContent ?? ''
    assert.match(css, /\.cs-page/); assert.match(css, /prefers-reduced-motion/)
    assert.ok(!/#[0-9a-f]{3,6}\b|rgb\(/i.test(css), 'colours come from theme variables only')
    assert.ok(dom.window.document.querySelector('.cs-art'), 'artwork is drawn')
    const vars = dom.window.document.querySelector('.cs-page').getAttribute('style')
    for (const name of ['--cs-hermes', '--cs-cart', '--cs-fly-body', '--cs-fly-wing']) assert.match(vars, new RegExp(`${name}: url\\("data:image/png;base64,`))
  })
  await fresh.close()
  for (const removed of ['home', 'prompts']) {
    scenario.storage = { ...kept, page: removed }
    const remembered = await mount(page)
    check(`a remembered ${removed} page opens on Build`, () => { assert.equal(currentTab(), 'Build') })
    await remembered.close()
  }
  scenario.storage = kept

  // 11. The dedicated profile: the first step creates it, then the page moves over to it.
  const createParams = { name: 'hermretro', description: 'hermretro', no_skills: true, share_auth: true, no_alias: true }
  const installer = (studio = {}) => ({ ...complete, profile: { name: 'default', is_studio: false, create: createParams,
    studio: { name: 'hermretro', exists: false, installed: false, ours: false, ...studio } } })
  scenario.ambient = installer(); scenario.status = answered(installer())
  scenario.routes = [{ profile: 'default', connectionId: 'local' }]; scenario.byProfile = {}
  const studioPage = await mount(page)
  await tab('Setup')
  check('a plugin installed into an ordinary profile starts with creating the studio profile', () => {
    assert.equal(heading(), 'Create the hermretro profile'); assert.match(text(), /Step 1 of 6/)
    assert.match(text(), /uses your existing sign-in and keys/)
    assert.match(text(), /The "default" profile, where the plugin is installed, is not changed/)
  })
  scenario.calls.length = 0; scenario.notices.length = 0
  scenario.byMethod['profiles.create'] = { ok: true, name: 'hermretro' }
  scenario.byMethod['plugin.hermretro.studio_profile'] = { ok: true, profile: 'hermretro' }
  await click('Create the hermretro profile')
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  check('the button has Hermes create the profile, then the plugin finishes it', () => {
    assert.deepEqual(scenario.calls.filter(call => call[0] === 'request').map(call => call[1]),
      ['profiles.create', 'plugin.hermretro.studio_profile'])
    assert.deepEqual(scenario.paramsByMethod['profiles.create'], createParams)
    assert.ok(scenario.notices.some(notice => /profile created/i.test(notice.message)))
  })
  scenario.ambient = installer({ exists: true, installed: true, ours: true })
  scenario.status = answered(scenario.ambient)
  await studioPage.rerender()
  check('until the new profile answers, the page says it is starting instead of offering the button again', () => {
    assert.match(text(), /Waiting for Hermes to start it/)
    assert.match(text(), /Set it up again/)
    assert.ok(![...dom.window.document.querySelectorAll('button')].some(node => node.textContent.includes('Create the hermretro profile')))
  })
  scenario.routes.push({ profile: 'hermretro', targetProfile: 'hermretro', connectionId: 'local' })
  scenario.byProfile = { 'hermretro': complete }
  const moved = await scenario.fns.status()
  check('the page moves over to the studio profile once it answers', () => {
    assert.equal(moved.via_profile, 'hermretro'); assert.equal(moved.profile.is_studio, true)
  })
  scenario.calls.length = 0
  await scenario.fns.status()
  check('from then on it asks the studio profile, not the profile the app is on', () => {
    assert.deepEqual(scenario.calls, [['requestProfile', 'hermretro', 'plugin.hermretro.status']])
  })
  scenario.status = answered(moved)
  await studioPage.rerender()
  // The first-game planning action still drafts in the routed studio profile, never the active composer.
  const setupMemory = scenario.storage
  scenario.storage = { setup: { onboardStarted: true, hardwareSkipped: true } }
  const onboarding = await mount(page)
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Plan it first')
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  check('onboarding planning opens a draft in the studio profile without sending it', () => {
    assert.deepEqual(scenario.calls[0], ['newChat', 'hermretro'])
    assert.match(scenario.inserted.at(-1)?.[1], /plan a small Game Boy Color game before we build anything/)
    assert.ok(!scenario.calls.some(([kind, argument, method]) =>
      (kind === 'request' && argument === 'prompt.submit') || (kind === 'requestProfile' && method === 'prompt.submit')))
  })
  await onboarding.close()
  scenario.storage = setupMemory
  scenario.byProfile = {}
  scenario.ambient = installer({ exists: true })
  scenario.byMethod['plugin.hermretro.studio_profile'] = { ok: false, code: 'NAME_TAKEN', error: 'A profile named hermretro already exists and was not made by hermretro.' }
  scenario.status = answered(await scenario.fns.status())
  await studioPage.rerender()
  await tab('Setup')
  scenario.calls.length = 0
  await click('Create the hermretro profile')
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  check('a profile of that name made by someone else is not recreated, and the refusal is shown', () => {
    assert.ok(!scenario.calls.some(call => call[1] === 'profiles.create'))
    assert.match(text(), /already exists and was not made by hermretro/)
    assert.equal(heading(), 'Create the hermretro profile')
  })
  const old = { ...complete }; delete old.profile
  scenario.status = answered(old)
  await studioPage.rerender()
  check('a backend that predates profiles does not block setup on this step', () => { assert.equal(heading(), 'Setup is complete') })
  await studioPage.close()
})
