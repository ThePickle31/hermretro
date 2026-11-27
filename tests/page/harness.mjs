// Shared harness for the page tests (tests/page/page-*.test.mjs): it loads the built desktop/plugin.js
// (what ships) with the SDK stand-in from sdk-stub.mjs into jsdom, and hands each scenario file a fresh page,
// scenario object and the helpers below. After editing page/ run node tools/bundle/bundle.mjs first.
// Needs react, react-dom and jsdom (tools/bundle/node-modules.mjs says where they come from):
//   node tests/page/page-<name>.test.mjs [path to a node_modules folder, relative or absolute]
// The bundle keeps module-level state (the Build conversations, the profile route), so each file runs in its
// own process with its own copy; a file sets every precondition it relies on itself.
// What a query shows is read at render time: the stub's useQuery returns scenario[<query key>] (scenario.games,
// scenario.player, ...) while the page renders, so set that value before render() (or rerender after changing it);
// a value set afterwards is not seen. A function there gets the query's whole key and answers for it (a per-game
// query: scenario.captures = key => answered({ captures: byGame[key[2]] })).
// scenario.byMethod[<rpc>] is what a direct host.request call answers.
// A slot's contributions render in PAGES order (page/pages/index.js), not in the order pages were written.
// Assert DOM presence and identity as booleans so failures do not inspect React's object graph, and the page's text
// with shows(expected) / hides(expected) (a string or a RegExp), whose failures print only the part of the page
// around the closest match instead of all of it.
import assert from 'node:assert/strict'
import { cpSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { staleReasons } from '../../tools/bundle/bundle.mjs'
import { findModules, MISSING_HINT } from '../../tools/bundle/node-modules.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const realSetTimeout = globalThis.setTimeout  // settle() waits on the real clock, even while holdTimers() holds timers

/** The optional node_modules folder after the file's name, absolute: the temp folder links to it, and a relative
 *  link target would be read from inside that folder (so `node tests/page/<file> tools/npm/node_modules` works). */
export const modulesFrom = argv => (argv[2] ? path.resolve(argv[2]) : null)

/** The button labelled `label` in a page's own tab bar (`.cs-tabs`, app/page-view.js), not the studio nav. */
export const tabButton = (document, label) =>
  [...document.querySelectorAll('.cs-tabs button')].find(node => node.textContent === label) ?? null

/** The label of the selected tab (`aria-selected`) in a page's own tab bar (`.cs-tabs`, app/page-view.js) inside
 *  `scope`, or null when it has none. The studio nav's open page is `currentTab()`, not this. */
export const selectedPageTab = scope =>
  scope?.querySelector('.cs-tabs [role="tab"][aria-selected="true"]')?.textContent ?? null

// The SDK stand-in, the bundle rewritten to use it, and the jsdom globals, in a temp folder that is removed
// however the file ends.
async function load() {
  // The page under test is the built bundle: never test one that no longer matches page/.
  const stale = staleReasons()

  if (stale.length) {
    console.error(`${stale.join('\n')}\nRun: node tools/bundle/bundle.mjs`)
    process.exit(1)
  }

  const modules = modulesFrom(process.argv) || findModules(['react', 'react-dom', 'jsdom'])

  if (!modules) {
    console.error(`react, react-dom and jsdom were not found; ${MISSING_HINT}`)
    process.exit(1)
  }
  const work = mkdtempSync(path.join(os.tmpdir(), 'chromatic-page-'))
  // Interrupted (Ctrl+C, a CI timeout): still remove the temp folder.
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.once(signal, () => { rmSync(work, { recursive: true, force: true }); process.exit(130) })
  }
  // A crash outside the scenario's own try (an unhandled rejection, an error thrown in a timer): clean up, fail.
  for (const event of ['uncaughtException', 'unhandledRejection']) {
    process.once(event, error => { console.error(error); rmSync(work, { recursive: true, force: true }); process.exit(1) })
  }
  try {
    symlinkSync(modules, path.join(work, 'node_modules'), 'dir')
    cpSync(path.join(here, 'sdk-stub.mjs'), path.join(work, 'sdk-stub.mjs'))
    writeFileSync(path.join(work, 'plugin.mjs'),
      readFileSync(path.join(here, '..', '..', 'desktop', 'plugin.js'), 'utf8').replace(/(['"])@hermes\/plugin-sdk\1/g, "'./sdk-stub.mjs'"))
    writeFileSync(path.join(work, 'run.mjs'), `
      import { JSDOM } from 'jsdom'
      import { VirtualConsole } from 'jsdom'
      // An error thrown inside the page (a React event handler, a timer) reaches only jsdom's console: fail on it.
      const virtualConsole = new VirtualConsole()
      virtualConsole.forwardTo(console, { jsdomErrors: 'none' })
      virtualConsole.on('jsdomError', error => {
        if (/Not implemented/.test(String(error?.message))) return   // canvas and friends: jsdom has none
        console.error(error); process.exitCode = 1; globalThis.__pageErrors = (globalThis.__pageErrors ?? 0) + 1
      })
      const dom = new JSDOM('<!doctype html><div id="root"></div>', { virtualConsole })
      globalThis.window = dom.window; globalThis.document = dom.window.document
      globalThis.IS_REACT_ACT_ENVIRONMENT = true
      const { createRoot } = await import('react-dom/client')
      const { act } = await import('react')
      const { emit, host, scenario } = await import('./sdk-stub.mjs')
      const plugin = (await import('./plugin.mjs')).default
      export { act, createRoot, dom, emit, host, plugin, scenario }
    `)
    return { work, loaded: await import(pathToFileURL(path.join(work, 'run.mjs')).href) }
  } catch (error) {
    rmSync(work, { recursive: true, force: true })
    throw error
  }
}

// The registered page and every helper the scenarios share.
function environment({ act, createRoot, dom, emit, host, plugin, scenario }) {
  const registrations = []
  const settingsPages = []
  const intervals = []
  const ctx = {
    registerMany: list => registrations.push(...list),
    registerSettingsPage: entry => settingsPages.push(entry),
    setTimeout: (fn, ms) => { const id = setTimeout(fn, 0); return () => clearTimeout(id) },
    setInterval: (fn, ms) => { intervals.push({ fn, ms }); return () => { intervals.splice(intervals.findIndex(i => i.fn === fn), 1) } },
    os: { writeClipboard: async value => { scenario.clipboard.push(value); return true }, openExternal: async () => true, revealPath: async path => { scenario.revealed = path; return true } },
    storage: { get: (key, fallback) => scenario.storage[key] ?? fallback, set: (key, value) => { scenario.storage[key] = value } }
  }
  plugin.register(ctx)
  const page = registrations.find(entry => entry.area === 'routes')
  const root = createRoot(dom.window.document.getElementById('root'))
  const render = async () => { await act(async () => { root.render(page.render()) }) }
  const text = () => dom.window.document.body.textContent.replace(/\s+/g, ' ')
  const heading = () => dom.window.document.querySelector('h2')?.textContent ?? null
  // The first-run welcome's headline.
  const WELCOME = 'Make a game.Play it tonight.'
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
  // A page's own tab (its tab bar, `.cs-tabs`); tab(name) above is the studio nav's.
  const pageTab = async label => {
    const button = tabButton(dom.window.document, label)
    assert.ok(button, 'page tab not found: ' + label + ' (tabs: ' + [...dom.window.document.querySelectorAll('.cs-tabs button')].map(node => node.textContent).join(', ') + ')')
    await act(async () => { button.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  }
  const currentTab = () => nav()?.querySelector('[aria-current="page"]')?.firstChild?.textContent ?? null
  // The open page's own selected tab (its `.cs-tabs`), looked up only in the mounted page (#root), never in a pane
  // that mount() added beside it; currentTab() above is the studio nav's.
  const currentPageTab = () => selectedPageTab(dom.window.document.getElementById('root'))
  const settle = async (ms = 20) => { await act(async () => { await new Promise(resolve => realSetTimeout(resolve, ms)) }) }
  const button = label => [...dom.window.document.querySelectorAll('button')].find(node => node.textContent.includes(label))
  const typeInto = async (input, value) => {
    const proto = input.tagName === 'TEXTAREA' ? dom.window.HTMLTextAreaElement.prototype : dom.window.HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(input, value)
    await act(async () => { input.dispatchEvent(new dom.window.Event('input', { bubbles: true })) })
  }
  const key = async (type, keyName, target = dom.window) => {
    await act(async () => { target.dispatchEvent(new dom.window.KeyboardEvent(type, { key: keyName, bubbles: true, cancelable: true })) })
  }
  // A page (or a workspace tab's render) in its own root, beside the main one.
  const mount = async entry => {
    const node = dom.window.document.createElement('div'); dom.window.document.body.appendChild(node)
    const paneRoot = createRoot(node)
    await act(async () => { paneRoot.render(entry.render()) })
    return { node, rerender: async () => { await act(async () => { paneRoot.render(entry.render()) }) }, close: async () => { await act(async () => { paneRoot.unmount() }); node.remove() } }
  }
  const shows = (expected, message) => assertShows(text(), expected, message)
  const hides = (expected, message) => assertHides(text(), expected, message)
  const checks = []
  // A failing check names itself on stderr first: tools/check.py page shows a failing file's own output.
  const check = (name, fn) => {
    try { fn() } catch (error) { console.error(`check failed: ${name}`); throw error }
    checks.push(name)
  }
  // The page's long timers (the Build page's open-request poll, 1.2 to 4 s), held instead of run by the real
  // clock: a fixed wait for one raced it on a loaded machine (the poll came late, or early with an old answer).
  // Call holdTimers() before the page schedules them; clock.fire() then runs every timer held so far, once.
  const holdTimers = (atLeast = 1_000) => {
    const held = new Map()
    const realSet = realSetTimeout
    const realClear = globalThis.clearTimeout
    let next = 1_000_000
    globalThis.setTimeout = (fn, ms = 0, ...args) => {
      if (!(ms >= atLeast)) return realSet(fn, ms, ...args)
      next += 1; held.set(next, () => fn(...args)); return next
    }
    globalThis.clearTimeout = id => (held.delete(id) ? undefined : realClear(id))
    return {
      held: () => held.size,
      fire: async () => {
        const due = [...held.values()]
        held.clear()
        await act(async () => { for (const run of due) run() })
        await settle()
      }
    }
  }

  // The Build page's starting point (page-build*.test.mjs): setup finished in this profile (hardware off and skipped),
  // the Build page open; `selected` is the game (or 'new') it remembers as storage.buildSelected.
  const buildScenario = ({ selected } = {}) => {
    const complete = completeStatus()
    scenario.status = answered({ ...complete, hardware_enabled: false }); scenario.doctor = answered(doctor([]))
    scenario.storage = { setup: { hardwareSkipped: true, onboarded: true }, page: 'build', ...(selected ? { buildSelected: selected } : {}) }
    scenario.ambient = complete; scenario.routes = []; scenario.byProfile = {}
  }

  return {
    act, createRoot, dom, emit, host, plugin, scenario, buildScenario,
    registrations, settingsPages, intervals, ctx, page, root, render, text, shows, hides, heading, WELCOME, headings, click, nav, tab, pageTab, currentTab,
    currentPageTab, settle, button, typeInto, key, mount, checks, check, holdTimers,
    answered, notLoaded, cli, status, doctor, manifest, installAnswer, complete: completeStatus()
  }
}

// Text assertions that fail with ~300 characters of the page around the closest match, not the whole page.
// `expected` is a string or a RegExp; the closest match is the longest leading part of it that the page has.
const AROUND = 150
const literal = expected => expected instanceof RegExp
  ? expected.source.split(/\\[dDsSwWbB]|(?<!\\)[[\](){}|?*+^$.]/).map(part => part.replace(/\\(.)/g, '$1'))
    .reduce((a, b) => (b.length > a.length ? b : a), '')
  : expected
export function nearest(page, expected) {
  const needle = literal(expected)
  for (let length = needle.length; length >= 3; length--) {
    const at = page.indexOf(needle.slice(0, length))
    if (at >= 0) return { at, matched: needle.slice(0, length) }
  }
  return { at: 0, matched: '' }
}
const excerpt = (page, at) => (at > AROUND ? '…' : '') + page.slice(Math.max(0, at - AROUND), at + AROUND) + (at + AROUND < page.length ? '…' : '')
const found = (page, expected) => (expected instanceof RegExp ? page.search(expected) : page.indexOf(expected))
export function assertShows(page, expected, message) {
  if (found(page, expected) >= 0) return
  const { at, matched } = nearest(page, expected)
  const where = matched ? `closest: "${matched}" at ${at}` : 'nothing close; the start of the page'
  assert.fail(`${message ? message + ': ' : ''}the page does not show ${expected} (${page.length} chars; ${where}):\n  ${excerpt(page, at)}`)
}
export function assertHides(page, expected, message) {
  const at = found(page, expected)
  if (at < 0) return
  assert.fail(`${message ? message + ': ' : ''}the page shows ${expected} at ${at}:\n  ${excerpt(page, at)}`)
}

// Query answers and backend replies.
const answered = data => ({ data, isFetching: false, isPending: false })
const notLoaded = { isError: true, error: Object.assign(new Error('unknown method'), { code: -32601 }), isFetching: false }
const cli = state => ({ state, version: state === 'installed' ? '1.2.1' : null, terms: 'https://modretro.com/eula' })
const status = (extra = {}) => ({
  ok: true, plugin: { version: '9.9.9' }, platform: { system: 'linux', machine: 'x86_64', qualified: true },
  node: { found: true, version: '26.13.0', required: '22', ok: true }, engine: { present: true, version: '2.0.0', verified: true },
  hardware_enabled: false, project: null,
  profile: { name: 'hermretro', is_studio: true, studio: { name: 'hermretro', exists: true, installed: true, ours: true } },
  deps: { toolchain_root: '/h/hermretro/.cache/toolchain', device_cli: cli('missing') }, ...extra
})
const doctor = missing => ({ ok: true, missing_required: missing, components: [
  { id: 'cli', label: 'GB Studio CLI', status: missing.length ? 'missing' : 'ready', required: '4.3.2', optional: false }] })
const manifest = { bytes: 708_271_425, disk_bytes: 2_300_000_000, measured_on: 'linux-x64', exact: true, items: [
  { id: 'gbdk', component: 'gbdk', name: 'GBDK compiler', version: '4.5.0', source: 'github.com/gbdk-2020/gbdk-2020', bytes: 6_870_728, purpose: 'Compiles C for the Game Boy CPU', approx: false },
  { id: 'gbstudio', component: 'cli', name: 'GB Studio CLI', version: '4.3.2', source: 'github.com/chrismaltby/gb-studio', bytes: 18_130_254, purpose: 'Builds your game into a ROM', approx: false },
  { id: 'packages', component: 'cli', name: 'GB Studio packages', version: 'yarn 4.4.1', source: 'registry.npmjs.org', bytes: 551_000_000, purpose: 'The libraries GB Studio needs', approx: true },
  { id: 'uv', component: 'uv', name: 'uv', version: '0.12.6', source: 'github.com/astral-sh/uv', bytes: 20_274_889, purpose: 'Installs the Python parts', approx: false },
  { id: 'emulator', component: 'emulator', name: 'Python, PyBoy and Pillow', version: '3.13.12 · 2.7.0 · 12.3.0', source: 'python-build-standalone · pypi.org', bytes: 108_000_000, purpose: 'The emulator Hermes playtests with', approx: true }] }
const installAnswer = install => answered({ ok: true, manifest, root: '/h/hermretro/.cache/toolchain', install })
// Every step verified, hardware tools on: the studio as a finished setup reports it.
const completeStatus = () => status({ hardware_enabled: true, deps: { toolchain_root: '/h/hermretro/.cache/toolchain', device_cli: cli('installed') } })

// Runs one scenario file: a fresh page, then `body(env)`. Prints the checks that ran as JSON and exits 0, or
// prints the failure and exits 1; either way the last line is '<file>: N passed, M failed'. Exits either way:
// turns never end in these scenarios, so the page's request polling would keep the process alive.
export async function runScenario(body) {
  const { work, loaded } = await load()
  const file = path.basename(process.argv[1] ?? 'page test')
  let code = 0
  let env = null

  try {
    env = environment(loaded)
    await body(env)
    if (globalThis.__pageErrors) throw new Error(`${globalThis.__pageErrors} error(s) were thrown inside the page (see above)`)
    console.log(JSON.stringify({ passed: true, checks: env.checks.length, names: env.checks }, null, 1))
  } catch (error) {
    console.error(error)
    code = 1
  } finally {
    rmSync(work, { recursive: true, force: true })
  }
  // Last, so the tail of a long run shows the result (a failure stops the scenario: the rest did not run).
  console.log(`${file}: ${env?.checks.length ?? 0} passed, ${code} failed`)
  process.exit(code)
}
