// Drives the real hermretro page in jsdom: the header nav, the setup wizard (one step per
// page, automatic advance when a step verifies) and the Home, Prompts, Games and Emulator pages.
// Needs react, react-dom and jsdom from a Hermes Desktop checkout:
//   node tests/desktop/wizard_test.mjs [path to apps/desktop/node_modules]
import assert from 'node:assert/strict'
import { cpSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const modules = process.argv[2] || process.env.HERMES_DESKTOP_NODE_MODULES ||
  path.join(os.homedir(), '.hermes', 'hermes-agent', 'apps', 'desktop', 'node_modules')
const work = mkdtempSync(path.join(os.tmpdir(), 'chromatic-wizard-'))

try {
  symlinkSync(modules, path.join(work, 'node_modules'), 'dir')
  cpSync(path.join(here, 'sdk-stub.mjs'), path.join(work, 'sdk-stub.mjs'))
  writeFileSync(path.join(work, 'plugin.mjs'),
    readFileSync(path.join(here, '..', '..', 'desktop', 'plugin.js'), 'utf8').replace("'@hermes/plugin-sdk'", "'./sdk-stub.mjs'"))
  writeFileSync(path.join(work, 'run.mjs'), `
    import { JSDOM } from 'jsdom'
    const dom = new JSDOM('<!doctype html><div id="root"></div>')
    globalThis.window = dom.window; globalThis.document = dom.window.document
    globalThis.IS_REACT_ACT_ENVIRONMENT = true
    const { createRoot } = await import('react-dom/client')
    const { act } = await import('react')
    const { emit, host, scenario } = await import('./sdk-stub.mjs')
    const plugin = (await import('./plugin.mjs')).default
    export { act, createRoot, dom, emit, host, plugin, scenario }
  `)
  const { act, createRoot, dom, emit, host, plugin, scenario } = await import(pathToFileURL(path.join(work, 'run.mjs')).href)

  const registrations = []
  const intervals = []
  const ctx = {
    registerMany: list => registrations.push(...list),
    setTimeout: (fn, ms) => { const id = setTimeout(fn, 0); return () => clearTimeout(id) },
    setInterval: (fn, ms) => { intervals.push({ fn, ms }); return () => { intervals.splice(intervals.findIndex(i => i.fn === fn), 1) } },
    os: { writeClipboard: async () => true, openExternal: async () => true },
    storage: { get: (key, fallback) => scenario.storage[key] ?? fallback, set: (key, value) => { scenario.storage[key] = value } }
  }
  plugin.register(ctx)
  const page = registrations.find(entry => entry.area === 'routes')
  const root = createRoot(dom.window.document.getElementById('root'))
  const render = async () => { await act(async () => { root.render(page.render()) }) }
  const text = () => dom.window.document.body.textContent.replace(/\s+/g, ' ')
  const heading = () => dom.window.document.querySelector('h2')?.textContent ?? null
  const HOME = 'Make a game.Play it tonight.'
  const headings = () => [...dom.window.document.querySelectorAll('h2')].map(node => node.textContent)
  const click = async (label, scope = dom.window.document) => {
    const button = [...scope.querySelectorAll('button')].find(node => node.textContent.includes(label))
    assert.ok(button, 'button not found: ' + label)
    await act(async () => { button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  }
  const nav = () => dom.window.document.querySelector('nav[aria-label="Studio pages"]')
  const tab = async name => {
    const button = [...nav().querySelectorAll('button')].find(node => node.textContent === name || node.firstChild?.textContent === name)
    assert.ok(button, 'tab not found: ' + name)
    await act(async () => { button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  }
  const currentTab = () => nav()?.querySelector('[aria-current="page"]')?.firstChild?.textContent ?? null
  const settle = async (ms = 20) => { await act(async () => { await new Promise(resolve => setTimeout(resolve, ms)) }) }
  const button = label => [...dom.window.document.querySelectorAll('button')].find(node => node.textContent.includes(label))
  const typeInto = async (input, value) => {
    const proto = input.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(input, value)
    await act(async () => { input.dispatchEvent(new dom.window.Event('input', { bubbles: true })) })
  }
  const key = async (type, keyName, target = dom.window) => {
    await act(async () => { target.dispatchEvent(new dom.window.KeyboardEvent(type, { key: keyName, bubbles: true, cancelable: true })) })
  }
  const answered = data => ({ data, isFetching: false, isPending: false })
  const notLoaded = { isError: true, error: Object.assign(new Error('unknown method'), { code: -32601 }), isFetching: false }
  const cli = state => ({ state, version: state === 'installed' ? '1.2.1' : null, terms: 'https://modretro.com/eula' })
  const status = (extra = {}) => ({
    ok: true, plugin: { version: '0.0.4' }, platform: { system: 'linux', machine: 'x86_64', qualified: true },
    node: { found: true, version: '26.13.0', required: '22', ok: true }, engine: { present: true, version: '1.0.34', verified: true },
    hardware_enabled: false, project: null,
    profile: { name: 'hermretro', is_studio: true, studio: { name: 'hermretro', exists: true, installed: true, ours: true } },
    deps: { inside_plugin: true, toolchain_root: '/p/deps/toolchain', device_cli: cli('missing') }, ...extra
  })
  const doctor = missing => ({ ok: true, missing_required: missing, components: [
    { id: 'cli', label: 'GB Studio CLI', status: missing.length ? 'missing' : 'ready', required: '4.3.2', optional: false }] })
  const checks = []
  const check = (name, fn) => { fn(); checks.push(name) }

  // 1. Not switched on anywhere: an explanation, not a setup step.
  scenario.status = notLoaded
  await render()
  check('one segmented control in the header: Home · Setup · Prompts · Games · Emulator, Home first', () => {
    assert.deepEqual([...nav().querySelectorAll('button')].map(node => node.firstChild.textContent), ['Home', 'Setup', 'Prompts', 'Games', 'Emulator'])
    assert.equal(currentTab(), 'Home')
  })
  check('with the backend off there are no setup steps, only how to switch it on', () => {
    assert.deepEqual(headings(), ['hermretro is not switched on in any profile'])
    assert.ok(!/Step \d of/.test(text()), 'no step counter')
    assert.match(text(), /Open Capabilities/)
    assert.ok(!text().includes('Start building'), 'prompt library must not show')
  })


  // 1b. First run: a new user sees only the guided setup, and the page installs the tools itself.
  const createParams0 = { name: 'hermretro', description: 'hermretro', no_skills: true, share_auth: true, no_alias: true }
  const firstRun = status({ profile: { name: 'default', is_studio: false, create: createParams0,
    studio: { name: 'hermretro', exists: false, installed: false, ours: false } } })
  const manifest = { bytes: 708_271_425, disk_bytes: 2_300_000_000, measured_on: 'linux-x64', exact: true, items: [
    { id: 'gbdk', component: 'gbdk', name: 'GBDK compiler', version: '4.5.0', source: 'github.com/gbdk-2020/gbdk-2020', bytes: 6_870_728, purpose: 'Compiles C for the Game Boy CPU', approx: false },
    { id: 'gbstudio', component: 'cli', name: 'GB Studio CLI', version: '4.3.2', source: 'github.com/chrismaltby/gb-studio', bytes: 18_130_254, purpose: 'Builds your game into a ROM', approx: false },
    { id: 'packages', component: 'cli', name: 'GB Studio packages', version: 'yarn 4.4.1', source: 'registry.npmjs.org', bytes: 551_000_000, purpose: 'The libraries GB Studio needs', approx: true },
    { id: 'uv', component: 'uv', name: 'uv', version: '0.12.6', source: 'github.com/astral-sh/uv', bytes: 20_274_889, purpose: 'Installs the Python parts', approx: false },
    { id: 'emulator', component: 'emulator', name: 'Python, PyBoy and Pillow', version: '3.13.12 · 2.7.0 · 12.3.0', source: 'python-build-standalone · pypi.org', bytes: 108_000_000, purpose: 'The emulator Hermes playtests with', approx: true }] }
  const installAnswer = install => answered({ ok: true, manifest, root: '/p/deps/toolchain', install })
  scenario.storage = {}
  scenario.status = answered(firstRun); scenario.doctor = answered(doctor(['cli'])); scenario.install = installAnswer({ state: 'idle' })
  await render()
  check('first run: only the welcome, no segmented nav, Home or prompts', () => {
    assert.equal(nav(), null)
    assert.equal(dom.window.document.querySelector('h1')?.textContent, HOME)
    assert.ok(button('Get started')); assert.match(text(), /≈ 708 MB download · ≈ 2\.3 GB on disk/)
    assert.ok(!dom.window.document.querySelector('.cs-home, .cs-quick, .cs-stat'), 'no Home, quick starts or Studio panel')
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
    assert.match(text(), /Node\.js 26\.13\.0 \(from Hermes\)/); assert.match(text(), /\/p\/deps\/toolchain/)
    assert.ok(button('Download and install')); assert.ok(!/Set up in chat/.test(text()), 'the install never goes through a chat')
    assert.match(dom.window.document.querySelector('.cs-onb-steps').getAttribute('aria-label'), /step 1 of 3: Install/)
    assert.equal(nav(), null)
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
    assert.match(text(), /40%/); assert.match(text(), /281 MB downloaded/)
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
    assert.equal(heading(), "One part didn't finish"); assert.match(text(), /ENOTFOUND registry\.npmjs\.org/)
    assert.ok(button('Try again')); assert.ok(button('Ask Hermes to fix it'))
  })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Ask Hermes to fix it'); await settle()
  check('Ask Hermes opens a new chat with the error in the prompt (not sent)', () => {
    assert.ok(scenario.calls.some(call => call[0] === 'newChat'))
    assert.match(scenario.inserted.at(-1)[1], /stopped with this error:\ncli: yarn: ENOTFOUND/)
  })
  scenario.install = installAnswer({ state: 'done', started_at: 1, fraction: 1 })
  scenario.status = answered(status()); scenario.doctor = answered(doctor([]))
  await render()
  check('tools verified and profile made: Do you have a Chromatic?', () => {
    assert.equal(heading(), 'Do you have a Chromatic?'); assert.equal(nav(), null)
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
  check('Start in chat opens a new chat with the idea, ends onboarding and shows the studio', () => {
    assert.ok(scenario.calls.some(call => call[0] === 'newChat'))
    assert.match(scenario.inserted.at(-1)[1], /make a new Game Boy Color game: a tiny platformer where a frog/)
    assert.equal(scenario.storage.setup.onboarded, true)
    assert.equal(currentTab(), 'Home'); assert.match(text(), /Ready to make games in the emulator/)
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
  check('install already running in a chat: waits and keeps checking, no failure', () => {
    assert.match(text(), /being installed from a chat/); assert.ok(!button('Try again'))
    assert.equal(scenario.queries.filter(query => query.key === 'doctor').at(-1).refetchInterval, 8000)
  })
  await act(async () => { root.render(null) })

  // 2. After onboarding the toolchain breaks: Home says so and Setup repairs it (Node.js is not a step).
  scenario.storage = { setup: { onboarded: true } }
  scenario.status = answered(status()); scenario.doctor = answered(doctor(['cli'])); scenario.install = installAnswer({ state: 'idle' })
  await render()
  await tab('Home')
  check('while setup is incomplete Home leads with Continue setup and greys out the quick starts', () => {
    assert.equal(heading(), HOME); assert.match(text(), /Next: Game toolchain/)
    // The hero and the Studio list count the same thing (done steps, like the Setup rail).
    assert.match(text(), /Setup: 1 of 2 done/); assert.match(dom.window.document.querySelector(".cs-stat").textContent, /Setup1 of 2 done/)
    assert.match(dom.window.document.querySelector('.cs-repair').textContent, /Game toolchain needs attention/)
    assert.ok(!/Setup: step \d/.test(text()), 'no step-position counter that could disagree with the done count')
    assert.match(text(), /after setup/); assert.ok(button('Plan a game').disabled, 'quick starts wait for setup')
    assert.ok(nav().querySelector('.pip'), 'the Setup tab shows a dot while setup is incomplete')
  })
  await click('Continue setup')
  check('Continue setup opens the Setup tab', () => { assert.equal(currentTab(), 'Setup') })
  check('one step per page, starting at the first incomplete one', () => {
    assert.deepEqual(headings(), ['Install the game toolchain'])
    assert.match(text(), /Step 2 of 6/); assert.ok(button('Download and install')); assert.ok(!/Set up in chat/.test(text()))
    assert.match(dom.window.document.querySelector('.cs-dl').textContent, /GB Studio packages/)
    assert.ok(!dom.window.document.querySelector('.cs-repair'), 'no repair banner on the Setup page itself')
    assert.ok(!text().includes('Start building'), 'prompt library must not show during setup')
  })
  check('toolchain step polls the check; status polls fast during setup', () => {
    const last = key => scenario.queries.filter(query => query.key === key).at(-1)
    assert.equal(last('doctor').refetchInterval, 8000)
    assert.equal(last('status').refetchInterval, 4000)
  })

  // 3. Reviewing an earlier step, then the toolchain finishes: review is dropped, page advances, user is told.
  await click('Back')
  check('Back shows the previous step with a Continue button', () => {
    assert.equal(heading(), 'Create the hermretro profile'); assert.match(text(), /Continue/)
  })
  scenario.notices.length = 0
  scenario.doctor = answered(doctor([]))
  await render()
  check('a verified step advances even while another page is being reviewed, and announces it', () => {
    assert.deepEqual(scenario.notices.map(notice => notice.message), ['Install the game toolchain: done'])
  })
  check('with the game steps done, the page asks whether there is a Chromatic before any hardware step', () => {
    assert.equal(heading(), 'Ready to make games')
    assert.match(text(), /A physical Chromatic is optional/)
    assert.match(text(), /Start making games/); assert.match(text(), /Set up my Chromatic/)
    assert.match(text(), /4 more steps/)
  })
  await click('Set up my Chromatic')
  check('choosing the Chromatic shows its first step and remembers the choice', () => {
    assert.equal(heading(), 'Update your Chromatic'); assert.equal(scenario.storage.setup.hardwareWanted, true)
    assert.match(text(), /Step 3 of 6/); assert.match(text(), /Only for a physical Chromatic/)
  })

  // 4. Steps done outside Hermes are confirmed by the user and remembered.
  await click("I've done this")
  check('manual step: confirming moves on and is remembered', () => {
    assert.equal(heading(), 'Activate Developer Mode'); assert.equal(scenario.storage.setup.firmwareDone, true)
  })
  await click("I've done this")
  check('device software step waits for the backend', () => {
    assert.equal(heading(), "Install ModRetro's device software"); assert.match(text(), /Install in chat/)
  })
  scenario.status = answered(status({ deps: { inside_plugin: true, toolchain_root: '/p/deps/toolchain', device_cli: cli('installed') } }))
  await render()
  check('device software detected: moves to hardware tools', () => { assert.equal(heading(), 'Turn on hardware tools') })

  // 5. Skipping the hardware part ends setup; it can be resumed.
  await click("Skip, I'll use the emulator")
  check('skip ends setup: the Setup tab says so, emulator only', () => {
    assert.equal(heading(), 'Setup is complete'); assert.match(text(), /emulator only/)
    assert.equal(scenario.storage.setup.hardwareSkipped, true)
    assert.ok(!nav().querySelector('.pip'), 'no dot once setup is complete')
  })
  await tab('Home')
  check('Home in emulator-only mode', () => {
    assert.equal(heading(), HOME); assert.match(text(), /Ready to make games in the emulator/)
    assert.match(text(), /Your Chromatic is not set up, so streaming and flashing are off/)
    assert.ok(!button('Plan a game').disabled, 'quick starts are live once setup is complete')
    assert.ok(button('Play my game'), 'the play quick start is named for what it does now'); assert.ok(!/Play in browser/.test(text()))
  })
  await tab('Prompts')
  await click('Flash a cartridge', dom.window.document.querySelector('nav[aria-label="Prompts"]'))
  check('in emulator-only mode the hardware prompts are shown but locked', () => {
    assert.equal(dom.window.document.querySelector('h2').textContent, 'Start building')
    assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Flash a cartridge')
    assert.match(text(), /Needs your Chromatic/)
    assert.ok(button('Start a new chat').disabled && button('Add to current chat').disabled, 'a locked prompt cannot go to a chat')
    assert.ok(dom.window.document.querySelector('[data-copy]'), 'but it can still be copied')
  })
  check('polling slows down once setup is complete', () => {
    assert.equal(scenario.queries.filter(query => query.key === 'status').at(-1).refetchInterval, 30000)
  })
  await click('Set up my Chromatic')
  check('resuming returns to the unfinished hardware step', () => { assert.equal(currentTab(), 'Setup'); assert.equal(heading(), 'Turn on hardware tools') })
  const complete = status({ hardware_enabled: true, deps: { inside_plugin: true, toolchain_root: '/p/deps/toolchain', device_cli: cli('installed') } })
  scenario.status = answered(complete)
  await render()
  check('everything verified: setup complete', () => {
    assert.equal(heading(), 'Setup is complete'); assert.match(text(), /All 6 steps done/)
  })
  await tab('Prompts')
  check('hardware prompts unlock once hardware tools are on', () => {
    assert.ok(!text().includes('Needs your Chromatic')); assert.ok(!button('Start a new chat').disabled)
  })
  await tab('Setup')
  await click('Studio profile')
  check('a finished setup can be reviewed and left again', () => {
    assert.equal(heading(), 'Create the hermretro profile'); assert.match(text(), /Continue/)
  })
  await click('Continue')
  check('Continue returns to the finished setup', () => { assert.equal(heading(), 'Setup is complete') })

  // 6. Something breaks later: the page says so instead of showing prompts.
  scenario.status = notLoaded
  await render()
  check('a backend that goes away replaces the prompts with the explanation', () => {
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
  await tab('Home')
  check('the page says which profile it is showing', () => {
    assert.equal(heading(), HOME); assert.match(text(), /Showing the "chromatic-dev" profile/)
  })
  scenario.calls.length = 0
  await click('Use in chat')
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  check('"Use in chat" opens a chat in that profile, never the current composer', () => {
    assert.deepEqual(scenario.calls[0], ['newChat', 'chromatic-dev'])
    assert.ok(!scenario.calls.some(call => call[0] === 'insert' && call[1] !== 'new'))
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
    assert.equal(heading(), "Could not read hermretro's status"); assert.match(text(), /not_found/)
    assert.ok(!text().includes('not switched on'))
  })

  scenario.status = answered(complete)
  await render()
  check('ready page explains the studio and drops the Setup card', () => {
    assert.match(text(), /Build your game by chatting/); assert.ok(!text().includes('Check what is already installed'))
  })
  await act(async () => { root.unmount() })

  // 9. The panes docked beside the chat.
  const panes = registrations.filter(entry => entry.area === 'panes')
  check('two panes are contributed (closing a plugin\'s only pane would disable it)', () => {
    assert.deepEqual(panes.map(pane => pane.id), ['live', 'worklog'])
    assert.deepEqual(panes[0].data.dock, { pane: 'workspace', pos: 'right' })
    assert.deepEqual(panes[1].data.dock, { pane: 'hermretro:live', pos: 'bottom' })
  })
  const mount = async entry => {
    const node = dom.window.document.createElement('div'); dom.window.document.body.appendChild(node)
    const paneRoot = createRoot(node)
    await act(async () => { paneRoot.render(entry.render()) })
    return { node, rerender: async () => { await act(async () => { paneRoot.render(entry.render()) }) }, close: async () => { await act(async () => { paneRoot.unmount() }); node.remove() } }
  }
  const now = Date.now() / 1000
  scenario.activity = { ...answered({ ok: true, running: true, lane: null, matched: null }), dataUpdatedAt: Date.now() }
  let game = await mount(panes[0])
  check('game pane with no game yet offers to start one', () => {
    assert.match(game.node.textContent, /No game is open yet/); assert.match(game.node.textContent, /Start a game/)
  })
  scenario.activity = { ...answered({
    ok: true, running: true, matched: 'chat',
    lane: { project_name: 'MoonGarden', project_root: '/games/MoonGarden', alive: true, busy: true, current_tool: 'rom_build', preview_url: null },
    frame: { t: now - 12, tool: 'emulator_step', frame: 180, src: 'data:image/png;base64,AAAA' },
    build: { t: now - 90, ok: true, seconds: 6.7, rom: '/games/MoonGarden/build/game.gb' },
    events: [
      { t: now - 200, tool: 'project_create', kind: 'select', ok: true, seconds: 0.1 },
      { t: now - 90, tool: 'rom_build', kind: 'project-write', ok: true, seconds: 6.7 },
      { t: now - 30, tool: 'scene_update', kind: 'project-write', ok: false, seconds: 0.1, error: 'STALE_REVISION' }
    ]
  }), dataUpdatedAt: Date.now() }
  await game.rerender()
  check('game pane shows the project, what is running, the latest real frame and the last build', () => {
    const shown = game.node.textContent
    assert.match(shown, /MoonGarden/); assert.match(shown, /Building the ROM…/)
    assert.equal(game.node.querySelector('img').getAttribute('src'), 'data:image/png;base64,AAAA')
    assert.match(shown, /frame 180 · 12s ago/); assert.match(shown, /Last build succeeded · 2 min ago/)
    assert.match(shown, /Build and playtest/); assert.match(shown, /Play it myself/)
  })

  // 10. Hermes tests headless: the pane shows a still of what it last saw, and runs no player of its own.
  check('the pane shows the last screen the agent saw, as a still', () => {
    assert.equal(game.node.querySelector('img[alt="What Hermes last saw in its playtest"]').getAttribute('src'), 'data:image/png;base64,AAAA')
    assert.equal(intervals.length, 0)
    assert.ok(!('plugin.hermretro.replay' in scenario.paramsByMethod))
  })
  await game.close()
  const log = await mount(panes[1])
  check('log pane lists the work newest first, in plain words, with failures', () => {
    const rows = [...log.node.querySelectorAll('[role="log"] > div')].map(row => row.textContent)
    assert.equal(rows.length, 3)
    assert.match(rows[0], /Failed: Edited a scene/); assert.match(rows[0], /STALE_REVISION/)
    assert.match(rows[1], /Built the ROM/); assert.match(rows[2], /Created the project/)
  })
  await log.close()
  scenario.ambient = { ok: true, lane: null, matched: null }
  scenario.lastParams = null
  await scenario.fns.activity()
  check('the panes ask about the focused chat by both of its ids', () => {
    assert.deepEqual(scenario.lastParams, { chat: 'rt-1', stored: 'st-1' })
  })

  // 8b. Someone without a Chromatic: one click from the choice page to the studio.
  const kept = scenario.storage
  scenario.storage = {}
  scenario.status = answered(status()); scenario.doctor = answered(doctor([]))
  const fresh = await mount(page)
  check('a fresh user starts on Home', () => { assert.equal(currentTab(), 'Home'); assert.equal(heading(), HOME) })
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
    assert.match(css, /rotateY\(-14deg\) rotateX\(6deg\) rotateZ\(16deg\)/)
    assert.match(css, /prefers-reduced-motion: reduce\) \{[^}]*\.cs-flyer \* \{ animation: none/)
  })
  const flyerNode = dom.window.document.querySelector('.cs-flyer')
  await click('Studio profile')
  check('moving between steps keeps the same flyer element, so its animation does not restart', () => {
    assert.equal(dom.window.document.querySelector('.cs-flyer'), flyerNode)
  })
  await click('Continue')
  await tab('Home')
  check('the page carries its stylesheet and artwork', () => {
    const css = dom.window.document.querySelector('style')?.textContent ?? ''
    assert.match(css, /\.cs-page/); assert.match(css, /prefers-reduced-motion/)
    assert.ok(!/#[0-9a-f]{3,6}\b|rgb\(/i.test(css), 'colours come from theme variables only')
    assert.ok(dom.window.document.querySelector('.cs-art'), 'artwork is drawn')
    const vars = dom.window.document.querySelector('.cs-page').getAttribute('style')
    for (const name of ['--cs-hermes', '--cs-cart', '--cs-fly-body', '--cs-fly-wing']) assert.match(vars, new RegExp(`${name}: url\\("data:image/png;base64,`))
  })
  await fresh.close()
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
  scenario.byMethod['plugin.hermretro.activity'] = { ok: true, matched: 'chat', lane: { project_root: '/games/here' } }
  const mine = await scenario.fns.activity()
  delete scenario.byMethod['plugin.hermretro.activity']
  check('a chat that lives in the profile the app is on still shows its own game in the panes', () => {
    assert.equal(mine.lane.project_root, '/games/here')
  })
  scenario.status = answered(moved)
  await studioPage.rerender()
  await tab('Home')
  scenario.calls.length = 0
  await click('Use in chat')
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  check('setup is complete and prompts open chats in the studio profile', () => {
    assert.equal(heading(), HOME); assert.deepEqual(scenario.calls[0], ['newChat', 'hermretro'])
  })
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

  // 12. Games, Prompts and the Emulator, fed by the games / player RPCs (docs/dev/STUDIO-PAGES.md).
  scenario.status = answered({ ...complete, hardware_enabled: false }); scenario.doctor = answered(doctor([]))
  scenario.storage = { setup: { hardwareSkipped: true } }
  const now2 = Math.round(Date.now() / 1000)
  const games = [
    { id: 'aaa111aaa111', title: 'Comet Drift', projectRoot: '/home/u/ChromaticGames/CometDrift', kind: 'gbstudio', state: 'ready',
      rom: { path: '/home/u/ChromaticGames/CometDrift/build/web/rom/game.gbc', sha256: 'sha-one', size: 262144, builtAt: now2 - 120 },
      webExport: true, thumb: 'data:image/png;base64,AAAA', chat: { sessionId: 'stored-comet', title: 'Comet Drift — first level' }, error: null },
    { id: 'bbb222bbb222', title: 'Robo Run', projectRoot: '/home/u/ChromaticGames/RoboRun', kind: 'gbdk', state: 'failed', rom: null,
      webExport: false, thumb: null, chat: null, error: 'background uses 212 tiles (limit 192)' }
  ]
  scenario.games = answered({ games, gamesDir: '/home/u/plugins/hermretro/games', device: { hardwareEnabled: true, skipped: false } })
  scenario.player = { isPending: true }
  const studio = await mount(page)
  await click('Refresh') // forget the profile route left over from the cases above
  check('Home continues with the last game from the games RPC', () => {
    assert.equal(heading(), HOME)
    assert.equal(dom.window.document.querySelector('.cs-cont .name').textContent, 'Comet Drift')
    assert.match(text(), /Chat: Comet Drift — first level/)
  })
  await tab('Games')
  check('Games shows each game as the real cartridge with its title screen, state and meta, plus a blank cartridge', () => {
    const cards = [...dom.window.document.querySelectorAll('.cs-gcard')]
    assert.equal(cards.length, 3)
    assert.equal(cards[0].querySelector('.cs-cart .slot img').getAttribute('src'), 'data:image/png;base64,AAAA')
    assert.match(cards[0].textContent, /Ready/); assert.match(cards[0].textContent, /GB Studio/); assert.match(cards[0].textContent, /256 KB/)
    assert.match(cards[1].textContent, /Build failed/); assert.match(cards[1].textContent, /Fix in chat/)
    assert.match(cards[2].textContent, /Blank cartridge/)
    assert.match(text(), /Games · 2 in your studio/)
  })
  check('without hardware tools Install is locked and the strip offers to set up the Chromatic', () => {
    assert.ok(button('Install').disabled); assert.match(text(), /Playing in the emulator/)
  })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Fix in chat')
  await settle()
  check('Fix in chat puts the build error into a chat, not sent', () => {
    assert.ok(scenario.inserted.some(([, value]) => /212 tiles/.test(value) && /Robo Run/.test(value)))
    assert.ok(!scenario.calls.some(call => /send|submit/i.test(call[0])))
  })
  scenario.status = answered({ ...complete, hardware_enabled: true })
  await studio.rerender()
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Install')
  await settle()
  check("Install sends the flash prompt, naming the game, to that game's own chat (the chat's approval gate applies)", () => {
    assert.deepEqual(scenario.calls[0], ['openSession', 'stored-comet', null])
    const [, value] = scenario.inserted.at(-1)
    assert.match(value, /^Flash the built ROM of "Comet Drift" \(\/home\/u\/ChromaticGames\/CometDrift\) to the connected Chromatic cartridge/)
  })
  scenario.games = { isError: true, isFetching: false, error: Object.assign(new Error('unknown method'), { code: -32601 }) }
  await studio.rerender()
  check('a backend without the games RPC is reported honestly', () => { assert.match(text(), /cannot list your games yet/) })
  scenario.games = answered({ games: [], device: { hardwareEnabled: true, skipped: false } })
  await studio.rerender()
  check('an empty library offers a new game and the remix', () => { assert.equal(heading(), 'No games yet'); assert.match(text(), /Remix Wrecklight/) })
  // The Emulator never shows an empty page: with nothing of the user's to play it loads the demo cartridge.
  scenario.games = answered({ games: [], demo: { id: 'demo', title: 'Hello Color', kind: 'gbdk', note: 'ModRetro example' }, device: { hardwareEnabled: true, skipped: false } })
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/demo/index.html', romSha256: 'sha-demo', title: 'Hello Color', demo: true })
  scenario.byMethod['plugin.hermretro.player'] = params => ({ url: `http://127.0.0.1:4567/tok/${params.id}/index.html` })
  await tab('Emulator')
  check('an empty library still shows the player: the demo cartridge in a sandboxed frame', () => {
    const demoFrame = dom.window.document.querySelector('.cs-rp-stage iframe')
    assert.ok(demoFrame, 'the player frame is shown')
    assert.equal(demoFrame.getAttribute('src'), 'http://127.0.0.1:4567/tok/demo/index.html')
    assert.equal(demoFrame.getAttribute('data-sandbox'), 'allow-scripts allow-downloads')
    assert.ok(!/the player is not available/i.test(text())); assert.ok(!/Nothing to play yet/.test(text()))
  })
  await scenario.fns.player()
  check('the player RPC is asked for the demo id', () => { assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.player'], { id: 'demo' }) })
  check('the bar above the player holds only its controls: no game tabs, demo chip or profile line, and no Install for the demo', () => {
    assert.ok(!dom.window.document.querySelector('.cs-rp-games')); assert.ok(!/Demo cartridge/.test(text())); assert.ok(!button('Make your first game'))
    assert.ok(!/Showing the "/.test(text())); assert.ok(!button('Install')); assert.match(text(), /Ask Hermes/)
  })
  check('every bar button keeps an accessible name when a narrow pane hides its label (.cs-lbl)', () => {
    const bar = dom.window.document.querySelector('.cs-rp-bar')
    for (const name of ['Ask Hermes', 'Captures', 'Full screen']) {
      assert.ok(bar.querySelector(`button[aria-label="${name}"]`), `${name} has an aria-label`)
    }
    assert.ok([...bar.querySelectorAll('.cs-lbl')].some(node => node.textContent === 'Captures'))
    assert.ok(dom.window.document.querySelector('.cs-top button[aria-label="Refresh"] .cs-lbl'), 'Refresh label can hide too')
  })
  scenario.player = notLoaded
  await tab('Prompts')
  await tab('Emulator')
  check('an old backend without the player RPC: a compact notice with the reason and Refresh, above an empty device area', () => {
    const note = dom.window.document.querySelector('.cs-rp-note')
    assert.ok(note, 'notice shown')
    assert.match(note.textContent, /This profile is running an older copy of the hermretro backend\. Reload the plugin \(Capabilities › Plugins, switch it off and on\) and press Refresh\./)
    assert.ok([...note.querySelectorAll('button')].some(node => node.textContent.includes('Refresh')))
    const stage = dom.window.document.querySelector('.cs-rp-stage')
    assert.ok(note.compareDocumentPosition(stage) & dom.window.Node.DOCUMENT_POSITION_FOLLOWING, 'the notice sits above the device area')
    assert.ok(stage.querySelector('.cs-rp-void')); assert.ok(!stage.querySelector('iframe'))
    assert.ok(!/the player is not available/i.test(text()))
  })
  scenario.player = { isError: true, isFetching: false, error: new Error('gateway timed out') }
  await studio.rerender()
  check('any other player failure shows its real reason in the same notice', () => {
    assert.match(dom.window.document.querySelector('.cs-rp-note').textContent, /gateway timed out/)
  })
  delete scenario.byMethod['plugin.hermretro.player']
  scenario.player = { isPending: true }
  await tab('Games')
  scenario.games = answered({ games, gamesDir: '/home/u/plugins/hermretro/games', device: { hardwareEnabled: true, skipped: false } })
  await studio.rerender()

  // Prompts: the Reader.
  await click('New game', dom.window.document.querySelector('.cs-shelf'))
  check('the blank cartridge opens the Create a new game prompt', () => {
    assert.equal(currentTab(), 'Prompts'); assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Create a new game')
  })
  check('the Reader lists the prompts grouped Plan / Create / Play / Polish / On your Chromatic', () => {
    const groups = [...dom.window.document.querySelectorAll('.cs-rgrp > span:first-child')].map(node => node.textContent)
    assert.deepEqual(groups, ['Plan', 'Create', 'Play', 'Polish', 'On your Chromatic'])
    assert.equal(dom.window.document.querySelectorAll('.cs-ritem').length, 11)
  })
  const area = () => dom.window.document.querySelector('.cs-rdetail textarea')
  check('{folder}/{name} become inputs; the folder defaults to the plugin games folder', () => {
    assert.equal(dom.window.document.getElementById('cs-f-folder').value, '/home/u/plugins/hermretro/games')
    assert.equal(dom.window.document.getElementById('cs-f-name').value, 'MoonGarden')
    assert.match(area().value, /new GB Studio project at \/home\/u\/plugins\/hermretro\/games\/MoonGarden\. Make a small exploration game/)
  })
  await typeInto(dom.window.document.getElementById('cs-f-name'), 'StarFarm')
  check('editing the name rewrites the prompt', () => {
    assert.match(area().value, /\/home\/u\/plugins\/hermretro\/games\/StarFarm\./)
  })
  await typeInto(area(), 'My own words')
  check('the prompt text is editable and can be reset', () => { assert.equal(area().value, 'My own words'); assert.ok(button('Reset text')) })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await click('Start a new chat')
  await settle()
  check('Start a new chat opens a new chat and puts the edited text in its composer', () => {
    assert.deepEqual(scenario.calls[0], ['newChat', null]); assert.deepEqual(scenario.inserted.at(-1), ['new', 'My own words'])
  })
  await click('Reset text')
  check('Reset text restores the prompt', () => { assert.match(area().value, /StarFarm/) })
  scenario.calls.length = 0
  await click('Add to current chat')
  await settle()
  check('Add to current chat goes to the composer the user is in first', () => { assert.deepEqual(scenario.calls[0], ['insert', null]) })
  await key('keydown', 'ArrowDown', dom.window.document.body)
  check('↓ moves to the next prompt', () => { assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Remix an example') })
  await typeInto(dom.window.document.querySelector('.cs-search input'), 'palette')
  check('search filters the list', () => {
    assert.deepEqual([...dom.window.document.querySelectorAll('.cs-ritem')].map(node => node.textContent), ['Update the palette'])
    assert.equal(dom.window.document.querySelector('.cs-rdetail h3').textContent, 'Update the palette')
  })

  // Emulator: Play on the shelf opens ModRetro's player in a sandboxed frame.
  await tab('Games')
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-one', title: 'Comet Drift' })
  await click('Play')
  const frame = () => dom.window.document.querySelector('.cs-rp-stage iframe')
  check('Play switches to the Emulator page and loads the player RPC url in a sandboxed frame', () => {
    assert.equal(currentTab(), 'Emulator')
    assert.equal(frame().getAttribute('src'), 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html')
    assert.equal(frame().getAttribute('data-sandbox'), 'allow-scripts allow-downloads')
    assert.match(text(), /Ask Hermes/); assert.match(text(), /Captures/); assert.match(text(), /Keyboard/)
    assert.ok(!text().includes('Hermes rebuilt'))
  })
  const posted = []
  frame().contentWindow.postMessage = message => posted.push(message)
  await key('keydown', 'ArrowLeft', dom.window.document.body); await key('keyup', 'ArrowLeft', dom.window.document.body)
  await key('keydown', 'q', dom.window.document.body)
  check('game keys typed on the page reach the frame; other keys do not', () => {
    assert.deepEqual(posted.filter(message => message.type === 'key').map(message => [message.key, message.down]), [['ArrowLeft', true], ['ArrowLeft', false]])
  })
  const kept2 = frame()
  await tab('Home')
  check('leaving the Emulator keeps the frame loaded but hidden, and holds the game', () => {
    assert.equal(frame(), kept2); assert.ok(dom.window.document.querySelector('.cs-rp-stage.off'))
    assert.deepEqual(posted.at(-1), { cs: 'cmd', type: 'hold' })
    assert.ok(nav().querySelector('.live'), 'the Emulator tab shows that a game is loaded')
  })
  await tab('Emulator')
  check('coming back releases it, without reloading the frame', () => {
    assert.equal(frame(), kept2); assert.deepEqual(posted.at(-1), { cs: 'cmd', type: 'release' })
  })
  scenario.byMethod['plugin.hermretro.capture_image'] = params => ({ path: `/home/u/ChromaticGames/CometDrift/captures/${params.id}.png` })
  scenario.calls.length = 0; scenario.inserted.length = 0
  await act(async () => {
    dom.window.dispatchEvent(new dom.window.MessageEvent('message', { source: frame().contentWindow, data: {
      cs: 'annotate', target: { name: 'Sprite 1; tile 00', role: 'game-sprite', metadata: { oam: 1, tile: 0 } }, note: 'The jump is too low', image: 'data:image/png;base64,AAAA' } }))
  })
  await settle()
  check("an annotation is saved through capture_image and put into the game's chat with the note and screenshot path, not sent", () => {
    assert.deepEqual(scenario.paramsByMethod['plugin.hermretro.capture_image'], { id: 'aaa111aaa111', png: 'data:image/png;base64,AAAA' })
    assert.deepEqual(scenario.calls.map(call => call[0]).slice(0, 3), ['request', 'openSession', 'insert'])
    assert.deepEqual(scenario.calls[1], ['openSession', 'stored-comet', null])
    const [, value] = scenario.inserted.at(-1)
    assert.match(value, /I marked Sprite 1; tile 00 \(sprite\)/); assert.match(value, /The jump is too low/)
    assert.match(value, /"oam":1/); assert.match(value, /Screenshot: \/home\/u\/ChromaticGames\/CometDrift\/captures\/aaa111aaa111\.png/)
  })
  scenario.byMethod['plugin.hermretro.capture_image'] = () => { throw Object.assign(new Error('unknown method'), { code: -32601 }) }
  scenario.notices.length = 0; scenario.inserted.length = 0
  await act(async () => {
    dom.window.dispatchEvent(new dom.window.MessageEvent('message', { source: frame().contentWindow, data: { cs: 'annotate', target: { name: 'Background' }, note: 'too dark', image: 'data:image/png;base64,AAAA' } }))
  })
  await settle()
  check('without capture_image the note still reaches the chat and the missing screenshot is reported', () => {
    assert.match(scenario.inserted.at(-1)[1], /too dark/); assert.ok(!/Screenshot:/.test(scenario.inserted.at(-1)[1]))
    assert.ok(scenario.notices.some(notice => notice.kind === 'warning' && /cannot save screenshots yet/.test(notice.message)))
  })
  await act(async () => {
    dom.window.dispatchEvent(new dom.window.MessageEvent('message', { source: dom.window, data: { cs: 'annotate', target: { name: 'spoof' } } }))
  })
  await settle()
  check('messages that do not come from the player frame are ignored', () => { assert.ok(!scenario.inserted.some(([, value]) => /spoof/.test(value))) })
  scenario.games = answered({ games: [{ ...games[0], rom: { ...games[0].rom, sha256: 'sha-two' } }, games[1]], device: { hardwareEnabled: true, skipped: false } })
  await studio.rerender()
  check('a rebuild in chat (new ROM hash) shows the banner', () => { assert.match(text(), /Hermes rebuilt Comet Drift/); assert.match(text(), /Load the new build/) })
  check('the games list polls every 5 s while the Emulator is shown', () => {
    assert.equal(scenario.queries.filter(query => query.key === 'games').at(-1).refetchInterval, 5000)
  })
  await click('Later')
  check('Later hides the banner for that build', () => { assert.ok(!text().includes('Hermes rebuilt')) })
  scenario.player = { isError: true, isFetching: false, error: Object.assign(new Error('unknown method'), { code: -32601 }) }
  await studio.rerender()
  check('a backend without the player RPC is reported honestly', () => { assert.match(text(), /older copy of the hermretro backend/); assert.ok(dom.window.document.querySelector('.cs-rp-note')) })
  scenario.player = answered({ error: 'Comet Drift has no web export yet. Ask Hermes in its chat to build it.' })
  await studio.rerender()
  check("the player's own error is shown with a way to build it", () => { assert.match(text(), /has no web export yet/); assert.match(text(), /Build it in chat/) })

  // 13. The emulator beside the chat opens only when the agent presents the game (chromatic_present_game).
  const pageFrame = () => studio.node.querySelector('.cs-rp-stage iframe')
  const library13 = [
    { ...games[0], rom: { ...games[0].rom, sha256: 'native-one' }, web: { sha256: 'sha-one', builtAt: now2 - 60 } },
    games[1],
    { id: 'ccc333ccc333', title: 'Star Farm', projectRoot: '/home/u/ChromaticGames/StarFarm', kind: 'gbstudio', state: 'ready',
      rom: { path: '/x.gbc', sha256: 'native-star', size: 1, builtAt: now2 - 30 }, web: { sha256: 'web-star', builtAt: now2 - 30 },
      webExport: true, thumb: null, chat: { sessionId: 'stored-star', title: 'Star Farm' }, error: null }
  ]
  scenario.byMethod['plugin.hermretro.games'] = () => ({ ok: true, games: library13, device: { hardwareEnabled: true, skipped: false } })
  // The backend answers with its own clock (here ahead of this one) and only presentations after `since`.
  const backendNow = Date.now() / 1000 + 50
  let shownByBackend = []
  scenario.byMethod['plugin.hermretro.presentations'] = params =>
    ({ ok: true, now: backendNow, presentations: shownByBackend.filter(item => params?.since == null || item.t > params.since) })
  scenario.games = answered({ games: library13, device: { hardwareEnabled: true, skipped: false } })
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-one', title: 'Comet Drift' })
  await studio.rerender()
  check('the Emulator page keeps Open beside the chat under the player, with no auto-open setting', () => {
    const row = studio.node.querySelector('.cs-rp-foot')
    assert.ok(row, 'row shown'); assert.ok(!row.querySelector('input[type=checkbox]'), 'no setting')
    assert.ok(!/after a build/.test(row.textContent)); assert.match(row.textContent, /when it is ready for you to try/)
    assert.ok([...row.querySelectorAll('button')].some(node => node.textContent.includes('Open beside the chat')))
    assert.ok(!/beside the chat/.test(studio.node.querySelector('.cs-rp-bar').textContent))
    assert.ok(pageFrame(), 'the page runs the game')
  })
  const finish = async (sessionId, name, result, extra = {}) => {
    await act(async () => { emit({ type: 'tool.complete', session_id: sessionId, payload: { tool_id: 't' + Math.random(), name, args: {}, result, ...extra } }) })
    await settle()
  }
  const built = { structuredContent: { success: true }, player: { ready: true }, nextStep: 'call chromatic_present_game' }
  const presented = (gameId, title, note = null, presentedAt = Math.random()) =>
    ({ ok: true, studio: { gameId, playerUrl: `http://127.0.0.1:4567/tok/${gameId}/index.html`, title, note, presentedAt }, message: 'Shown to the user beside the chat.' })
  await finish('rt-comet', 'chromatic_rom_build', { isError: true, error: 'compile failed' })
  await finish('rt-comet', 'chromatic_rom_build', built)
  await finish('rt-comet', 'chromatic_web_preview', { structuredContent: { success: true, url: 'http://e/' } })
  // A build result from an older backend that still names the Studio player opens nothing either.
  await finish('rt-comet', 'chromatic_rom_build', { ...built, studioGameId: 'aaa111aaa111', studioPlayerUrl: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html' })
  await finish('rt-comet', 'chromatic_present_game', { ok: false, code: 'BUILD_FIRST', error: 'Run chromatic_rom_build first.' })
  await finish('rt-comet', 'chromatic_present_game', presented('aaa111aaa111', 'Comet Drift'), { error: 'tool failed' })
  await finish('rt-comet', 'chromatic_emulator_step', presented('aaa111aaa111', 'Comet Drift'))
  check('build completion opens NOTHING (nor failed presents or other tools)', () => { assert.equal(scenario.workspaces.length, 0); assert.ok(pageFrame()) })
  await finish('rt-comet', 'chromatic_present_game', presented('aaa111aaa111', 'Comet Drift', 'Try the double jump on the second ledge.', 101))
  const tabs = () => scenario.workspaces.filter(tab => !tab.closed)
  check('chromatic_present_game opens one tab docked right of the chat, titled after the game', () => {
    assert.equal(scenario.workspaces.length, 1)
    const [tab] = scenario.workspaces
    assert.equal(tab.id, 'hermretro.emulator.aaa111aaa111'); assert.equal(tab.options.title, 'Emulator · Comet Drift')
    assert.deepEqual(tab.options.dock, { pane: 'workspace', pos: 'right' }); assert.equal(typeof tab.options.render, 'function')
  })
  const side = await mount({ render: scenario.workspaces[0].options.render })
  const sideFrame = () => side.node.querySelector('.cs-rp-stage iframe')
  const sideReload = () => scenario.queries.filter(query => query.key === 'player' && query.queryKey?.[2] === 'side').at(-1)?.queryKey?.[4]
  await studio.rerender()
  check('one live player: the presented tab runs the game, the page says where it is', () => {
    assert.ok(sideFrame(), 'the tab runs the player'); assert.equal(sideFrame().getAttribute('src'), 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html')
    assert.ok(!pageFrame(), 'the page dropped its frame'); assert.match(studio.node.textContent, /Playing beside the chat/)
    assert.ok([...studio.node.querySelectorAll('button')].some(node => node.textContent.includes('Bring it here')))
    assert.match(side.node.textContent, /Ask Hermes/); assert.match(side.node.textContent, /Captures/); assert.match(side.node.textContent, /Keyboard/)
  })
  check('the note appears as a slim line above the player in the tab', () => {
    const note = side.node.querySelector('.cs-side-note')
    assert.ok(note, 'note shown'); assert.match(note.textContent, /Try the double jump on the second ledge\./)
    const order = [...side.node.querySelector('.cs-side').children]
    assert.ok(order.indexOf(note) < order.indexOf(side.node.querySelector('.cs-rp-stage')), 'above the player')
  })
  check("the tab compares the web export's own ROM: a fresh build is not reported as rebuilt", () => { assert.ok(!side.node.textContent.includes('Hermes rebuilt')) })
  await click('Bring it here', studio.node)
  check('Bring it here moves the game back to the page and the tab shows a placeholder', () => {
    assert.ok(pageFrame()); assert.ok(!sideFrame()); assert.match(side.node.textContent, /Playing in hermretro/)
  })
  await click('Bring it here', side.node)
  check('and back beside the chat again', () => { assert.ok(sideFrame()); assert.ok(!pageFrame()) })
  await tab('Games'); await tab('Emulator')
  check('visiting the Emulator page again does not take (and restart) the game playing beside the chat', () => {
    assert.ok(sideFrame()); assert.ok(!pageFrame()); assert.match(studio.node.textContent, /Playing beside the chat/)
  })
  const sidePosted = []
  sideFrame().contentWindow.postMessage = message => sidePosted.push(message)
  await key('keydown', 'ArrowRight', dom.window.document.body)
  check('beside the chat, keys typed in the chat do not reach the game', () => { assert.equal(sidePosted.length, 0) })
  await act(async () => { side.node.querySelector('.cs-rp-bar').dispatchEvent(new dom.window.Event('pointerdown', { bubbles: true })) })
  await key('keydown', 'ArrowRight', dom.window.document.body)
  check('after a click in the tab, they do', () => { assert.deepEqual(sidePosted.filter(m => m.type === 'key').map(m => m.key), ['ArrowRight']) })
  await act(async () => { side.node.querySelector('.cs-side-note-x').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  check('the note can be dismissed', () => { assert.ok(!side.node.querySelector('.cs-side-note')) })
  const reloadBefore = sideReload()
  const frameBefore = sideFrame()
  library13[0] = { ...library13[0], web: { sha256: 'sha-two', builtAt: now2 } }
  scenario.games = answered({ games: library13, device: { hardwareEnabled: true, skipped: false } })
  await finish('rt-comet', 'chromatic_rom_build', built)
  await side.rerender()
  check('a rebuild without a presentation opens nothing and shows the rebuilt banner in the open tab, without reloading', () => {
    assert.equal(scenario.workspaces.length, 1); assert.equal(scenario.workspaces[0].fronted ?? 0, 0)
    assert.match(side.node.textContent, /Hermes rebuilt Comet Drift/); assert.match(side.node.textContent, /Load the new build/)
    assert.equal(sideReload(), reloadBefore); assert.equal(sideFrame(), frameBefore)
  })
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-two', title: 'Comet Drift' })
  await finish('rt-comet', 'chromatic_present_game', presented('aaa111aaa111', 'Comet Drift', 'Now the ledge is lower: try it again.', 102))
  await side.rerender()
  check('presenting again fronts the same tab and loads the newest build directly, with the new note', () => {
    assert.equal(tabs().length, 1); assert.equal(scenario.workspaces.length, 1); assert.equal(scenario.workspaces[0].fronted, 1)
    assert.equal(sideReload(), reloadBefore + 1, 'player asked again'); assert.notEqual(sideFrame(), frameBefore, 'new frame')
    assert.ok(!side.node.textContent.includes('Hermes rebuilt'), 'no banner: it is the newest build')
    assert.match(side.node.querySelector('.cs-side-note').textContent, /Now the ledge is lower/)
  })
  await finish('rt-comet', 'chromatic_present_game', presented('aaa111aaa111', 'Comet Drift', 'Now the ledge is lower: try it again.', 102))
  check('the same presentation heard twice is acted on once', () => { assert.equal(scenario.workspaces[0].fronted, 1); assert.equal(sideReload(), reloadBefore + 1) })
  await click('Open beside the chat', studio.node)
  check("the user's own Open beside the chat on the Emulator page still works", () => {
    assert.equal(tabs().length, 1); assert.equal(scenario.workspaces[0].fronted, 2)
  })
  await act(async () => { scenario.workspaces[0].close() })
  await side.close()
  await studio.rerender()
  check('closing the tab frees the game: the Emulator page takes it back', () => { assert.ok(pageFrame()); assert.equal(tabs().length, 0) })
  await finish('rt-comet', 'chromatic_rom_build', built)
  check('later builds never reopen a closed tab', () => { assert.equal(scenario.workspaces.length, 1) })
  await finish('stored-star', 'chromatic_present_game', presented('ccc333ccc333', 'Star Farm', null, backendNow + 0.25))
  check('presenting another game opens its own tab', () => {
    assert.equal(scenario.workspaces.length, 2); assert.equal(scenario.workspaces[1].options.title, 'Emulator · Star Farm')
  })
  const star = await mount({ render: scenario.workspaces[1].options.render })
  check('no note → no note line', () => { assert.ok(!star.node.querySelector('.cs-side-note')) })
  await act(async () => { scenario.workspaces[1].close() })
  await star.close()
  const openWorkspace = host.openWorkspace
  delete host.openWorkspace
  library13.push({ ...library13[2], id: 'ddd444ddd444', title: 'Moon Garden', chat: { sessionId: 'stored-moon' } })
  await finish('rt-moon', 'chromatic_present_game', presented('ddd444ddd444', 'Moon Garden', 'Hi', 104))
  await studio.rerender()
  check('on a desktop without openWorkspace nothing breaks: no tab, the page keeps its player, no Open beside the chat', () => {
    assert.equal(scenario.workspaces.length, 2); assert.ok(pageFrame()); assert.ok(!button('Open beside the chat'))
  })
  host.openWorkspace = openWorkspace
  // A gateway with tool progress off sends no tool.complete: turn ends ask `presentations` instead.
  plugin.register({ ...ctx, registerMany: () => {} })
  const opened = scenario.workspaces.length
  const turnEnd = async sessionId => { await act(async () => { emit({ type: 'message.complete', session_id: sessionId, payload: {} }) }); await settle() }
  await turnEnd('rt-x')
  check('a turn end with no new presentation opens nothing, and asks with a since timestamp', () => {
    assert.equal(scenario.workspaces.length, opened)
    assert.equal(typeof scenario.paramsByMethod['plugin.hermretro.presentations']?.since, 'number')
  })
  library13.push({ ...library13[2], id: 'eee555eee555', title: 'Night Owl', chat: { sessionId: 'stored-owl' }, web: { sha256: 'owl-1', builtAt: now2 + 5 } })
  library13[0] = { ...library13[0], web: { sha256: 'sha-three', builtAt: now2 + 6 } }
  await turnEnd('rt-owl')
  check('a turn end after a build alone (no presentation) opens nothing', () => { assert.equal(scenario.workspaces.length, opened) })
  shownByBackend = [{ gameId: 'eee555eee555', title: 'Night Owl', t: backendNow + 0.5, note: 'Find the owl', sessionId: 'rt-owl' }]
  await turnEnd('rt-owl')
  check('presentations fallback: a turn end that finds a presentation opens it beside the chat', () => {
    assert.equal(scenario.workspaces.length, opened + 1); assert.equal(scenario.workspaces.at(-1).options.title, 'Emulator · Night Owl')
    assert.equal(scenario.paramsByMethod['plugin.hermretro.presentations'].since, backendNow - 1, 'since follows the backend clock')
  })
  await turnEnd('rt-owl')
  check('the fallback never repeats a presentation it already acted on', () => {
    assert.equal(scenario.workspaces.length, opened + 1); assert.equal(scenario.workspaces.at(-1).fronted ?? 0, 0)
  })
  shownByBackend = [{ gameId: 'ccc333ccc333', title: 'Star Farm', t: backendNow + 0.25, note: null }]
  await turnEnd('rt-star')
  check('nor one first heard through tool.complete', () => { assert.equal(scenario.workspaces.length, opened + 1) })
  await act(async () => { scenario.workspaces.at(-1).close() })
  delete scenario.byMethod['plugin.hermretro.presentations']
  await turnEnd('rt-old')
  check('an older backend without the presentations RPC breaks nothing', () => { assert.equal(scenario.workspaces.length, opened + 1) })
  await studio.close()

  console.log(JSON.stringify({ passed: true, checks: checks.length, names: checks }, null, 1))
} finally {
  rmSync(work, { recursive: true, force: true })
}
