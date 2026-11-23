// From setup to the first game: onboarding's last screen hands the idea to Build's New Game box (unsent, with Build it
// or Plan first kept), the box keeps it across pages, a missing model provider is said with where to fix it, the
// opt-in demo during the install, and the hardware settings link aimed at the hermretro profile.
// Run alone: node tests/page/page-setup-handoff.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, createRoot, dom, host, mount, scenario, page, root, render, shows, hides, heading, click, tab, currentTab, settle, button, typeInto, check, answered, status, doctor, installAnswer, complete, cli }) => {
  const doc = dom.window.document
  const sent = () => scenario.calls.filter(call => call[1] === 'session.create' || call[1] === 'prompt.submit' || call[0] === 'newChat' || call[0] === 'insert')

  // The tools are in and the user chose the emulator: onboarding's last screen.
  scenario.storage = { setup: { onboardStarted: true, hardwareSkipped: true } }
  scenario.status = answered(status()); scenario.doctor = answered(doctor([])); scenario.install = installAnswer({ state: 'done', fraction: 1 })
  scenario.ambient = complete; scenario.routes = []; scenario.byProfile = {}
  scenario.games = answered({ games: [], device: { hardwareEnabled: false, skipped: true } })
  scenario.models = answered({ provider: 'openai-codex', model: 'gpt-x', providers: [{ slug: 'openai-codex', name: 'ChatGPT', authenticated: true, models: ['gpt-x'] }] })
  await render()
  check('the last screen says where the idea goes and that nothing is sent from it', () => {
    assert.equal(heading(), 'What do youwant to make?')
    shows(/It goes into the New Game box on Build\. Nothing is sent until you press send there\./)
    assert.ok(button('Continue in Build') && button('Plan it first') && button('Set up my Chromatic first'))
    hides(/opens in a new chat/)
  })
  await typeInto(doc.querySelector('.cs-idea textarea'), 'a frog who delivers mail across a flooded town')
  scenario.calls.length = 0
  await click('Plan it first'); await settle()
  const box = () => doc.querySelector('.cs-b-new textarea[aria-label="Your game idea"]')
  check('Plan it first ends onboarding on New Game with the idea in its box and Plan first chosen, nothing sent', () => {
    assert.equal(scenario.storage.setup.onboarded, true); assert.equal(currentTab(), 'Build')
    assert.equal(box()?.value, 'a frog who delivers mail across a flooded town')
    assert.equal(doc.querySelector('[data-mode="plan"]').getAttribute('aria-checked'), 'true')
    assert.equal(doc.querySelector('.cs-b-new .cs-b-send').getAttribute('aria-label'), 'Start planning')
    assert.equal(doc.activeElement, box(), 'the box has focus, ready to send or edit')
    assert.deepEqual(sent(), [], 'no session, no submit, no Hermes chat or composer')
  })
  check('with a signed-in provider there is no provider notice', () => { assert.ok(!doc.querySelector('.cs-b-provider')) })

  await typeInto(box(), 'a frog who delivers mail across a flooded town, with boats')
  await tab('Setup'); await tab('Build')
  check('leaving Build and coming back keeps what was typed and the choice', () => {
    assert.equal(box().value, 'a frog who delivers mail across a flooded town, with boats')
    assert.equal(doc.querySelector('[data-mode="plan"]').getAttribute('aria-checked'), 'true')
    assert.deepEqual(scenario.storage.buildNewGame, { idea: 'a frog who delivers mail across a flooded town, with boats', plan: true })
  })

  // The hermretro profile lists providers, none signed in: say so, with the way there (no model is called to find out).
  scenario.models = answered({ providers: [{ slug: 'anthropic', name: 'Anthropic', authenticated: false, models: ['claude'] }] })
  await render()
  check('no signed-in provider: a notice names the hermretro profile and keeps the idea', () => {
    const notice = doc.querySelector('.cs-b-provider')
    assert.ok(notice, 'the provider notice')
    assert.match(notice.textContent, /No model provider is signed in for the hermretro profile yet\./)
    assert.match(notice.textContent, /Your idea stays here until you send it/)
    assert.match(notice.textContent, /check that \u201cApplies to\u201d is hermretro/, 'Settings keep the last Applies to choice, on any profile')
    assert.equal(box().value, 'a frog who delivers mail across a flooded town, with boats')
  })
  scenario.models = { data: { providers: [{ slug: 'anthropic', name: 'Anthropic', authenticated: false, models: ['claude'] }] }, isFetching: true }
  await render()
  check('while the providers are asked again (back from Settings), the earlier answer is not shown', () => {
    assert.ok(!doc.querySelector('.cs-b-provider'))
    assert.equal(scenario.queries.filter(query => query.key === 'models').length > 0, true)
  })
  scenario.models = answered({ providers: [{ slug: 'anthropic', name: 'Anthropic', authenticated: false, models: ['claude'] }] })
  await render()
  scenario.navigations.length = 0
  await click('Open provider settings', doc.querySelector('.cs-b-provider'))
  check('Open provider settings goes to Settings › Providers', () => {
    assert.deepEqual(scenario.navigations, ['/settings?tab=providers'])
  })

  // Sending is the user's own press, through New Game's normal start.
  scenario.models = answered({ provider: 'openai-codex', model: 'gpt-x', providers: [{ slug: 'openai-codex', name: 'ChatGPT', authenticated: true, models: ['gpt-x'] }] })
  const builds = []
  const submits = []
  scenario.byMethod['session.create'] = () => ({ session_id: 'rt-first', stored_session_id: 'st-first', info: { model: 'gpt-x', provider: 'openai-codex' }, messages: [] })
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }
  scenario.byMethod['plugin.hermretro.build'] = params => { builds.push(params); return { ok: true } }
  await render()
  await act(async () => { doc.querySelector('.cs-b-new .cs-b-send').click() })
  await settle()
  check('send starts a planning New Game with the words as written, then the kept draft is cleared', () => {
    assert.deepEqual(builds.at(-1), { action: 'start', stored: 'st-first', name: null, plan: true })
    assert.equal(submits.at(-1).text, 'a frog who delivers mail across a flooded town, with boats')
    assert.equal(scenario.storage.buildNewGame, null)
  })

  // A failed start keeps the draft.
  scenario.storage.buildSelected = 'new'
  scenario.byMethod['session.create'] = () => { throw new Error('gateway is restarting') }
  const second = doc.createElement('div'); doc.body.appendChild(second)
  const secondRoot = createRoot(second)
  await act(async () => { root.render(null); secondRoot.render(page.render()) })
  await typeInto(second.querySelector('.cs-b-new textarea'), 'a moth who collects lamps')
  await act(async () => { second.querySelector('.cs-b-new .cs-b-send').click() })
  await settle()
  check('a start that fails keeps the idea in the box and in storage', () => {
    assert.match(scenario.notices.at(-1).message, /Could not start the conversation: gateway is restarting/)
    assert.equal(second.querySelector('.cs-b-new textarea').value, 'a moth who collects lamps')
    assert.deepEqual(scenario.storage.buildNewGame, { idea: 'a moth who collects lamps', plan: false })
  })
  // Hermes opened the conversation but refused its first message: the game did not start, so the idea stays too.
  scenario.byMethod['session.create'] = () => ({ session_id: 'rt-refused', stored_session_id: 'st-refused', info: { model: 'gpt-x', provider: 'openai-codex' }, messages: [] })
  scenario.byMethod['prompt.submit'] = () => { throw new Error('the gateway refused the turn') }
  await act(async () => { second.querySelector('.cs-b-new .cs-b-send').click() })
  await settle()
  check('a first message Hermes refused keeps the idea in the box and in storage, and the start is undone', () => {
    assert.match(scenario.notices.at(-1).message, /Could not start the conversation: Hermes did not take the first message/)
    assert.equal(second.querySelector('.cs-b-new textarea').value, 'a moth who collects lamps')
    assert.deepEqual(scenario.storage.buildNewGame, { idea: 'a moth who collects lamps', plan: false })
    assert.deepEqual(builds.at(-1), { action: 'cancel', stored: 'st-refused' })
  })
  await act(async () => { secondRoot.unmount() }); second.remove()
  delete scenario.byMethod['session.create']; delete scenario.byMethod['prompt.submit']; delete scenario.byMethod['plugin.hermretro.build']

  // During the install: the demo only when asked for, in its own tab beside the chat; the install screen stays.
  scenario.storage = { setup: { onboardStarted: true } }
  scenario.status = answered(status()); scenario.doctor = answered(doctor(['cli']))
  scenario.install = installAnswer({ state: 'running', run_id: 'run-1', started_at: 1, fraction: 0.2, current: 'cli', run: { components: { cli: { state: 'running', checks: [] } } } })
  scenario.workspaces.length = 0
  await act(async () => { root.render(null) }); await render()
  check('while installing, Try the demo is offered and nothing plays on its own', () => {
    assert.equal(heading(), 'Setting up the studio')
    assert.ok(button('Try the demo while you wait'))
    assert.equal(scenario.workspaces.length, 0)
  })
  await click('Try the demo while you wait'); await settle()
  check('Try the demo opens the bundled demo beside the chat and leaves the setup screen as it was', () => {
    assert.equal(scenario.workspaces.length, 1)
    assert.equal(scenario.workspaces[0].options.title, 'Emulator · Hello Color')
    assert.equal(heading(), 'Setting up the studio')
  })
  const demo = await mount({ render: scenario.workspaces[0].options.render })
  check('the demo tab asks the player for the bundled demo', () => {
    const asked = scenario.queries.filter(query => query.key === 'player' && query.queryKey?.[2] === 'side').at(-1)
    assert.equal(asked?.queryKey?.[3], 'demo')
  })
  await demo.close()
  scenario.workspaces.forEach(tab => tab.close())
  const openWorkspace = host.openWorkspace
  delete host.openWorkspace
  await render()
  check('a Desktop that cannot open a tab beside the chat offers no demo', () => {
    assert.equal(heading(), 'Setting up the studio'); assert.ok(!button('Try the demo while you wait'))
  })
  host.openWorkspace = openWorkspace
  scenario.install = installAnswer({ state: 'idle' })
  await render()
  check('before the install starts (the review) the demo is not offered', () => {
    assert.equal(heading(), "Here's what gets downloaded"); assert.ok(!button('Try the demo while you wait'))
  })

  // The hardware switch is a plugin setting of the hermretro profile, where the hardware tools are.
  scenario.storage = { setup: { hardwareWanted: true, firmwareDone: true, devmodeDone: true, onboarded: true }, page: 'setup' }
  scenario.status = answered(status({ hardware_enabled: false, deps: { toolchain_root: '/h/hermretro/.cache/toolchain', device_cli: cli('installed') } }))
  scenario.doctor = answered(doctor([]))
  await act(async () => { root.render(null) }); await render()
  scenario.navigations.length = 0
  await click('Open plugin settings')
  check('Open plugin settings opens the hermretro profile\'s plugin settings, even from another profile', () => {
    assert.deepEqual(scenario.navigations, ['/settings?tab=plugins&agent=hermretro&profile=hermretro'])
  })
})
