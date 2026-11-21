// The page before the studio is ready: the header nav, first-run onboarding and the setup wizard (one step per
// page, automatic advance when a step verifies), repairs, profile routing and the Build page's profile guard.
// Run alone: node tests/page/page-setup.test.mjs [path to a node_modules folder] (the harness is harness.mjs).
import assert from 'node:assert/strict'

import { runScenario } from './harness.mjs'

await runScenario(async ({ act, createRoot, dom, scenario, page, root, render, shows, hides, heading, WELCOME, headings, click, nav, tab, currentTab, settle, button, key, check, answered, notLoaded, cli, status, doctor, manifest, installAnswer, complete }) => {
  // 1. Not switched on anywhere: an explanation, not a setup step.
  scenario.status = notLoaded
  await render()
  // The registry test (registry.test.mjs) pins every page in nav order; here the shell draws them, the built-in ones
  // first, so a page added at the end (python tools/retrodev new page) changes only the registry and its test.
  check('one segmented control starts with Build · Setup · Games · Emulator, opening on Build', () => {
    const labels = [...nav().querySelectorAll('button')].map(node => node.firstChild.textContent)
    assert.deepEqual(labels.slice(0, 4), ['Build', 'Setup', 'Games', 'Emulator'])
    assert.equal(currentTab(), 'Build')
  })
  check('with the backend off there are no setup steps, only how to switch it on', () => {
    assert.deepEqual(headings(), ['hermretro is not switched on in any profile'])
    hides(/Step \d of/, 'no step counter')
    shows(/Open Capabilities/)
    hides('What are we making?', 'the New Game form does not appear while the backend is off')
  })


  // 1b. First run: a new user sees only the guided setup, and the page installs the tools itself.
  const createParams0 = { name: 'hermretro', description: 'hermretro', no_skills: true, share_auth: true, no_alias: true }
  const firstRun = status({ profile: { name: 'default', is_studio: false, create: createParams0,
    studio: { name: 'hermretro', exists: false, installed: false, ours: false } } })
  scenario.storage = {}
  scenario.status = answered(firstRun); scenario.doctor = answered(doctor(['cli'])); scenario.install = installAnswer({ state: 'idle' })
  await render()
  check('first run: only the welcome, no segmented nav', () => {
    assert.ok(!nav())
    assert.equal(dom.window.document.querySelector('h1')?.textContent, WELCOME)
    assert.ok(button('Get started')); shows(/≈ 708 MB download · ≈ 2\.3 GB on disk/)
    assert.ok(!button('Use in chat') && !button('Continue setup'))
    assert.match(dom.window.document.querySelector('.cs-onb-steps').textContent, /First-time setup/)
  })
  await click('Get started')
  check('Get started shows every download before anything starts: name, version, source, size, purpose', () => {
    assert.equal(scenario.storage.setup.onboardStarted, true)
    assert.equal(heading(), "Here's what gets downloaded")
    const table = dom.window.document.querySelector('.cs-dl').textContent
    for (const item of manifest.items) {
      assert.ok(table.includes(item.name) && table.includes(item.version) && table.includes(item.source) && table.includes(item.purpose), item.id)
    }
    assert.match(table, /18\.1 MB/); assert.match(table, /≈ 551 MB/); assert.match(table, /Your hermretro profile/)
    shows(/Node\.js 26\.13\.0 \(from Hermes\)/); shows(/\/h\/hermretro\/\.cache\/toolchain/)
    assert.ok(button('Download and install')); hides(/Set up in chat/, 'the install never goes through a chat')
    assert.match(dom.window.document.querySelector('.cs-onb-steps').getAttribute('aria-label'), /step 1 of 3: Install/)
    assert.ok(!nav())
  })
  scenario.calls.length = 0
  scenario.byMethod['plugin.hermretro.install'] = params => ({ ok: true, manifest, install: { state: params.action === 'start' ? 'running' : 'idle' } })
  scenario.byMethod['profiles.create'] = { ok: true, name: 'hermretro' }
  scenario.byMethod['plugin.hermretro.studio_profile'] = { ok: true, profile: 'hermretro' }
  await click('Download and install')
  await settle()
  check('Download and install starts the backend install and makes the studio profile alongside, no chat', () => {
    const requests = scenario.calls.filter(call => call[0] === 'request').map(call => call[1])
    assert.ok(requests.includes('plugin.hermretro.install')); assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.install'], { action: 'start' })
    assert.ok(requests.includes('profiles.create') && requests.includes('plugin.hermretro.studio_profile'))
    assert.ok(!scenario.calls.some(call => call[0] === 'newChat' || call[0] === 'insert'))
  })
  delete scenario.byMethod['plugin.hermretro.install']; delete scenario.byMethod['profiles.create']; delete scenario.byMethod['plugin.hermretro.studio_profile']
  scenario.install = installAnswer({ state: 'running', started_at: 1, fraction: 0.4, downloaded_bytes: 281_000_000, current: 'cli', run: { components: {
    gbdk: { state: 'done', version: '4.5.0', checks: [{ file: 'gbdk-linux64.tar.gz', sha256: 'd7857a5f6d135ee4', reused: false }] },
    cli: { state: 'running', checks: [] } } } })
  await render()
  check('while installing, the same list shows live state, progress and verified checksums', () => {
    assert.equal(heading(), 'Setting up the studio')
    const rows = [...dom.window.document.querySelectorAll('.cs-dl tbody tr')].map(row => [row.querySelector('.n').firstChild.textContent, row.dataset.state])
    assert.deepEqual(rows.slice(0, 4), [['Your hermretro profile', 'running'], ['GBDK compiler', 'done'], ['GB Studio CLI', 'running'], ['GB Studio packages', 'running']])
    shows(/40%/); shows(/281 MB downloaded/)
    const log = dom.window.document.querySelector('.cs-log').textContent
    assert.match(log, /gbdk-linux64\.tar\.gz {2}sha256 d7857a5f… {2}verified/); assert.match(log, /Installing GB Studio and its packages…/)
    assert.ok(!button('Download and install'), 'no second start while it runs')
  })
  check('the install status is polled quickly while it runs; the doctor is not', () => {
    const last = key => scenario.queries.filter(query => query.key === key).at(-1)
    assert.equal(last('install').enabled, true); assert.notEqual(last('doctor').refetchInterval, 8000)
  })
  scenario.install = installAnswer({ state: 'failed', started_at: 1, error: 'cli: yarn: ENOTFOUND registry.npmjs.org', run: { components: {
    gbdk: { state: 'done', checks: [] }, cli: { state: 'failed', error: 'yarn: ENOTFOUND registry.npmjs.org', checks: [] } } } })
  await render()
  check('a failed install says what stopped, keeps what finished, and offers retry or Hermes', () => {
    assert.equal(heading(), "One part didn't finish"); shows(/ENOTFOUND registry\.npmjs\.org/)
    assert.ok(button('Try again')); assert.ok(button('Ask Hermes to fix it'))
  })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Ask Hermes to fix it'); await settle()
  check('before the hermretro profile exists, Ask Hermes opens no chat in another profile: it copies the prompt and says why', () => {
    assert.ok(!scenario.calls.some(call => call[0] === 'newChat' || call[0] === 'insert'))
    assert.match(scenario.notices.at(-1).message, /hermretro profile is not set up yet.*prompt is copied/)
  })
  scenario.install = installAnswer({ state: 'done', started_at: 1, fraction: 1 })
  scenario.status = answered(status()); scenario.doctor = answered(doctor([]))
  await render()
  check('tools verified and profile made: Do you have a Chromatic?', () => {
    assert.equal(heading(), 'Do you have a Chromatic?'); assert.ok(!nav())
    assert.match(dom.window.document.querySelector('.cs-onb-steps').getAttribute('aria-label'), /step 2 of 3/)
    assert.ok(button('Not yet') && button('Yes, I have one'))
  })
  await click('Not yet')
  check('Not yet: emulator only, then What do you want to make?', () => {
    assert.equal(scenario.storage.setup.hardwareSkipped, true)
    assert.equal(heading(), 'What do youwant to make?')
  })
  await click('Tiny platformer')
  check('an idea fills the box', () => { assert.match(dom.window.document.querySelector('.cs-idea textarea').value, /frog hops/) })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Start in chat'); await settle()
  check('Start in chat opens a new chat with the idea, ends onboarding and shows Build', () => {
    assert.ok(scenario.calls.some(call => call[0] === 'newChat'))
    assert.match(scenario.inserted.at(-1)[1], /make a new Game Boy Color game: a tiny platformer where a frog/)
    assert.equal(scenario.storage.setup.onboarded, true)
    assert.equal(currentTab(), 'Build'); assert.equal(scenario.storage.page, 'build')
  })
  const keptRun = { ...scenario.storage }
  scenario.storage = { setup: { onboardStarted: true } }
  const second = dom.window.document.createElement('div'); dom.window.document.body.appendChild(second)
  const secondRoot = createRoot(second)
  await act(async () => { root.render(null); secondRoot.render(page.render()) })
  await click('Yes, I have one')
  check('Yes, I have one: onboarding ends on the first Chromatic step of Setup', () => {
    assert.equal(scenario.storage.setup.hardwareWanted, true); assert.equal(scenario.storage.setup.onboarded, true)
    assert.equal(currentTab(), 'Setup'); assert.equal(heading(), 'Update your Chromatic')
  })
  await act(async () => { secondRoot.unmount() }); second.remove()
  scenario.storage = keptRun
  scenario.install = undefined

  // 1c. An existing setup whose tools do not verify on the first load after an update: Repair, not Welcome.
  scenario.storage = { setup: { hardwareSkipped: true } }
  scenario.status = answered(status()); scenario.doctor = { isError: true, isFetching: false, error: new Error('toolchain_doctor timed out') }
  await act(async () => { root.render(null) }); await render()
  check('an existing user never gets the first-run welcome, even when the tools check fails', () => {
    assert.ok(nav(), 'the studio nav is shown'); assert.ok(!dom.window.document.querySelector('.cs-onb'))
    assert.equal(scenario.storage.setup.onboarded, true)
  })
  // 1d. A chat is already installing: the page waits for it instead of reporting a failure.
  scenario.storage = { setup: { onboardStarted: true } }
  scenario.status = answered(status()); scenario.doctor = answered(doctor(['cli'])); scenario.install = installAnswer({ state: 'idle' })
  await act(async () => { root.render(null) }); await render()
  scenario.byMethod['plugin.hermretro.install'] = { ok: false, code: 'OPERATION_IN_PROGRESS', error: 'Another setup operation is already running' }
  await click('Download and install'); await settle()
  delete scenario.byMethod['plugin.hermretro.install']
  check('install already running in a chat (an older backend that cannot say so): waits, with Check again, no failure', () => {
    shows(/being installed from a chat/); assert.ok(!button('Try again')); assert.ok(button('Check again'))
  })
  scenario.install = installAnswer({ state: 'idle', elsewhere: true })
  await render()
  check('the backend says a chat holds the setup lock: the tools check repeats while it does', () => {
    shows(/being installed from a chat/)
    assert.equal(scenario.queries.filter(query => query.key === 'doctor').at(-1).refetchInterval, 8000)
  })
  scenario.install = installAnswer({ state: 'idle', elsewhere: false })
  await render()
  check("the chat's install ended without the tools: the page says so and offers its own install", () => {
    shows(/install that was running in a chat stopped before the tools were ready/)
    assert.ok(button('Download and install') && !button('Download and install').disabled)
    assert.equal(scenario.queries.filter(query => query.key === 'doctor').at(-1).refetchInterval, false)
  })
  await act(async () => { root.render(null) })

  // After a plugin update the running Hermes still has the old code: the page asks for a restart.
  scenario.storage = { setup: { onboarded: true } }
  scenario.status = answered({ ...status(), restart_needed: true }); scenario.doctor = answered(doctor([])); scenario.install = installAnswer({ state: 'idle' })
  await render()
  check('after an update the page asks for a Hermes restart', () => {
    const banners = [...dom.window.document.querySelectorAll('.cs-repair')].map(node => node.textContent).join(' ')
    assert.match(banners, /hermretro was updated, but Hermes is still running the old version\. Quit and reopen Hermes to finish/)
  })
  await act(async () => { root.render(null) })

  // 2. After onboarding the toolchain breaks: the page says so and Setup repairs it (Node.js is not a step).
  scenario.storage = { setup: { onboarded: true } }
  scenario.status = answered(status()); scenario.doctor = answered(doctor(['cli'])); scenario.install = installAnswer({ state: 'idle' })
  await render()
  check('while setup is incomplete the page opens on Build with the Repair banner, and Setup has its dot', () => {
    assert.equal(currentTab(), 'Build')
    assert.match(dom.window.document.querySelector('.cs-repair').textContent, /Game toolchain needs attention/)
    assert.ok(nav().querySelector('.pip'), 'the Setup tab shows a dot while setup is incomplete')
  })
  await click('Repair')
  check('Repair opens the Setup tab', () => { assert.equal(currentTab(), 'Setup') })
  check('one step per page, starting at the first incomplete one', () => {
    assert.deepEqual(headings(), ['Install the game toolchain'])
    shows(/Step 2 of 6/); assert.ok(button('Download and install')); hides(/Set up in chat/)
    assert.match(dom.window.document.querySelector('.cs-dl').textContent, /GB Studio packages/)
    assert.ok(!dom.window.document.querySelector('.cs-repair'), 'no repair banner on the Setup page itself')
    hides('Start building', 'prompt library must not show during setup')
  })
  check('the toolchain step does not repeat the tools check while it is only read; status polls fast during setup', () => {
    const last = key => scenario.queries.filter(query => query.key === key).at(-1)
    assert.equal(last('doctor').refetchInterval, false)
    assert.equal(last('status').refetchInterval, 4000)
  })

  // 3. Reviewing an earlier step, then the toolchain finishes: review is dropped, page advances, user is told.
  await click('Back')
  check('Back shows the previous step with a Continue button', () => {
    assert.equal(heading(), 'Create the hermretro profile'); shows(/Continue/)
  })
  scenario.notices.length = 0
  scenario.doctor = answered(doctor([]))
  await render()
  check('a verified step advances even while another page is being reviewed, and announces it', () => {
    assert.deepEqual(scenario.notices.map(notice => notice.message), ['Install the game toolchain: done'])
  })
  check('with the game steps done, the page asks whether there is a Chromatic before any hardware step', () => {
    assert.equal(heading(), 'Ready to make games')
    shows(/A physical Chromatic is optional/)
    shows(/Start making games/); shows(/Set up my Chromatic/)
    shows(/4 more steps/)
  })
  await click('Set up my Chromatic')
  check('choosing the Chromatic shows its first step and remembers the choice', () => {
    assert.equal(heading(), 'Update your Chromatic'); assert.equal(scenario.storage.setup.hardwareWanted, true)
    shows(/Step 3 of 6/); shows(/Only for a physical Chromatic/)
  })

  // 4. Steps done outside Hermes are confirmed by the user and remembered.
  await click("I've done this")
  check('manual step: confirming moves on and is remembered', () => {
    assert.equal(heading(), 'Activate Developer Mode'); assert.equal(scenario.storage.setup.firmwareDone, true)
  })
  await click("I've done this")
  check('device software step waits for the backend', () => {
    assert.equal(heading(), "Install ModRetro's device software"); shows(/Install in chat/)
  })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Install in chat'); await settle()
  check('device setup puts its request in the studio composer without sending', () => {
    assert.deepEqual(scenario.calls[0], ['insert', null])
    assert.deepEqual(scenario.inserted.at(-1), [null, "Install ModRetro's Chromatic device software for hermretro so I can use my physical Chromatic."])
    assert.ok(!scenario.calls.some(([kind, argument, method]) =>
      (kind === 'request' && argument === 'prompt.submit') || (kind === 'requestProfile' && method === 'prompt.submit')))
  })
  scenario.status = answered(status({ deps: { toolchain_root: '/h/hermretro/.cache/toolchain', device_cli: cli('installed') } }))
  await render()
  check('device software detected: moves to hardware tools', () => { assert.equal(heading(), 'Turn on hardware tools') })

  // 5. Skipping the hardware part ends setup; it can be resumed.
  await click("Skip, I'll use the emulator")
  check('skip ends setup: the Setup tab says so, emulator only', () => {
    assert.equal(heading(), 'Setup is complete'); shows(/emulator only/)
    assert.equal(scenario.storage.setup.hardwareSkipped, true)
    assert.ok(!nav().querySelector('.pip'), 'no dot once setup is complete')
  })
  check('polling slows down once setup is complete', () => {
    assert.equal(scenario.queries.filter(query => query.key === 'status').at(-1).refetchInterval, 30000)
  })
  await click('Set up my Chromatic')
  check('resuming returns to the unfinished hardware step', () => { assert.equal(currentTab(), 'Setup'); assert.equal(heading(), 'Turn on hardware tools') })
  scenario.status = answered(complete)
  await render()
  check('everything verified: setup complete', () => {
    assert.equal(heading(), 'Setup is complete'); shows(/All 6 steps done/)
  })
  await click('Studio profile')
  check('a finished setup can be reviewed and left again', () => {
    assert.equal(heading(), 'Create the hermretro profile'); shows(/Continue/)
  })
  await click('Continue')
  check('Continue returns to the finished setup', () => { assert.equal(heading(), 'Setup is complete') })
  await click('Game toolchain')
  scenario.byMethod['plugin.hermretro.remove_tools'] = () => ({ ok: true, removed_bytes: 2_400_000_000, root: '/h/hermretro/.cache' })
  scenario.calls.length = 0
  await click('Remove downloaded tools')
  check('Remove downloaded tools asks first and says the games stay', () => {
    shows(/Delete the downloaded tools\? Your games stay/)
    assert.ok(!scenario.calls.some(call => call[1] === 'plugin.hermretro.remove_tools'))
  })
  await click('Remove', dom.window.document.querySelector('.cs-actions:has(> span)') ?? dom.window.document); await settle()
  check('confirming removes them through the backend and reports the size', () => {
    assert.ok(scenario.calls.some(call => call[0] === 'request' && call[1] === 'plugin.hermretro.remove_tools'))
    assert.match(scenario.notices.at(-1).message, /Downloaded tools removed \(2,400 MB\)\. Your games are untouched/)
  })
  delete scenario.byMethod['plugin.hermretro.remove_tools']
  await click('Continue')

  // 6. Something breaks later: the page shows the backend explanation.
  scenario.status = notLoaded
  await render()
  check('a backend that goes away replaces Setup with the explanation', () => {
    assert.equal(heading(), 'hermretro is not switched on in any profile')
  })

  // 7. The app is on a profile without the plugin; another profile has it.
  scenario.ambient = null
  scenario.routes = [{ profile: 'default', connectionId: 'local' }, { profile: 'chromatic-dev', targetProfile: 'chromatic-dev', connectionId: 'local' }]
  scenario.byProfile = { 'chromatic-dev': complete }
  scenario.calls.length = 0
  const found = await scenario.fns.status()
  check('status is read from the profile that has the plugin, without asking the active profile twice', () => {
    assert.equal(found.via_profile, 'chromatic-dev'); assert.equal(found.ok, true)
    assert.deepEqual(scenario.calls, [['request', 'plugin.hermretro.status'], ['profileRoutes'],
      ['requestProfile', 'chromatic-dev', 'plugin.hermretro.status'],
      ['requestProfile', 'chromatic-dev', 'plugin.hermretro.status']])
  })
  scenario.calls.length = 0
  await scenario.fns.status(); await scenario.fns.doctor()
  check('later reads go straight to that profile; the profile list is not rescanned', () => {
    assert.deepEqual(scenario.calls, [['request', 'plugin.hermretro.status'],
      ['requestProfile', 'chromatic-dev', 'plugin.hermretro.status'],
      ['request', 'plugin.hermretro.doctor'],
      ['requestProfile', 'chromatic-dev', 'plugin.hermretro.doctor']])
  })
  scenario.status = answered(found)
  await render()
  await tab('Games')
  check('the page says which profile it is showing', () => {
    const chip = dom.window.document.querySelector('.cs-top .cs-top-profile')
    assert.equal(chip?.textContent, 'chromatic-dev'); assert.match(chip.getAttribute('aria-label'), /Showing the "chromatic-dev" profile/)
  })
  scenario.ambient = complete
  const direct = await scenario.fns.status()
  check('once the active profile has the plugin it is used directly again', () => {
    assert.equal(direct.via_profile, undefined)
  })

  // 8. The focused chat is named without making the gateway authorize it as a live session.
  check('status names the focused chat as "chat", never as session_id', () => {
    assert.deepEqual(scenario.lastParams, { chat: 'rt-1' })
  })
  scenario.status = { isError: true, isFetching: false, error: Object.assign(new Error('not_found'), { code: 4001 }) }
  await render()
  check('a failed status call is reported as a failure, not as "switched off"', () => {
    assert.equal(heading(), "Could not read hermretro's status"); shows(/not_found/)
    hides('not switched on')
  })

  scenario.status = answered(complete)
  await render()
  check('once status answers again the page is back and the Setup card is gone', () => {
    assert.equal(currentTab(), 'Games'); hides('Check what is already installed')
  })

  // 8a. The Build page runs only in the hermretro profile: no fallback to the profile the app is on.
  scenario.status = answered(status({ profile: { name: 'default', is_studio: false, create: { name: 'hermretro' },
    studio: { name: 'hermretro', exists: true, installed: false, ours: true } } }))
  scenario.calls.length = 0
  await render(); await tab('Build')
  check('without a working hermretro profile, Build shows a repair panel and starts no session anywhere', () => {
    shows(/The hermretro profile needs repair/); assert.ok(button('Repair'))
    assert.ok(!dom.window.document.querySelector('.cs-b'), 'no Build conversation')
    assert.ok(!scenario.calls.some(call => call[1] === 'session.create' || call[2] === 'session.create'))
  })
  scenario.byMethod['plugin.hermretro.studio_profile'] = () => ({ ok: true, profile: 'hermretro' })
  scenario.calls.length = 0
  await act(async () => { dom.window.document.querySelector('.cs-studio-needed button').click() }); await settle()
  check('Repair finishes the existing profile again (no second profile is created)', () => {
    const requests = scenario.calls.filter(call => call[0] === 'request').map(call => call[1])
    assert.ok(requests.includes('plugin.hermretro.studio_profile')); assert.ok(!requests.includes('profiles.create'))
  })
  scenario.status = answered(status({ profile: { name: 'default', is_studio: false, create: { name: 'hermretro' },
    studio: { name: 'hermretro', exists: true, installed: true, ours: true } } }))
  await render()
  check('a finished profile that never answers still offers Repair while it waits', () => {
    shows(/Waiting for Hermes to start it/)
    assert.ok(dom.window.document.querySelector('.cs-studio-needed button'))
  })
  delete scenario.byMethod['plugin.hermretro.studio_profile']
  scenario.status = answered(complete)
  await render(); await tab('Games')
  await act(async () => { root.unmount() })
})
