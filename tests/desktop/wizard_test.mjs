// Drives the real hermretro page in jsdom: the header nav, the setup wizard (one step per
// page, automatic advance when a step verifies) and the Home, Prompts, Games and Emulator pages.
// It loads the built desktop/plugin.js (what ships); after editing desktop-src/ run node tools/bundle.mjs first.
// Needs react, react-dom and jsdom (tools/node-modules.mjs says where they come from):
//   node tests/desktop/wizard_test.mjs [path to a node_modules folder]
// Assert DOM presence and identity as booleans so failures do not inspect React's object graph.
import assert from 'node:assert/strict'
import { cpSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { staleReasons } from '../../tools/bundle.mjs'
import { findModules, MISSING_HINT } from '../../tools/node-modules.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
// The page under test is the built bundle: never test one that no longer matches desktop-src/.
const stale = staleReasons()

if (stale.length) {
  console.error(`${stale.join('\n')}\nRun: node tools/bundle.mjs`)
  process.exit(1)
}

const modules = process.argv[2] || findModules(['react', 'react-dom', 'jsdom'])

if (!modules) {
  console.error(`react, react-dom and jsdom were not found; ${MISSING_HINT}`)
  process.exit(1)
}
const work = mkdtempSync(path.join(os.tmpdir(), 'chromatic-wizard-'))
// Interrupted (Ctrl+C, a CI timeout): still remove the temp folder.
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => { rmSync(work, { recursive: true, force: true }); process.exit(130) })
}

try {
  symlinkSync(modules, path.join(work, 'node_modules'), 'dir')
  cpSync(path.join(here, 'sdk-stub.mjs'), path.join(work, 'sdk-stub.mjs'))
  writeFileSync(path.join(work, 'plugin.mjs'),
    readFileSync(path.join(here, '..', '..', 'desktop', 'plugin.js'), 'utf8').replace(/(['"])@hermes\/plugin-sdk\1/g, "'./sdk-stub.mjs'"))
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
    os: { writeClipboard: async () => true, openExternal: async () => true, revealPath: async path => { scenario.revealed = path; return true } },
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
    ok: true, plugin: { version: '9.9.9' }, platform: { system: 'linux', machine: 'x86_64', qualified: true },
    node: { found: true, version: '26.13.0', required: '22', ok: true }, engine: { present: true, version: '1.0.34', verified: true },
    hardware_enabled: false, project: null,
    profile: { name: 'hermretro', is_studio: true, studio: { name: 'hermretro', exists: true, installed: true, ours: true } },
    deps: { toolchain_root: '/h/hermretro/.cache/toolchain', device_cli: cli('missing') }, ...extra
  })
  const doctor = missing => ({ ok: true, missing_required: missing, components: [
    { id: 'cli', label: 'GB Studio CLI', status: missing.length ? 'missing' : 'ready', required: '4.3.2', optional: false }] })
  const checks = []
  const check = (name, fn) => { fn(); checks.push(name) }

  // 1. Not switched on anywhere: an explanation, not a setup step.
  scenario.status = notLoaded
  await render()
  check('one segmented control in the header: Home · Build · Setup · Prompts · Games · Emulator, Home first', () => {
    assert.deepEqual([...nav().querySelectorAll('button')].map(node => node.firstChild.textContent), ['Home', 'Build', 'Setup', 'Prompts', 'Games', 'Emulator'])
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
  const installAnswer = install => answered({ ok: true, manifest, root: '/h/hermretro/.cache/toolchain', install })
  scenario.storage = {}
  scenario.status = answered(firstRun); scenario.doctor = answered(doctor(['cli'])); scenario.install = installAnswer({ state: 'idle' })
  await render()
  check('first run: only the welcome, no segmented nav, Home or prompts', () => {
    assert.ok(!nav())
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
    assert.match(text(), /Node\.js 26\.13\.0 \(from Hermes\)/); assert.match(text(), /\/h\/hermretro\/\.cache\/toolchain/)
    assert.ok(button('Download and install')); assert.ok(!/Set up in chat/.test(text()), 'the install never goes through a chat')
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
  scenario.status = answered(status({ deps: { toolchain_root: '/h/hermretro/.cache/toolchain', device_cli: cli('installed') } }))
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
  const complete = status({ hardware_enabled: true, deps: { toolchain_root: '/h/hermretro/.cache/toolchain', device_cli: cli('installed') } })
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
  await click('Game toolchain')
  scenario.byMethod['plugin.hermretro.remove_tools'] = () => ({ ok: true, removed_bytes: 2_400_000_000, root: '/h/hermretro/.cache' })
  scenario.calls.length = 0
  await click('Remove downloaded tools')
  check('Remove downloaded tools asks first and says the games stay', () => {
    assert.match(text(), /Delete the downloaded tools\? Your games stay/)
    assert.ok(!scenario.calls.some(call => call[1] === 'plugin.hermretro.remove_tools'))
  })
  await click('Remove', dom.window.document.querySelector('.cs-actions:has(> span)') ?? dom.window.document); await settle()
  check('confirming removes them through the backend and reports the size', () => {
    assert.ok(scenario.calls.some(call => call[0] === 'request' && call[1] === 'plugin.hermretro.remove_tools'))
    assert.match(scenario.notices.at(-1).message, /Downloaded tools removed \(2,400 MB\)\. Your games are untouched/)
  })
  delete scenario.byMethod['plugin.hermretro.remove_tools']
  await click('Continue')

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
    assert.equal(heading(), HOME)
    const chip = dom.window.document.querySelector('.cs-top .cs-top-profile')
    assert.equal(chip?.textContent, 'chromatic-dev'); assert.match(chip.getAttribute('aria-label'), /Showing the "chromatic-dev" profile/)
  })
  scenario.calls.length = 0
  await click('Use in chat')
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
  check('"Use in chat" never opens a chat outside the hermretro profile, nor uses the current composer', () => {
    assert.ok(!scenario.calls.some(call => call[0] === 'newChat' || call[0] === 'insert'))
    assert.match(scenario.notices.at(-1).message, /hermretro profile is not set up yet/)
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

  // 8a. The Build page runs only in the hermretro profile: no fallback to the profile the app is on.
  scenario.status = answered(status({ profile: { name: 'default', is_studio: false, create: { name: 'hermretro' },
    studio: { name: 'hermretro', exists: true, installed: false, ours: true } } }))
  scenario.calls.length = 0
  await render(); await tab('Build')
  check('without a working hermretro profile, Build shows a repair panel and starts no session anywhere', () => {
    assert.match(text(), /The hermretro profile needs repair/); assert.ok(button('Repair'))
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
    assert.match(text(), /Waiting for Hermes to start it/)
    assert.ok(dom.window.document.querySelector('.cs-studio-needed button'))
  })
  delete scenario.byMethod['plugin.hermretro.studio_profile']
  scenario.status = answered(complete)
  await render(); await tab('Home')
  await act(async () => { root.unmount() })

  // 9. No panes beside the chat: the agent's work and the game live on the Build page.
  check('the plugin contributes no panes (closing a plugin\'s only pane would switch it off)', () => {
    assert.equal(registrations.filter(entry => entry.area === 'panes').length, 0)
  })
  const mount = async entry => {
    const node = dom.window.document.createElement('div'); dom.window.document.body.appendChild(node)
    const paneRoot = createRoot(node)
    await act(async () => { paneRoot.render(entry.render()) })
    return { node, rerender: async () => { await act(async () => { paneRoot.render(entry.render()) }) }, close: async () => { await act(async () => { paneRoot.unmount() }); node.remove() } }
  }
  const now = Date.now() / 1000

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
    assert.ok(dom.window.document.querySelector('.cs-flyer') === flyerNode, 'the flyer element is retained')
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
  scenario.games = answered({ games, gamesDir: '/home/u/.hermes/hermretro/games', device: { hardwareEnabled: true, skipped: false } })
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
    assert.match(cards[0].textContent, /Ready/); assert.doesNotMatch(cards[0].textContent, /GB Studio/)
    assert.match(cards[0].querySelector('.cs-gline').getAttribute('title'), /256 KB/)
    assert.match(cards[0].querySelector('.cs-split .main').textContent, /^Play$/)
    assert.match(cards[1].textContent, /Build failed/); assert.match(cards[1].querySelector('.cs-split .main').textContent, /Fix in chat/)
    assert.match(cards[1].textContent, /212 tiles/)
    assert.equal(cards[0].querySelectorAll('.cs-split > button, .cs-split > span > button').length, 2, 'one split control per card')
    assert.ok(!dom.window.document.querySelector('.cs-dev'), 'no hardware strip above a full shelf')
    assert.match(cards[2].textContent, /Blank cartridge/)
    assert.doesNotMatch(text(), /in your studio|Games showcase/)
  })
  scenario.revealed = null
  await click('Open games folder')
  check('the shelf shows the games folder and opens it', () => {
    assert.match(dom.window.document.querySelector('.cs-gfolder').textContent, /\/home\/u\/\.hermes\/hermretro\/games/)
    assert.equal(scenario.revealed, '/home/u/.hermes/hermretro/games')
  })
  const openGameMenu = async card => {
    await act(async () => { card.querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    return card.querySelector('.cs-gmenu')
  }
  const firstCard = () => dom.window.document.querySelectorAll('.cs-gcard')[0]
  check('the split arrow is closed until pressed', () => { assert.ok(!firstCard().querySelector('.cs-gmenu')) })
  {
    const menu = await openGameMenu(firstCard())
    check('without hardware tools Install is locked in the menu and the header chip offers to set up the Chromatic', () => {
      const install = [...menu.querySelectorAll('button')].find(node => /Install on Chromatic/.test(node.textContent))
      assert.ok(install.disabled); assert.match(install.textContent, /Needs your Chromatic/)
      assert.match(menu.textContent, /Open its chat/); assert.match(menu.textContent, /Show in folder/)
      assert.match(text(), /Emulator only · Set up my Chromatic/)
    })
    await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape' })) })
    check('Escape closes the game menu', () => { assert.ok(!firstCard().querySelector('.cs-gmenu')) })
  }
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
  await click('Install on Chromatic', await openGameMenu(firstCard()))
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
    assert.ok(!dom.window.document.querySelector('.cs-top-profile')); assert.ok(!button('Install')); assert.match(text(), /Ask Hermes/)
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
  scenario.games = answered({ games, gamesDir: '/home/u/.hermes/hermretro/games', device: { hardwareEnabled: true, skipped: false } })
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
    assert.equal(dom.window.document.getElementById('cs-f-folder').value, '/home/u/.hermes/hermretro/games')
    assert.equal(dom.window.document.getElementById('cs-f-name').value, 'MoonGarden')
    assert.match(area().value, /new GB Studio project at \/home\/u\/\.hermes\/hermretro\/games\/MoonGarden\. Make a small exploration game/)
  })
  await typeInto(dom.window.document.getElementById('cs-f-name'), 'StarFarm')
  check('editing the name rewrites the prompt', () => {
    assert.match(area().value, /\/home\/u\/\.hermes\/hermretro\/games\/StarFarm\./)
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
    assert.ok(frame() === kept2, 'the player frame is retained'); assert.ok(dom.window.document.querySelector('.cs-rp-stage.off'))
    assert.deepEqual(posted.at(-1), { cs: 'cmd', type: 'hold' })
    assert.ok(nav().querySelector('.live'), 'the Emulator tab shows that a game is loaded')
  })
  await tab('Emulator')
  check('coming back releases it, without reloading the frame', () => {
    assert.ok(frame() === kept2, 'the player frame is retained'); assert.deepEqual(posted.at(-1), { cs: 'cmd', type: 'release' })
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
    assert.equal(sideReload(), reloadBefore); assert.ok(sideFrame() === frameBefore, 'the player frame is retained')
  })
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/aaa111aaa111/index.html', romSha256: 'sha-two', title: 'Comet Drift' })
  await finish('rt-comet', 'chromatic_present_game', presented('aaa111aaa111', 'Comet Drift', 'Now the ledge is lower: try it again.', 102))
  await side.rerender()
  check('presenting again fronts the same tab and loads the newest build directly, with the new note', () => {
    assert.equal(tabs().length, 1); assert.equal(scenario.workspaces.length, 1); assert.equal(scenario.workspaces[0].fronted, 1)
    assert.equal(sideReload(), reloadBefore + 1, 'player asked again'); assert.ok(sideFrame() !== frameBefore, 'new frame')
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


  // 14. Build: one game, one conversation, driven through the gateway and the event stream.
  // The games are a menu on the title: open it, take a copy, close it again.
  const gamesMenu = async view => {
    await act(async () => { view.node.querySelector('.cs-b-sw').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    const menu = view.node.querySelector('.cs-b-sw-pop').cloneNode(true)
    await key('keydown', 'Escape')
    return menu
  }
  const fire = (node, type, init = {}) => act(async () => { node.dispatchEvent(new dom.window.MouseEvent(type, { bubbles: true, cancelable: true, ...init })) })
  const editAGame = async view => {
    await fire(view.node.querySelector('.cs-b-sw'), 'click')
    const edit = [...view.node.querySelectorAll('.cs-b-sw-pop button')].find(node => /Edit a game/.test(node.textContent))
    await fire(edit, 'click')
  }
  // Edit a game's list: open the menu, go to the library, take a copy, back out with Escape twice.
  const libraryMenu = async view => {
    await editAGame(view)
    const menu = view.node.querySelector('.cs-b-sw-pop').cloneNode(true)
    await key('keydown', 'Escape'); await key('keydown', 'Escape')
    return menu
  }
  const pickFromLibrary = async (view, title) => {
    await editAGame(view)
    await fire([...view.node.querySelectorAll('.cs-b-sw-list button')].find(node => node.textContent.includes(title)), 'click')
    await settle()
  }
  scenario.status = answered({ ...complete, hardware_enabled: false }); scenario.doctor = answered(doctor([]))
  scenario.storage = { setup: { hardwareSkipped: true, onboarded: true }, page: 'build' }
  scenario.ambient = complete; scenario.routes = []; scenario.byProfile = {}
  const lib14 = [{ id: 'fff666fff666', title: 'Frog Post', projectRoot: '/home/u/games/FrogPost', kind: 'gbstudio', state: 'ready',
    rom: null, webExport: true, thumb: null, chat: null, error: null }]
  scenario.games = answered({ games: lib14, device: { hardwareEnabled: false, skipped: true } })
  const submits = []
  let created = 0
  scenario.byMethod['session.create'] = params => { created += 1; scenario.lastCreate = params; return { session_id: `rt-new-${created}`, stored_session_id: `st-new-${created}`, messages: [] } }
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }
  scenario.byMethod['session.resume'] = params => ({ session_id: `rt-of-${params.session_id}`, messages: [
    { role: 'user', content: 'make the frog jump' }, { role: 'assistant', content: [{ type: 'text', text: 'Added a jump.' }],
      tool_calls: [{ id: 't0', function: { name: 'chromatic_rom_build' } }] },
    { role: 'tool', tool_call_id: 't0', content: '{}' }, { role: 'user', text: 'secret', display_kind: 'hidden' }] })
  scenario.byMethod['session.interrupt'] = params => { scenario.interrupted = params; return { ok: true } }
  const buildCalls = []
  let buildAnswer = params => ({ ok: true })
  scenario.byMethod['plugin.hermretro.build'] = params => { buildCalls.push(params); return buildAnswer(params) }
  const build14 = await mount(page)
  await click('Refresh')
  await tab('Build')
  let menu14 = await gamesMenu(build14)
  const shelf14 = await libraryMenu(build14)
  check('Build opens on New Game: one centred composer and two explained choices, no name field, genre chips or hardware choice', () => {
    const page = build14.node.querySelector('.cs-b-new')
    assert.match(page.querySelector('h1').textContent, /^What are we making\?$/)
    assert.ok(page.querySelector('.cs-b-comp textarea[aria-label="Your game idea"]'), 'the Build page composer')
    assert.ok(!page.querySelector('input'), 'no name field')
    const opts = [...page.querySelectorAll('[role="radiogroup"] [role="radio"]')]
    assert.deepEqual(opts.map(o => o.querySelector('b').textContent), ['Build it', 'Plan first'])
    assert.deepEqual(opts.map(o => o.getAttribute('aria-checked')), ['true', 'false'], 'Build it is the default')
    assert.match(opts[0].textContent, /quick questions.*shows it to you in the emulator/)
    assert.match(opts[1].textContent, /brief, backlog and test plan\. Nothing is built until you say so/)
    assert.ok(!/Game Boy\b(?! Color)/.test(page.textContent.replace('Game Boy Color', '')), 'no hardware choice')
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'New game')
  })
  check('the menu lists only games being edited; the rest of the library is under Edit a game', () => {
    assert.match(menu14.textContent, /New gameEdit a game/)
    assert.ok(!/Frog Post/.test(menu14.textContent)); assert.ok(!/Editing now/.test(menu14.textContent))
    assert.match(shelf14.textContent, /Frog Post/); assert.ok(shelf14.querySelector('input[aria-label="Search your games"]'))
    assert.ok(!build14.node.querySelector('.cs-b-sw-pop'), 'Escape backs out of the list, then closes the menu')
  })
  await typeInto(build14.node.querySelector('textarea[aria-label="Your game idea"]'), 'a lighthouse keeper in a storm')
  build14.node.querySelector('[role="radio"][data-mode="plan"]').click()
  await settle()
  check('choosing Plan first checks it, and the send button says it starts planning', () => {
    assert.equal(build14.node.querySelector('[data-mode="plan"]').getAttribute('aria-checked'), 'true')
    assert.equal(build14.node.querySelector('[data-mode="build"]').getAttribute('aria-checked'), 'false')
    assert.equal(build14.node.querySelector('.cs-b-new .cs-b-send').getAttribute('aria-label'), 'Start planning')
  })
  build14.node.querySelector('[role="radio"][data-mode="build"]').click()
  await settle()
  // The real gateway answers a New Game's first message "queued" (its own queue, nothing ahead): it starts at once.
  const plainSubmit14 = scenario.byMethod['prompt.submit']
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { status: 'queued', forwarded: true } }
  build14.node.querySelector('.cs-b-new .cs-b-send').click()
  await settle()
  scenario.byMethod['prompt.submit'] = plainSubmit14
  check('a first message Hermes answers "queued" with no turn running stays in the conversation, not in the queue', () => {
    assert.ok(!build14.node.querySelector('.cs-b-user.queued'))
    assert.equal(build14.node.querySelector('.cs-b-user').textContent, 'a lighthouse keeper in a storm')
  })
  check('sending makes a hidden New game session, records it as a New Game with no name, then sends the idea as written', () => {
    assert.equal(scenario.lastCreate.hidden, true); assert.equal(scenario.lastCreate.title, 'New game')
    assert.deepEqual(buildCalls.at(-1), { action: 'start', stored: 'st-new-1', name: null, plan: false })
    assert.equal(submits.at(-1).session_id, 'rt-new-1'); assert.match(submits.at(-1).submission_id, /^uuid-/)
    assert.equal(submits.at(-1).text, 'a lighthouse keeper in a storm', 'the backend tells the agent how to start')
  })
  menu14 = await gamesMenu(build14)
  check('the new game is listed as working, with its own conversation open and the user\'s words in a bubble', () => {
    assert.match(menu14.textContent, /Editing nowNew gameHermRetro is working/, 'unnamed until the agent creates the project')
    assert.ok(menu14.querySelector('.cs-b-spin'))
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'New game')
    assert.equal(build14.node.querySelector('.cs-b-user').textContent, 'a lighthouse keeper in a storm')
  })
  check('while the agent works, the status line above the message box says so, and Stop is there', () => {
    assert.match(build14.node.querySelector('.cs-b-status').textContent, /HermRetro is thinking/)
    assert.ok(button('Stop'))
  })
  // Text streams in batches (one render per frame); everything else lands at once.
  const ev = (type, payload, extra = {}) => act(async () => { emit({ type, session_id: 'rt-new-1', payload, ...extra }); await new Promise(resolve => setTimeout(resolve, 80)) })
  await ev('message.start', { turn_id: 'T1' }, { seq: 1 })
  await ev('message.delta', { text: 'Making ', turn_id: 'T1', segment: 0, offset: 0 }, { seq: 2 })
  await ev('message.delta', { text: 'Making the project', turn_id: 'T1', segment: 0, offset: 0 }, { seq: 3 })
  await ev('message.delta', { text: 'ignored', turn_id: 'T1', segment: 0, offset: 0 }, { seq: 3 })
  await ev('tool.start', { tool_id: 'c0', name: 'tool_describe', args: {} }, { seq: 4 })
  await ev('tool.start', { tool_id: 'c1', name: 'chromatic_project_create', args: { name: 'Lamplight', content: 'x'.repeat(5000) } }, { seq: 5 })
  await act(async () => { emit({ type: 'message.delta', session_id: 'rt-other', payload: { text: 'not ours' } }) })
  check('the stream lands in this conversation only, re-sent chunks are dropped, and steps read in plain words', () => {
    assert.equal(build14.node.querySelector('.cs-b-agent').textContent, 'Making the project')
    assert.ok(!build14.node.textContent.includes('not ours')); assert.ok(!build14.node.textContent.includes('ignored'))
    const rows = build14.node.querySelectorAll('.cs-b-tool')
    assert.equal(rows.length, 1, 'plumbing such as tool_describe is not a step')
    assert.equal(rows[0].dataset.state, 'running'); assert.match(rows[0].textContent, /Creating the project/)
    assert.equal(build14.node.querySelector('.cs-b-wk').dataset.open, 'true', 'the steps are open while it works')
    assert.match(build14.node.querySelector('.cs-b-wk-head').textContent, /Working for/)
    assert.match(build14.node.querySelector('.cs-b-status').textContent, /HermRetro is creating the project/)
    assert.match(build14.node.querySelector('.cs-b-who').textContent, /HermRetroworking now/)
  })
  // Questions reach the app as server requests: while the turn runs the page reads the open ones.
  let openRequests = [{ id: 'srq-1', method: 'clarify', params: { session_id: 'rt-new-1', questions: [
    { qid: 'q0', question: 'What is the core loop?', choices: ['Explore (Recommended)', 'Sneak'] }, { qid: 'q1', question: 'How long?', choices: ['Short', 'Long'] }] } }]
  const plainResume = scenario.byMethod['session.resume']
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? { session_id: params.session_id, running: true, open_requests: openRequests } : plainResume(params))
  scenario.locks = []
  scenario.byMethod['clarify.lock'] = params => { scenario.locks.push(params); if (scenario.locks.length === 2) openRequests = []; return { status: 'ok', remaining: [] } }
  await settle(1500)
  menu14 = await gamesMenu(build14)
  check('a question shows as one card, outside the steps, with numbered choices and the suggested one marked', () => {
    assert.equal(build14.node.querySelectorAll('.cs-b-card.ask').length, 1)
    const card = build14.node.querySelector('.cs-b-card.ask')
    assert.match(card.textContent, /What is the core loop\?.*Explore.*Suggested.*Sneak.*How long\?/)
    assert.ok(!card.textContent.includes('(Recommended)'))
    assert.ok(button('Send answer').disabled, 'every question needs an answer first')
    assert.match(build14.node.querySelector('.cs-b-status').textContent, /waiting for your answer/)
    assert.match(menu14.textContent, /Needs your answer/)
  })
  await key('keydown', '2')
  await typeInto(build14.node.querySelectorAll('.cs-b-own')[1], 'about ten minutes')
  await click('Send answer', build14.node)
  await settle()
  check('a number key picks a choice, Send answer locks each question, and the answers become a step', () => {
    assert.deepEqual(scenario.locks, [{ request_id: 'srq-1', question_id: 'q0', answer: 'Sneak' }, { request_id: 'srq-1', question_id: 'q1', answer: 'about ten minutes' }])
    assert.equal(build14.node.querySelectorAll('.cs-b-card.ask').length, 0)
    assert.match(build14.node.querySelector('.cs-b-wk').textContent, /You answeredSneakabout ten minutes/)
  })
  scenario.byMethod['session.resume'] = plainResume
  await ev('tool.complete', { tool_id: 'c1', name: 'chromatic_project_create', result: { ok: false, error: 'folder exists' } }, { seq: 6 })
  await ev('message.complete', { text: 'Making the project', status: 'complete' }, { seq: 7 })
  check('a failed step says why; the turn end folds the steps into "Worked for", ends the status, and keeps one reply', () => {
    const row = build14.node.querySelector('.cs-b-tool')
    assert.equal(row.dataset.state, 'failed'); assert.match(row.textContent, /Creating the project failed.*folder exists/)
    assert.equal(build14.node.querySelector('.cs-b-wk').dataset.open, 'false')
    assert.match(build14.node.querySelector('.cs-b-wk-head').textContent, /Worked for \d+s/)
    assert.equal(build14.node.querySelectorAll('.cs-b-agent').length, 1); assert.ok(!button('Stop'))
    assert.ok(!build14.node.querySelector('.cs-b-status'))
  })
  await click('Worked for', build14.node)
  check('the folded steps open again on a click', () => { assert.equal(build14.node.querySelector('.cs-b-wk').dataset.open, 'true') })
  // The gateway restarted: a new replay epoch counts from 1 again and must not be dropped as seen.
  await ev('message.start', { turn_id: 'T2' }, { seq: 1, replay_epoch: 'E2' })
  await ev('message.delta', { text: 'After restart', turn_id: 'T2', segment: 0, offset: 0 }, { seq: 2, replay_epoch: 'E2' })
  check('after a gateway restart (new replay epoch) the stream is shown again, as a new reply', () => {
    assert.match([...build14.node.querySelectorAll('.cs-b-agent')].at(-1).textContent, /After restart/)
    assert.equal(build14.node.querySelectorAll('.cs-b-her').length, 2)
  })
  // A question announced as an event and then seen again by the poll is one card; settling it answers it.
  await ev('approval.request', { request_id: 'ap-1', command: 'flash', description: 'Flash the cart' }, { seq: 3, replay_epoch: 'E2' })
  scenario.byMethod['session.resume'] = params => (params.omit_messages
    ? { session_id: params.session_id, running: true, open_requests: [{ id: 'ap-1', method: 'approval', params: { command: 'flash' } }] }
    : plainResume(params))
  await settle(1500)
  check('an approval seen both as an event and by the poll is one card', () => {
    assert.equal(build14.node.querySelectorAll('.cs-b-card.warn').length, 1)
    assert.match(build14.node.querySelector('.cs-b-card.warn').textContent, /needs your OK/)
  })
  await ev('approval.settled', { request_id: 'ap-1' }, { seq: 4, replay_epoch: 'E2' })
  scenario.byMethod['session.resume'] = plainResume
  await ev('error', { message: 'provider went away' }, { seq: 5, replay_epoch: 'E2' })
  check('an error frame ends the turn and says why in a card', () => {
    assert.match(build14.node.querySelector('.cs-b-card.bad').textContent, /Something went wrong.*provider went away/); assert.ok(!button('Stop'))
    assert.equal(build14.node.querySelectorAll('.cs-b-card.warn').length, 0)
  })
  // The game the conversation made appears in the library: the conversation becomes that game's.
  scenario.games = answered({ games: [...lib14], pending: [{ storedId: 'st-new-1', name: 'Lamplight' }], device: { hardwareEnabled: false, skipped: true } })
  await build14.rerender(); await settle()
  menu14 = await gamesMenu(build14)
  check('until its project exists the New Game conversation is listed from the backend, once', () => {
    assert.equal((menu14.textContent.match(/Lamplight/g) ?? []).length, 1)
  })
  lib14.push({ id: 'aaa000aaa000', title: 'Lamplight', projectRoot: '/home/u/games/Lamplight', kind: 'gbstudio', state: 'unbuilt',
    rom: null, webExport: false, thumb: null, chat: null, session: { storedId: 'st-new-1' }, error: null })
  scenario.games = answered({ games: [...lib14], pending: [], device: { hardwareEnabled: false, skipped: true } })
  await build14.rerender(); await settle()
  menu14 = await gamesMenu(build14)
  check('once the backend binds the game it made, the conversation is that game\'s and stays selected', () => {
    assert.equal(menu14.textContent.match(/Lamplight/g).length, 1)
    assert.ok(!/Setting up/.test(menu14.textContent))
    assert.equal(build14.node.querySelector('.cs-b-head h2').textContent, 'Lamplight')
    assert.equal(build14.node.querySelector('.cs-b-agent').textContent, 'Making the project')
  })
  const shelfLamp = await libraryMenu(build14)
  check('a game with its own conversation is not in the Edit a game list, and the list says it is open above', () => {
    assert.ok(!/Lamplight/.test([...shelfLamp.querySelectorAll('.cs-b-sw-list')].map(node => node.textContent).join('')))
    assert.match(shelfLamp.querySelector('.cs-b-sw-foot').textContent, /Lamplight is already open above\./)
  })
  await pickFromLibrary(build14, 'Frog Post')
  menu14 = await gamesMenu(build14)
  check('picking a game from Edit a game opens it, and it joins Editing now', () => {
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'Frog Post')
    assert.match(menu14.textContent, /Editing now.*Frog PostNew editing chat.*Lamplight/)
    assert.ok(!/Edit a game/.test(menu14.textContent), 'nothing left in the library: no Edit a game')
  })
  await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: '2', ctrlKey: true, bubbles: true, cancelable: true })) })
  await settle()
  menu14 = await gamesMenu(build14)
  check('Ctrl+2 switches to the second game in the menu; a game left without a conversation drops out of it', () => {
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'Lamplight')
    assert.ok(!/Frog Post/.test(menu14.textContent))
  })
  await pickFromLibrary(build14, 'Frog Post')
  check('a game with no conversation opens a blank one; nothing is created until the first message', () => {
    assert.equal(created, 1); assert.match(build14.node.textContent, /Tell HermRetro what to make or change in Frog Post/)
  })
  await typeInto(build14.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add rain')
  await click('Send', build14.node.querySelector('.cs-b-comp'))
  await settle()
  check('the first message creates the conversation, binds it to the game in the backend, and sends what the user typed', () => {
    assert.equal(created, 2)
    assert.deepEqual(buildCalls.at(-1), { action: 'bind', game: 'fff666fff666', stored: 'st-new-2', replace: false })
    assert.equal(submits.at(-1).text, 'add rain')
    assert.equal([...build14.node.querySelectorAll('.cs-b-user')].at(-1).textContent, 'add rain')
  })
  // Stop editing (right-click a game being edited): the game is unbound and its old conversation un-hidden.
  scenario.byMethod['session.set_hidden'] = params => { scenario.unhidden = params; return { hidden: false } }
  const frogRow = () => [...build14.node.querySelectorAll('.cs-b-sw-list button')].find(node => node.textContent.includes('Frog Post'))
  await fire(build14.node.querySelector('.cs-b-sw'), 'click')
  await fire(frogRow(), 'contextmenu', { clientX: 60, clientY: 120 })
  check('right-clicking a game being edited offers Open in full chat and Stop editing, and nothing else', () => {
    const items = [...build14.node.querySelectorAll('.cs-b-ctx button')].map(node => node.textContent)
    assert.deepEqual(items, ['Open in full chat', 'Stop editing'])
    assert.ok(build14.node.querySelector('.cs-b-ctx button.danger').disabled, 'not while the agent works')
  })
  await key('keydown', 'Escape'); await key('keydown', 'Escape')
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-new-2', payload: { text: 'Raining now.' } }) })
  await settle()
  await fire(build14.node.querySelector('.cs-b-sw'), 'click')
  await fire(frogRow(), 'contextmenu', { clientX: 60, clientY: 120 })
  await fire(build14.node.querySelector('.cs-b-ctx button.danger'), 'click')
  await settle()
  menu14 = await gamesMenu(build14)
  const shelfAfter = await libraryMenu(build14)
  check('Stop editing unbinds the game, shows its old conversation in the Hermes sidebar, and puts it back under Edit a game', () => {
    assert.deepEqual(buildCalls.at(-1), { action: 'unbind', game: 'fff666fff666', stored: 'st-new-2' })
    assert.deepEqual(scenario.unhidden, { session_id: 'st-new-2', hidden: false })
    assert.equal(build14.node.querySelector('.cs-b-sw h2').textContent, 'New game')
    assert.ok(!/Frog Post/.test(menu14.textContent)); assert.match(shelfAfter.textContent, /Frog Post/)
  })
  await build14.close()
  // An older backend without the build RPC: the binding lasts this visit, and the message names the project.
  buildAnswer = () => { throw Object.assign(new Error('unknown method'), { code: -32601 }) }
  lib14[0] = { ...lib14[0], session: null }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  scenario.storage.buildSelected = 'fff666fff666'
  const build14o = await mount(page)
  await settle()
  await typeInto(build14o.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add snow')
  await click('Send', build14o.node.querySelector('.cs-b-comp'))
  await settle()
  check('on an older backend the first message names the project instead, and still shows what the user typed', () => {
    assert.match(submits.at(-1).text, /\/home\/u\/games\/FrogPost/); assert.match(submits.at(-1).text, /add snow$/)
    assert.equal([...build14o.node.querySelectorAll('.cs-b-user')].at(-1).textContent, 'add snow')
  })
  await build14o.close()
  buildAnswer = () => ({ ok: true })
  // A bound game from an earlier visit resumes its stored conversation: history with timings, Hermes's
  // deferred tool_call unwrapped, and the images its steps made.
  lib14[0] = { ...lib14[0], session: { storedId: 'st-old' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  scenario.storage.buildSelected = 'fff666fff666'
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? plainResume(params) : { session_id: `rt-of-${params.session_id}`, running: false, messages: [
    { role: 'user', content: 'make the frog jump', timestamp: 1000 },
    { role: 'assistant', content: [{ type: 'text', text: 'On it.' }], timestamp: 1001, tool_calls: [
      { id: 'v1', function: { name: 'vision_analyze', arguments: JSON.stringify({ image_url: '/home/u/games/FrogPost/docs/art/frog.png', question: 'ok?' }) } },
      { id: 'w1', function: { name: 'tool_call', arguments: JSON.stringify({ calls: [{ name: 'chromatic_asset_import', arguments: { assetPath: 'assets/sprites/frog.png', kind: 'sprite' } }, { name: 'chromatic_rom_build', arguments: {} }] }) } }] },
    { role: 'tool', tool_call_id: 'v1', name: 'vision_analyze', timestamp: 1004 },
    { role: 'tool', tool_call_id: 'w1', name: 'tool_call', args: { calls: [{ name: 'chromatic_asset_import', arguments: { assetPath: 'assets/sprites/frog.png' } }] }, timestamp: 1020 },
    { role: 'assistant', content: 'Added a jump.', timestamp: 1167 },
    { role: 'user', text: 'secret', display_kind: 'hidden' }] })
  scenario.assetCalls = []
  scenario.byMethod['plugin.hermretro.asset'] = params => {
    scenario.assetCalls.push(params.path)
    return { ok: true, path: params.path, name: params.path.split('/').pop(), relative: 'assets/sprites/frog.png', kind: 'sprite', width: 32, height: 16, bytes: 90,
      dataUrl: 'data:image/png;base64,iVBORw0KGgo=', sprite: { name: 'Frog', frameWidth: 16, frameHeight: 16, animSpeed: 15 } }
  }
  // What the viewer shows beside a sprite: its animations (from the sidecar) and kept versions.
  scenario.byMethod['plugin.hermretro.asset_info'] = params => ({ ok: true, path: params.path, relative: 'assets/sprites/frog.png', kind: 'sprite',
    versions: [{ id: '1', at: 1000, file: params.path, current: true }],
    sprite: { name: 'Frog', id: 'frog', type: 'fixed_movement', flipLeft: false, canvasWidth: 16, canvasHeight: 16, animSpeed: 15, numTiles: 4,
      animations: [{ slot: 0, name: 'Idle', frames: [[{ x: 0, y: 0, sliceX: 0, sliceY: 0 }, { x: 8, y: 0, sliceX: 8, sliceY: 0 }]] }] },
    usedIn: [], scenes: [] })
  const build14b = await mount(page)
  await settle(100)
  check('a bound game resumes its stored session: history, plain-word steps from inside tool_call, and how long it took', () => {
    assert.match(build14b.node.textContent, /make the frog jump/); assert.match(build14b.node.textContent, /Added a jump\./)
    assert.ok(!build14b.node.textContent.includes('secret'))
    const steps = [...build14b.node.querySelectorAll('.cs-b-tool')].map(node => node.textContent)
    assert.equal(steps.length, 3, 'a call and its result row are one step; tool_call is its calls')
    assert.match(steps[0], /Looked at frog\.png/); assert.match(steps[1], /Added art to the game/); assert.match(steps[2], /Built the game/)
    assert.match(build14b.node.querySelector('.cs-b-wk-head').textContent, /Worked for 2m 47s· drew the art, built it/)
    assert.equal(build14b.node.querySelector('.cs-b-agent').textContent, 'On it.', 'the words before the first step come first')
  })
  check('the folded line shows what the turn made as a small stack and an \u201cN assets\u201d link (not pictures it only looked at)', () => {
    assert.deepEqual([...new Set(scenario.assetCalls)].sort(), ['/home/u/games/FrogPost/assets/sprites/frog.png', '/home/u/games/FrogPost/docs/art/frog.png'], 'each picture is fetched once')
    const link = build14b.node.querySelector('.cs-b-wk-row .cs-b-wk-assets')
    assert.ok(link); assert.match(link.textContent, /^1 asset$/)
    assert.equal(link.querySelectorAll('.cs-b-stack-i').length, 1)
    assert.ok(!/new images/.test(build14b.node.querySelector('.cs-b-wk-head').textContent))
  })
  check('a turn that built the game ends in build card #1, titled by the request, and says it is not playable yet', () => {
    const card = build14b.node.querySelector('.cs-b-bc')
    assert.ok(card); assert.equal(card.dataset.build, '1')
    assert.match(card.querySelector('.cs-b-bc-head').textContent, /#1make the frog jump/)
    assert.match(card.textContent, /The playable copy is not ready yet/)
    assert.ok(!build14b.node.querySelector('.cs-ip')); assert.ok(!build14b.node.querySelector('.cs-b-pc'), 'no separate play card under a build card')
  })
  check('the header shows the build pill and a Builds menu; the Assets panel and Full chat button are gone', () => {
    assert.match(build14b.node.querySelector('.cs-b-pill').textContent, /Build #1 · up to date|Edited since build #1|Build #1/)
    assert.ok(button('Builds')); assert.ok(!build14b.node.querySelector('button[aria-label^="Assets"]')); assert.ok(!build14b.node.querySelector('button[aria-label="Open in full chat"]'))
  })
  await act(async () => { build14b.node.querySelector('.cs-b-wk-assets').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle(50)
  check('the assets link opens the viewer on the picture it made, without folding the steps open', () => {
    const viewer = build14b.node.querySelector('.cs-v')
    assert.ok(viewer); assert.match(viewer.textContent, /Frog/); assert.match(viewer.textContent, /32×16/)
    assert.equal(build14b.node.querySelector('.cs-b-wk').dataset.open, 'false')
    assert.ok(!build14b.node.querySelector('.cs-b-ap'), 'no Assets panel any more')
  })
  check('the viewer is image-first: a sprite has Animation, Sheet, and Details or Change beside it', () => {
    const viewer = build14b.node.querySelector('.cs-v')
    assert.deepEqual([...viewer.querySelectorAll('.cs-v-seg button')].map(node => node.textContent), ['Animation', 'Sheet'])
    assert.deepEqual([...viewer.querySelectorAll('.cs-v-tabs button')].map(node => node.textContent), ['Details', 'Change'])
    assert.match(viewer.querySelector('.cs-v-quote')?.textContent ?? '', /make the frog jump/, 'it quotes the message that asked for it')
  })
  await click('Show in folder', build14b.node.querySelector('.cs-v'))
  check('Show in folder reveals the file', () => { assert.match(scenario.revealed, /frog\.png$/) })
  await key('keydown', 'Escape')
  check('Escape closes the viewer', () => { assert.ok(!build14b.node.querySelector('.cs-v')) })
  await act(async () => { build14b.node.querySelector('.cs-b-wk-assets').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle(30)
  await click('Change', build14b.node.querySelector('.cs-v-tabs'))
  await typeInto(build14b.node.querySelector('.cs-v-input'), 'make it green')
  await click('Send to HermRetro', build14b.node.querySelector('.cs-v'))
  await settle()
  check('Change sends the request from the viewer, naming the image, and the viewer stays open', () => {
    assert.match(submits.at(-1).text, /^About \/home\/u\/games\/FrogPost\/[^\n]*frog\.png:\nmake it green\n\n- When it is done, build the game and show it to me/)
    const bubble = [...build14b.node.querySelectorAll('.cs-b-user')].at(-1)
    assert.match(bubble.textContent, /frog\.png/); assert.match(bubble.textContent, /make it green$/)
    assert.ok(build14b.node.querySelector('.cs-v'), 'the viewer stays open while it works')
    assert.match(build14b.node.querySelector('.cs-v-pane').textContent, /You asked/)
  })
  await key('keydown', 'Escape')
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-old', payload: { text: 'Greener now.' } }) })
  await settle()
  await build14b.close()
  // A long turn: Simple shows five plain groups, Technical every step; a reply's pictures are small cards.
  const resume14b = scenario.byMethod['session.resume']
  const lib14Session = lib14[0].session
  lib14[0] = { ...lib14[0], session: { storedId: 'st-long' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const callOf = (id, name, args = {}) => ({ id, function: { name, arguments: JSON.stringify(args) } })
  const report14 = { title: 'Robin in the sky', summary: 'A little red robin in a big daytime sky. Fly anywhere with the D-pad.',
    changes: [{ kind: 'added', text: 'Robin sprite, 3 views', asset: 'assets/sprites/bird.png' }, { kind: 'changed', text: 'Camera follows the player' }],
    tested: ['Robin faces where it flies', 'Camera follows'], untested: ['Sound'], notes: ['It only flaps while moving'], suggestions: ['Flap while idle', 'Fly faster'] }
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? plainResume(params) : { session_id: `rt-of-${params.session_id}`, running: false, messages: [
    { role: 'user', content: 'make a bird game', timestamp: 2000 },
    { role: 'assistant', content: 'Planning.', timestamp: 2001, tool_calls: [
      callOf('p1', 'skill_view', { name: 'hermretro:authoring' }), callOf('p2', 'skill_view', { name: 'hermretro:pixel-art' }), callOf('p3', 'chromatic_project_inspect'), callOf('p4', 'chromatic_project_inventory'),
      callOf('a1', 'chromatic_asset_import', { assetPath: 'assets/sprites/bird.png' }), callOf('a2', 'chromatic_sprite_edit'), callOf('a3', 'terminal', { command: 'python draw.py' }),
      callOf('w1', 'chromatic_scene_update'), callOf('w2', 'chromatic_actor_update'),
      callOf('b1', 'chromatic_rom_build'), callOf('b2', 'chromatic_emulator_step'), callOf('r1', 'chromatic_build_report', report14)] },
    ...['p1', 'p2', 'p3', 'p4', 'a1', 'a2', 'a3', 'w1', 'w2', 'b1', 'b2', 'r1'].map((id, index) => ({ role: 'tool', tool_call_id: id, timestamp: 2002 + index })),
    { role: 'assistant', content: 'Here they are:\n\nMEDIA:/home/u/games/FrogPost/assets/sprites/bird.png\nMEDIA:/home/u/games/FrogPost/cover.png\n\nWant it to flap all the time?', timestamp: 2100 },
    { role: 'user', content: 'add music', timestamp: 3000 },
    { role: 'assistant', content: '', timestamp: 3001, tool_calls: [callOf('m1', 'chromatic_rom_build')] },
    { role: 'tool', tool_call_id: 'm1', content: JSON.stringify({ ok: false, error: 'The song is 2.4 KB too big for the cartridge.' }), timestamp: 3050 },
    { role: 'assistant', content: 'The music did not fit.', timestamp: 3060 }] })
  const build14ph = await mount(page)
  await settle(100)
  check('the report becomes build card #1: title, summary, what changed, and a footer with what was tested', () => {
    const card = build14ph.node.querySelector('.cs-b-bc[data-build="1"]')
    assert.ok(card); assert.match(card.querySelector('.cs-b-bc-title').textContent, /Robin in the sky/)
    assert.match(card.querySelector('.cs-b-bc-sum').textContent, /little red robin/)
    assert.deepEqual([...card.querySelectorAll('.cs-b-bc-changes li')].map(node => node.textContent), ['+Robin sprite, 3 views', '~Camera follows the player'])
    assert.match(card.querySelector('.cs-b-bc-foot').textContent, /✓ 2 play-tested.*○ 1 not tested.*⚠ 1 note/)
    assert.ok(!/chromatic_build_report|Using build report/.test(build14ph.node.textContent), 'the report is not a step')
  })
  check('the reply after a report is a line after the card, and its pictures are small cards in one row', () => {
    const turn = build14ph.node.querySelectorAll('.cs-b-turn')[0]
    const order = [...turn.querySelector('.cs-b-her').children].map(node => node.className.split(' ')[0])
    assert.ok(order.indexOf('cs-b-bc') < order.lastIndexOf('cs-b-agent'), 'card first, then the reply')
    const cards = turn.querySelectorAll('.cs-b-rimgs .cs-b-rchip')
    assert.equal(cards.length, 2)
  })
  await click('Details', build14ph.node.querySelector('.cs-b-bc[data-build="1"]'))
  check('Details lists what was play-tested, not tested and the notes', () => {
    const details = build14ph.node.querySelector('.cs-b-bc-details').textContent
    assert.match(details, /Play-tested.*Robin faces where it flies.*Not tested.*Sound.*You might notice.*only flaps while moving/)
  })
  check('a failed compile is build #2 that didn\u2019t finish, with what went wrong, and the pill says so', () => {
    const card = build14ph.node.querySelector('.cs-b-bc[data-build="2"]')
    assert.ok(card); assert.ok(card.classList.contains('bad'))
    assert.match(card.textContent, /#2The build didn’t finish/); assert.match(card.textContent, /2\.4 KB too big/)
    assert.ok(button('Ask HermRetro to fix it'))
    assert.match(build14ph.node.querySelector('.cs-b-pill').textContent, /Build #2 didn’t finish/)
  })
  check('next-step chips show only under the newest reply', () => {
    assert.equal(build14ph.node.querySelectorAll('.cs-b-next-steps').length, 0, 'the last turn reported nothing to suggest')
  })
  await click('Worked for', build14ph.node.querySelector('.cs-b-turn'))
  check('Simple shows the turn as five plain groups, folded, each with its step count', () => {
    const heads = [...build14ph.node.querySelectorAll('.cs-b-ph-head')].map(node => node.textContent)
    assert.deepEqual(heads.map(text => text.replace(/\d+ steps?.*/, '').trim()), ['Planned it', 'Drew the art', 'Set up the level', 'Built it', 'Play-tested it'])
    assert.match(heads[1], /3 steps/, 'a command joins the group it was helping')
    assert.equal(build14ph.node.querySelectorAll('.cs-b-ph-body').length, 0, 'a finished turn starts with every group folded')
  })
  await click('Planned it', build14ph.node)
  check('a group of only glances says so instead of listing them', () => {
    const body = build14ph.node.querySelector('.cs-b-ph-body')
    assert.equal(body.querySelectorAll('.cs-b-tool').length, 0); assert.match(body.textContent, /Technical shows them/)
  })
  await click('Technical', build14ph.node.querySelector('.cs-b-wk-mode'))
  check('Technical lists every step with its detail, for every turn', () => {
    assert.equal(build14ph.node.querySelector('.cs-b-turn .cs-b-wk-inner').querySelectorAll('.cs-b-tool').length, 11)
    assert.match(build14ph.node.querySelector('.cs-b-turn .cs-b-wk-inner').textContent, /python draw\.py/)
  })
  await click('Simple', build14ph.node.querySelector('.cs-b-wk-mode'))
  await click('Builds', build14ph.node.querySelector('.cs-b-head'))
  await settle(30)
  check('Builds lists every build newest first; an earlier build offers Restore only once its files are found', () => {
    const rows = [...build14ph.node.querySelectorAll('.cs-b-brow')].map(node => node.textContent)
    assert.equal(rows.length, 2); assert.match(rows[0], /#2add music.*didn’t finish/); assert.match(rows[1], /#1Robin in the sky/)
  })
  await key('keydown', 'Escape')
  await build14ph.close()
  // The report's suggestions and the @ picker: chips fill the box; @ lists the game's pictures.
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? plainResume(params) : { session_id: `rt-of-${params.session_id}`, running: false, messages: [
    { role: 'user', content: 'make a bird game', timestamp: 2000 },
    { role: 'assistant', content: '', timestamp: 2001, tool_calls: [callOf('b1', 'chromatic_rom_build'), callOf('r1', 'chromatic_build_report', report14)] },
    { role: 'tool', tool_call_id: 'b1', content: JSON.stringify({ ok: true }), timestamp: 2010 },
    { role: 'tool', tool_call_id: 'r1', content: JSON.stringify({ ok: true, report: report14 }), timestamp: 2011 },
    { role: 'assistant', content: 'Want it to flap all the time?', timestamp: 2012 }] })
  lib14[0] = { ...lib14[0], session: { storedId: 'st-long2' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const gamePictures = []
  scenario.byMethod['plugin.hermretro.assets'] = params => {
    gamePictures.push(params.game)
    return { ok: true, assets: [
      { path: '/home/u/games/FrogPost/cover.png', name: 'Cover', file: 'cover.png', kind: 'cover', modifiedAt: 5 },
      { path: '/home/u/games/FrogPost/assets/sprites/bird.png', name: 'Robin', file: 'bird.png', kind: 'sprite', modifiedAt: 5 },
      { path: '/home/u/games/FrogPost/assets/backgrounds/sky.png', name: 'Open Sky', file: 'sky.png', kind: 'background', modifiedAt: 5 }] }
  }
  const build14pa = await mount(page)
  await settle(100)
  check('the newest reply ends with its suggestions as chips', () => {
    assert.deepEqual([...build14pa.node.querySelectorAll('.cs-b-next-steps button')].map(node => node.textContent), ['Flap while idle', 'Fly faster'])
  })
  await click('Fly faster', build14pa.node.querySelector('.cs-b-next-steps'))
  await settle()
  check('a suggestion fills the message box and is not sent', () => {
    assert.equal(build14pa.node.querySelector('textarea[aria-label="Message Hermes"]').value, 'Fly faster')
  })
  const box14 = build14pa.node.querySelector('textarea[aria-label="Message Hermes"]')
  await typeInto(box14, 'make @')
  await settle(50)
  check('typing @ lists the game\u2019s pictures', () => {
    assert.deepEqual(gamePictures.slice(-1), ['fff666fff666'])
    assert.deepEqual([...build14pa.node.querySelectorAll('.cs-b-mention-row b')].map(node => node.textContent), ['Cover', 'Robin', 'Open Sky'])
  })
  await typeInto(box14, 'make @rob')
  await settle(20)
  check('what follows @ filters the list', () => {
    assert.deepEqual([...build14pa.node.querySelectorAll('.cs-b-mention-row b')].map(node => node.textContent), ['Robin'])
  })
  await key('keydown', 'Enter', box14)
  await settle()
  check('Enter picks it: the @word leaves the text and the picture is attached as a mention', () => {
    assert.ok(!build14pa.node.querySelector('.cs-b-mention'))
    assert.equal(box14.value, 'make ')
    assert.match(build14pa.node.querySelector('.cs-b-comp .cs-b-chip.mention').textContent, /@Robin/)
  })
  await typeInto(box14, 'make it chubbier')
  await click('Send', build14pa.node.querySelector('.cs-b-comp'))
  await settle()
  check('the message names the file for the agent and shows the mention in the bubble', () => {
    assert.match(submits.at(-1).text, /^About \/home\/u\/games\/FrogPost\/assets\/sprites\/bird\.png:\nmake it chubbier$/)
    assert.match([...build14pa.node.querySelectorAll('.cs-b-user')].at(-1).textContent, /@Robin/)
  })
  delete scenario.byMethod['plugin.hermretro.assets']
  await build14pa.close()
  scenario.byMethod['session.resume'] = resume14b
  lib14[0] = { ...lib14[0], session: lib14Session }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  // The game plays inside the conversation, only while the agent is not working.
  lib14[0] = { ...lib14[0], web: { sha256: 'w1' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const playerBefore = scenario.player
  scenario.player = answered({ url: 'http://127.0.0.1:4567/tok/fff666fff666/index.html', romSha256: 'w1', title: 'Frog Post' })
  const tabsBefore = scenario.workspaces.length
  const build14p = await mount(page)
  await settle(100)
  const inlineFrame = () => build14p.node.querySelector('.cs-ip iframe')
  const cardPlay = () => [...build14p.node.querySelectorAll('.cs-b-bc-head button')].find(node => node.textContent.includes('Play'))
  check('the build card of the turn that built the game offers Play; nothing plays until asked', () => {
    assert.ok(cardPlay()); assert.ok(!inlineFrame()); assert.ok(!build14p.node.querySelector('.cs-b-pc'))
  })
  await act(async () => { cardPlay().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('Play opens the real player right in the conversation', () => {
    assert.match(inlineFrame()?.getAttribute('src') ?? '', /tok\/fff666fff666\/index\.html/)
    assert.ok(build14p.node.querySelector('.cs-b-bc .cs-ip'), 'it plays inside the build card'); assert.ok(!cardPlay())
  })
  await typeInto(build14p.node.querySelector('textarea[aria-label="Message Hermes"]'), 'make it rain')
  await click('Send', build14p.node.querySelector('.cs-b-comp'))
  await settle()
  check('while the agent works the game rests as a card that says when it is back', () => {
    assert.ok(!inlineFrame())
    assert.match(build14p.node.querySelector('.cs-b-bc').textContent, /Playable again when HermRetro finishes/, [...build14p.node.querySelectorAll('.cs-b-turn')].map(node => `[${node.dataset.turn}] ${node.textContent.slice(0, 120)}`).join(' || '))
  })
  const runtime = 'rt-of-st-old'
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { status: 'queued' } }
  await typeInto(build14p.node.querySelector('textarea[aria-label="Message Hermes"]'), 'and make it snow after')
  await click('Send', build14p.node.querySelector('.cs-b-comp'))
  await settle()
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }
  check('a message Hermes queues while it works waits under the conversation, marked queued', () => {
    const queued = build14p.node.querySelector('.cs-b-user.queued')
    assert.match(queued?.textContent ?? '', /Queued · HermRetro reads this when it finishes.*and make it snow after/)
    assert.equal([...build14p.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'make it rain')
  })
  await act(async () => { emit({ type: 'tool.start', session_id: runtime, payload: { tool_id: 'p0', name: 'chromatic_rom_build', args: {} } }) })
  await act(async () => { emit({ type: 'tool.complete', session_id: runtime, payload: { tool_id: 'p0', name: 'chromatic_rom_build', args: {}, result: { result: 'Completed.' } } }) })
  await act(async () => { emit({ type: 'tool.complete', session_id: runtime, payload: { tool_id: 'p1', name: 'chromatic_present_game', args: {},
    result: { ok: true, studio: { gameId: 'fff666fff666', title: 'Frog Post', note: 'Try the rain', presentedAt: 99 } } } }) })
  await settle()
  check('presenting from a Build conversation opens no tab beside the chat, and the game waits for the turn to end', () => {
    assert.equal(scenario.workspaces.length, tabsBefore); assert.ok(!inlineFrame())
    assert.ok(build14p.node.querySelector('.cs-b-turn[data-live] .cs-b-pc.busy'), 'the turn building it now holds the resting game')
    assert.match(build14p.node.querySelector('.cs-b-bc').textContent, /Earlier build/)
  })
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Done.' } }) })
  await settle()
  check('when the turn ends the newest build opens in the newest reply, with the agent\'s note; the older one says it is older', () => {
    assert.ok(inlineFrame()); assert.match(build14p.node.querySelector('.cs-ip').textContent, /Try the rain/)
    const turnsNow = [...build14p.node.querySelectorAll('.cs-b-turn')]
    assert.ok(turnsNow.at(-1).querySelector('.cs-ip'), turnsNow.map(node => node.textContent.slice(0, 60)).join(' | '))
    assert.match(turnsNow.at(-1).querySelector('.cs-b-bc-head').textContent, /#2/); assert.match(build14p.node.textContent, /Earlier build/)
  })
  await act(async () => { emit({ type: 'message.start', session_id: runtime, payload: { turn_id: 'Q' } }) })
  await settle()
  check('when its turn starts the queued message joins the conversation as the newest one', () => {
    assert.ok(!build14p.node.querySelector('.cs-b-user.queued'))
    assert.equal([...build14p.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'and make it snow after')
    assert.ok(!inlineFrame(), 'the game rests while the agent works again')
  })
  await act(async () => { emit({ type: 'message.complete', session_id: runtime, payload: { text: 'Snowing.' } }) })
  await settle()
  check('a game the user had open comes back when the agent is done', () => { assert.ok(inlineFrame()) })
  await act(async () => { build14p.node.querySelector('.cs-ip button[aria-label="Close the game"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  check('closing the game puts Play back on the card', () => { assert.ok(!inlineFrame()); assert.ok(cardPlay()) })
  await build14p.close()
  // The inline player itself: one bar, whole-number sizes, and the play-test panel from the build report.
  scenario.byMethod['session.resume'] = params => (params.omit_messages ? plainResume(params) : { session_id: `rt-of-${params.session_id}`, running: false, messages: [
    { role: 'user', content: 'make a bird game', timestamp: 2000 },
    { role: 'assistant', content: '', timestamp: 2001, tool_calls: [callOf('b1', 'chromatic_rom_build'), callOf('r1', 'chromatic_build_report', report14)] },
    { role: 'tool', tool_call_id: 'b1', content: JSON.stringify({ ok: true }), timestamp: 2010 },
    { role: 'tool', tool_call_id: 'r1', content: JSON.stringify({ ok: true, report: report14 }), timestamp: 2011 },
    { role: 'assistant', content: 'Try flying around.', timestamp: 2012 }] })
  lib14[0] = { ...lib14[0], session: { storedId: 'st-play' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const build14ip = await mount(page)
  await settle(100)
  const ipPlay = [...build14ip.node.querySelectorAll('.cs-b-bc-head button')].find(node => node.textContent.includes('Play'))
  check('the reported build offers Play', () => assert.ok(ipPlay))
  await act(async () => { ipPlay.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  const ip = () => build14ip.node.querySelector('.cs-ip')
  check('the inline player loads the bare screen in the Midnight finish, with the player\'s own controls hidden', () => {
    assert.match(ip().querySelector('iframe').getAttribute('src'), /index\.html\?view=screen&color=hermes-midnight$/)
    assert.equal(ip().querySelector('.cs-ip-screen').dataset.view, 'screen')
  })
  check('one bar: Fit and whole-number sizes, Chromatic, Play-test, Annotate and Close', () => {
    assert.deepEqual([...ip().querySelectorAll('.cs-ip-seg [role=radio]')].map(node => [node.textContent, node.getAttribute('aria-checked')]), [['Fit', 'true'], ['2×', 'false'], ['3×', 'false'], ['4×', 'false']])
    for (const label of ['Show the Chromatic around the game', 'Close the game']) assert.ok(ip().querySelector(`.cs-ip-bar button[aria-label="${label}"]`), label)
    assert.ok([...ip().querySelectorAll('.cs-ip-bar button')].some(node => /^Annotate/.test(node.getAttribute('aria-label') ?? '')))
    assert.ok([...ip().querySelectorAll('.cs-ip-bar button')].some(node => node.textContent === 'Play-test'))
  })
  const checkRows = () => [...ip().querySelectorAll('.cs-ip-check')].map(node => [node.querySelector('.cs-ip-check-text').textContent, node.dataset.state])
  check('the panel opens with the report\'s checks, what was not tested first', () => {
    assert.ok(ip().querySelector('.cs-ip-panel'))
    assert.deepEqual(checkRows(), [['Sound', 'untested'], ['Robin faces where it flies', 'todo'], ['Camera follows', 'todo']])
    assert.match(ip().querySelector('.cs-ip-panel').textContent, /Try this\s*0\/3/)
  })
  await act(async () => { ip().querySelectorAll('.cs-ip-check input')[1].click() })
  await settle()
  check('a tick is the user\'s, kept for this game and build', () => {
    assert.equal(checkRows()[1][1], 'done')
    assert.deepEqual(Object.keys(scenario.storage.playtest ?? {}), ['fff666fff666'])
    assert.match(JSON.stringify(scenario.storage.playtest), /robin faces where it flies/)
  })
  await act(async () => { ip().querySelector('.cs-ip-bar button[aria-label="Show the Chromatic around the game"]').click() })
  await settle()
  check('Chromatic shows the handheld around the game and is remembered for every game', () => {
    assert.equal(ip().querySelector('.cs-ip-screen').dataset.view, 'device')
    assert.equal(scenario.storage.inlinePlayer.view, 'device')
  })
  const sentKeys = []
  ip().querySelector('iframe').contentWindow.postMessage = message => { if (message.type === 'key') sentKeys.push(`${message.key}:${message.down ? 'down' : 'up'}`) }
  const keyOn = async (target, type, keyName) => act(async () => { target.dispatchEvent(new dom.window.KeyboardEvent(type, { key: keyName, bubbles: true, cancelable: true })) })
  await act(async () => { ip().querySelector('.cs-ip-stage').dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true })) })
  await keyOn(ip().querySelector('.cs-ip-stage'), 'keydown', 'ArrowUp')
  await keyOn(ip().querySelector('.cs-ip-bar button[aria-label="Close the game"]'), 'keydown', 'Enter')
  check('after a click in the player, game keys on the page reach the game, but Enter on a bar button presses the button', () => {
    assert.deepEqual(sentKeys, ['ArrowUp:down'])
  })
  await act(async () => { build14ip.node.querySelector('textarea[aria-label="Message Hermes"]').dispatchEvent(new dom.window.MouseEvent('pointerdown', { bubbles: true })) })
  await keyOn(build14ip.node.querySelector('textarea[aria-label="Message Hermes"]'), 'keydown', 'ArrowDown')
  check('clicking into the message box lets go of a held key, and typing there never reaches the game', () => {
    assert.deepEqual(sentKeys, ['ArrowUp:down', 'ArrowUp:up'])
  })
  await act(async () => { ip().querySelector('.cs-ip-bar button[aria-label="Close the game"]').click() })
  await build14ip.close()
  delete scenario.storage.inlinePlayer
  scenario.byMethod['session.resume'] = resume14b
  scenario.player = playerBefore
  lib14[0] = { ...lib14[0], web: null }
  // The conversation was removed from Hermes: say so, and replace it on the next message.
  lib14[0] = { ...lib14[0], session: { storedId: 'st-gone' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  scenario.byMethod['session.resume'] = params => { if (params.session_id === 'st-gone') throw Object.assign(new Error('session not found'), { code: 4007 }); return plainResume(params) }
  const build14c = await mount(page)
  await settle()
  check('a game whose conversation was removed says so and offers a new one', () => {
    assert.match(build14c.node.textContent, /conversation was removed from Hermes/)
    assert.ok(button('Start a new conversation'))
  })
  await click('Start a new conversation', build14c.node)
  await typeInto(build14c.node.querySelector('textarea[aria-label="Message Hermes"]'), 'start again')
  await click('Send', build14c.node.querySelector('.cs-b-comp'))
  await settle()
  check('the next message makes a new conversation and replaces the removed one', () => {
    assert.deepEqual(buildCalls.at(-1), { action: 'bind', game: 'fff666fff666', stored: `st-new-${created}`, replace: true })
    assert.equal(submits.at(-1).text, 'start again')
  })
  await build14c.close()
  // A turn Hermes lost when it restarted pauses the conversation: the page says so, and Continue drops it.
  lib14[0] = { ...lib14[0], session: { storedId: 'st-lost' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  let lostRows = [{ admission_id: 'adm-lost', status: 'unknown', text: 'make a bird', execution_generation: 1 }, { admission_id: 'adm-q', status: 'queued', text: 'continue' }]
  const resolved = []
  scenario.byMethod['session.resume'] = params => ({ ...plainResume(params), running: false, pending: lostRows })
  scenario.byMethod['prompt.resolve_unknown'] = params => { resolved.push(params); lostRows = lostRows.filter(row => row.admission_id !== params.admission_id); return { status: 'terminal', outcome: 'interrupted' } }
  const build14l = await mount(page)
  await settle()
  check('a conversation paused on a lost turn says so, with the message that waits behind it', () => {
    assert.match(build14l.node.querySelector('.cs-b-card.warn')?.textContent ?? '', /HermRetro stopped partway through.*Continue to send your waiting message/)
    assert.match(build14l.node.querySelector('.cs-b-user.queued')?.textContent ?? '', /Waiting · sent when you continue.*continue/)
  })
  const submitsBefore = submits.length
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { status: 'queued' } }
  await typeInto(build14l.node.querySelector('textarea[aria-label="Message Hermes"]'), 'and add clouds')
  await click('Send', build14l.node.querySelector('.cs-b-comp'))
  await settle()
  scenario.byMethod['prompt.submit'] = params => { submits.push(params); return { ok: true } }
  check('a message sent while paused waits too, and the page does not claim to be working', () => {
    assert.deepEqual([...build14l.node.querySelectorAll('.cs-b-user.queued')].map(node => node.lastChild.textContent), ['continue', 'and add clouds'])
    assert.ok(!build14l.node.querySelector('.cs-b-comp button[aria-label="Stop"]'))
  })
  await click('Continue', build14l.node.querySelector('.cs-b-card.warn'))
  await settle()
  check('Continue drops the lost turn (not run again) and sends nothing new when messages wait', () => {
    assert.deepEqual(resolved, [{ session_id: 'rt-of-st-lost', admission_id: 'adm-lost' }])
    assert.equal(submits.length, submitsBefore + 1)
    assert.ok(!build14l.node.querySelector('.cs-b-card.warn'))
  })
  await act(async () => { emit({ type: 'message.start', session_id: 'rt-of-st-lost', payload: { turn_id: 'L1' } }) })
  await settle()
  check('then the waiting messages run in order', () => {
    assert.equal([...build14l.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'continue')
    assert.deepEqual([...build14l.node.querySelectorAll('.cs-b-user.queued')].map(node => node.lastChild.textContent), ['and add clouds'])
  })
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-lost', payload: { text: 'Done.' } }) })
  // Lost again with nothing waiting: Continue asks HermRetro to pick up where it stopped.
  await act(async () => { emit({ type: 'message.start', session_id: 'rt-of-st-lost', payload: { turn_id: 'L2' } }) })
  await settle()
  check('while a turn runs the message box offers Stop', () => { assert.ok(build14l.node.querySelector('.cs-b-comp button[aria-label="Stop"]')) })
  lostRows = [{ admission_id: 'adm-lost-2', status: 'unknown', text: 'and add clouds', execution_generation: 3 }]
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-lost', payload: { pending: lostRows, running: false } }) })
  await settle()
  check('a turn lost while the page watched stops the working state and shows the card', () => {
    assert.match(build14l.node.querySelector('.cs-b-card.warn')?.textContent ?? '', /pick up where it stopped/)
    assert.ok(!build14l.node.querySelector('.cs-b-comp button[aria-label="Stop"]'))
  })
  await click('Continue', build14l.node.querySelector('.cs-b-card.warn'))
  await settle()
  check('with nothing waiting, Continue drops the lost turn and asks to continue', () => {
    assert.deepEqual(resolved.at(-1), { session_id: 'rt-of-st-lost', admission_id: 'adm-lost-2' })
    assert.match(submits.at(-1).text, /cut off when Hermes restarted\. Continue where you left off/)
    assert.equal([...build14l.node.querySelectorAll('.cs-b-turn .cs-b-user')].at(-1).textContent, 'Continue')
  })
  await build14l.close()
  scenario.byMethod['session.resume'] = plainResume
  // Model and effort: one button in the message box opens providers, models and effort together.
  scenario.models = answered({ model: 'claude-opus-5-5[1m]', provider: 'claude-sub', providers: [
    { slug: 'claude-sub', name: 'Claude Subscription', authenticated: true, total_models: 3, models: ['claude-opus-5-5[1m]', 'claude-sonnet-5-5[1m]', 'claude-haiku-4-5-20251001'],
      capabilities: { 'claude-opus-5-5[1m]': { reasoning: true }, 'claude-sonnet-5-5[1m]': { reasoning: true }, 'claude-haiku-4-5-20251001': { reasoning: true } } },
    { slug: 'openai-codex', name: 'ChatGPT or Codex Subscription', authenticated: true, total_models: 2, models: ['gpt-6.1-sol', 'gpt-6-sol-900k'],
      capabilities: { 'gpt-6.1-sol': { fast: true, reasoning: true }, 'gpt-6-sol-900k': { fast: true, reasoning: true } } },
    { slug: 'off', name: 'Signed Out Co', authenticated: false, models: ['x-1'] }] })
  scenario.sets = []
  scenario.byMethod['config.set'] = params => { scenario.sets.push(params); return { key: params.key, value: params.value } }
  lib14[0] = { ...lib14[0], session: { storedId: 'st-old' } }
  scenario.games = answered({ games: [...lib14], device: { hardwareEnabled: false, skipped: true } })
  const build14m = await mount(page)
  await settle()
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-old', payload: { model: 'claude-opus-5-5[1m]', provider: 'claude-sub', reasoning_effort: 'high' } }) })
  await settle()
  // Another game asks a question while this one is open: the title says so.
  await act(async () => { emit({ type: 'clarify.request', session_id: 'rt-new-1', payload: { request_id: 'other-q', question: 'Which lamp?' } }) })
  await settle()
  check('a question in another game shows as "1 needs you" beside the title', () => {
    assert.equal(build14m.node.querySelector('.cs-b-needs')?.textContent, '1 needs you')
    assert.match(build14m.node.querySelector('.cs-b-needs').getAttribute('title'), /Lamplight/)
  })
  await act(async () => { emit({ type: 'clarify.settled', session_id: 'rt-new-1', payload: { request_id: 'other-q' } }) })
  await settle()
  check('once it is answered the badge goes away', () => { assert.ok(!build14m.node.querySelector('.cs-b-needs')) })
  const chip = () => build14m.node.querySelector('.cs-b-mp-chip')
  const pop = () => build14m.node.querySelector('.cs-b-mp-pop')
  check('the message box shows the conversation\'s model and effort in plain words', () => {
    assert.equal(chip().textContent, 'CClaude Opus 5.5·High')
  })
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  check('the panel lists connected providers only, the current one\'s models, and the effort levels', () => {
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-prov .cs-b-mp-pname')].map(node => node.textContent), ['Claude Subscription', 'ChatGPT or Codex Subscription'])
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-row .cs-b-mp-label')].map(node => node.textContent), ['Claude Opus 5.5', 'Claude Sonnet 5.5', 'Claude Haiku 4.5'])
    assert.equal(pop().querySelector('.cs-b-mp-row[aria-selected="true"]').textContent, 'Claude Opus 5.51M')
    assert.deepEqual([...pop().querySelectorAll('.cs-b-seg button')].map(node => node.textContent), ['Off', 'Minimal', 'Low', 'Medium', 'High', 'X-high', 'Max'])
    assert.equal(pop().querySelector('.cs-b-seg button[aria-checked="true"]').textContent, 'High')
  })
  await typeInto(pop().querySelector('input[aria-label="Search models"]'), 'sol')
  check('search looks through every provider and names each match\'s provider', () => {
    assert.deepEqual([...pop().querySelectorAll('.cs-b-mp-row')].map(node => node.textContent), ['GPT-6.1 SolChatGPT or Codex Subscriptionfast mode', 'GPT-6 SolChatGPT or Codex Subscription900Kfast mode'])
  })
  await act(async () => { pop().querySelectorAll('.cs-b-mp-row')[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('picking a model switches this conversation only, and the button shows it', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-old', key: 'model', value: 'gpt-6.1-sol --provider openai-codex --session' })
    assert.ok(!pop())
    assert.match(chip().textContent, /GPT-6\.1 Sol·High/)
  })
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Medium', pop())
  await settle()
  check('an effort level is one click and applies to this conversation', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-old', key: 'reasoning', value: 'medium' })
    assert.match(chip().textContent, /GPT-6\.1 Sol·Medium/)
  })
  await key('keydown', 'Escape')
  check('Escape closes the panel', () => { assert.ok(!pop()) })
  // While HermRetro works, a pick waits for the turn to end.
  await typeInto(build14m.node.querySelector('textarea[aria-label="Message Hermes"]'), 'add a boss')
  await click('Send', build14m.node.querySelector('.cs-b-comp'))
  await settle()
  const before = scenario.sets.length
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Max', pop())
  await settle()
  await key('keydown', 'Escape')
  check('a pick made while HermRetro works is held, marked "next message", and not sent yet', () => {
    assert.equal(scenario.sets.length, before)
    assert.match(chip().textContent, /Max/); assert.match(chip().textContent, /next message/)
  })
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-old', payload: { text: 'Boss added.' } }) })
  await settle()
  check('when the turn ends the held pick is applied', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-old', key: 'reasoning', value: 'max' })
    assert.ok(!/next message/.test(chip().textContent))
  })
  await typeInto(build14m.node.querySelector('textarea[aria-label="Message Hermes"]'), 'now a second boss')
  await click('Send', build14m.node.querySelector('.cs-b-comp'))
  await act(async () => { emit({ type: 'message.complete', session_id: 'rt-of-st-old', payload: { text: 'Second boss.' } }) })
  await settle()
  check('a reply names its model when it changed since the message before', () => {
    const labels = [...build14m.node.querySelectorAll('.cs-b-who')].map(node => node.textContent)
    assert.match(labels.at(-1), /· GPT-6\.1 Sol · Max$/)
    assert.ok(!/GPT/.test(labels.at(-2)), 'the first message on a model has nothing to compare with')
  })
  // A model that asks before it is used (cost).
  let asked = 0
  scenario.byMethod['config.set'] = params => {
    scenario.sets.push(params)
    if (params.key === 'model' && !params.confirm_expensive_model) { asked += 1; return { confirm_required: true, confirm_message: 'Opus costs 5× more.' } }
    return { key: params.key, value: params.value }
  }
  await act(async () => { chip().dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Claude Subscription', pop())
  await act(async () => { pop().querySelectorAll('.cs-b-mp-row')[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('a model that asks first shows its question in the panel, and the switch waits', () => {
    assert.equal(asked, 1); assert.match(pop().querySelector('.cs-b-mp-confirm').textContent, /Opus costs 5× more\./)
    assert.match(chip().textContent, /GPT-6\.1 Sol/)
  })
  await click('Use it', pop())
  await settle()
  check('Use it switches, confirmed', () => {
    assert.deepEqual(scenario.sets.at(-1), { session_id: 'rt-of-st-old', key: 'model', value: 'claude-opus-5-5[1m] --provider claude-sub --session', confirm_expensive_model: true })
    assert.match(chip().textContent, /Claude Opus 5\.5/)
  })
  // A provider that is no longer signed in.
  await act(async () => { emit({ type: 'session.info', session_id: 'rt-of-st-old', payload: { model: 'x-1', provider: 'off' } }) })
  await settle()
  check('a conversation on a signed-out provider says so on the button', () => {
    assert.match(chip().textContent, /off is signed out/); assert.ok(chip().classList.contains('warn'))
  })
  await build14m.close()
  // New Game starts on the picked model, and remembers it for the next one.
  scenario.storage.buildSelected = 'new'
  delete scenario.byMethod['config.set']
  const creates = []
  const plainCreate = scenario.byMethod['session.create']
  scenario.byMethod['session.create'] = params => { creates.push(params); return plainCreate(params) }
  const build14n = await mount(page)
  await settle()
  await act(async () => { build14n.node.querySelector('.cs-b-mp-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { build14n.node.querySelectorAll('.cs-b-mp-row')[1].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await act(async () => { build14n.node.querySelector('.cs-b-mp-chip').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await click('Low', build14n.node.querySelector('.cs-b-mp-pop'))
  await typeInto(build14n.node.querySelector('textarea[aria-label="Your game idea"]'), 'a frog racing game')
  await act(async () => { build14n.node.querySelector('.cs-b-new .cs-b-send[aria-label="Start building"]').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await settle()
  check('New Game makes its conversation on the picked model and effort, and remembers them', () => {
    assert.equal(creates.at(-1).model, 'claude-sonnet-5-5[1m]'); assert.equal(creates.at(-1).provider, 'claude-sub'); assert.equal(creates.at(-1).reasoning_effort, 'low')
    assert.deepEqual(scenario.storage.buildModel, { model: 'claude-sonnet-5-5[1m]', provider: 'claude-sub', effort: 'low' })
  })
  scenario.byMethod['session.create'] = plainCreate
  await build14n.close()
  // The game card on the Games page: cover art, tagline and genres; a game without one offers to make it.
  scenario.games = answered({ games: [
    { ...lib14[0], session: null, card: null, cover: false },
    { id: 'ccc333ccc333', title: 'Comet', displayTitle: 'Comet Drift', projectRoot: '/home/u/games/Comet', kind: 'gbstudio', state: 'ready',
      rom: { sha256: 'r1' }, webExport: true, thumb: 'data:image/png;base64,COVER', cover: true, chat: null, error: null, session: null,
      card: { title: 'Comet Drift', tagline: 'Dodge comets in a tiny ship.', description: 'Fly through three comet belts.', genres: ['Arcade', 'Action'],
        tags: [], controls: {}, complete: true, missing: [], hasCover: true } }], device: { hardwareEnabled: false, skipped: true } })
  scenario.storage.page = 'games'
  const shelf = await mount(page)
  await settle()
  const cards = () => [...shelf.node.querySelectorAll('.cs-gcard')]
  check('a game with a card shows its cover, display title, tagline and genres, and no Make cover art', () => {
    const comet = cards().find(node => /Comet Drift/.test(node.textContent))
    assert.equal(comet.querySelector('.cs-cart img').getAttribute('alt'), 'Comet Drift cover art')
    assert.equal(comet.querySelector('.cs-gtag').textContent, 'Dodge comets in a tiny ship.')
    assert.match(comet.querySelector('.cs-gtag').getAttribute('title'), /Arcade · Action/)
    assert.ok(!comet.querySelector('.nocover'))
  })
  {
    const comet = cards().find(node => /Comet Drift/.test(node.textContent))
    await act(async () => { comet.querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
    check('a game with a complete card has no Make cover art in its menu', () => { assert.ok(!/Make cover art/.test(comet.querySelector('.cs-gmenu').textContent)) })
    await act(async () => { dom.window.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape' })) })
  }
  const frog = () => cards().find(node => /Frog Post/.test(node.textContent))
  await act(async () => { frog().querySelector('.cs-split .caret').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  check('a game without a card offers Make cover art in its menu', () => { assert.ok(/Make cover art/.test(frog().querySelector('.cs-gmenu').textContent)) })
  await click('Make cover art', frog().querySelector('.cs-gmenu'))
  await settle()
  check('Make cover art opens that game on Build with the request in its message box, not sent', () => {
    assert.equal(shelf.node.querySelector('.cs-b-sw h2')?.textContent, 'Frog Post')
    assert.match(shelf.node.querySelector('textarea[aria-label="Message Hermes"]').value, /160x144 pixel-art cover.*chromatic_game_info/)
  })
  await shelf.close()
  scenario.storage.page = 'build'
  console.log(JSON.stringify({ passed: true, checks: checks.length, names: checks }, null, 1))
} finally {
  rmSync(work, { recursive: true, force: true })
}
// Turns never end in these scenarios, so the page's request polling would keep the process alive: every check
// has run and been printed, so stop here instead of waiting for it.
process.exit(0)
