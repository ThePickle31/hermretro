// Shared harness for the page tests (tests/desktop/page-*.test.mjs): it loads the built desktop/plugin.js
// (what ships) with the SDK stand-in from sdk-stub.mjs into jsdom, and hands each scenario file a fresh page,
// scenario object and the helpers below. After editing desktop-src/ run node tools/bundle.mjs first.
// Needs react, react-dom and jsdom (tools/node-modules.mjs says where they come from):
//   node tests/desktop/page-<name>.test.mjs [path to a node_modules folder]
// The bundle keeps module-level state (the Build conversations, the profile route), so each file runs in its
// own process with its own copy; a file sets every precondition it relies on itself.
// Assert DOM presence and identity as booleans so failures do not inspect React's object graph.
import assert from 'node:assert/strict'
import { cpSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { staleReasons } from '../../tools/bundle.mjs'
import { findModules, MISSING_HINT } from '../../tools/node-modules.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))

// The SDK stand-in, the bundle rewritten to use it, and the jsdom globals, in a temp folder that is removed
// however the file ends.
async function load() {
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
  const work = mkdtempSync(path.join(os.tmpdir(), 'chromatic-page-'))
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
    return { work, loaded: await import(pathToFileURL(path.join(work, 'run.mjs')).href) }
  } catch (error) {
    rmSync(work, { recursive: true, force: true })
    throw error
  }
}

// The registered page and every helper the scenarios share.
function environment({ act, createRoot, dom, emit, host, plugin, scenario }) {
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
  // A page (or a workspace tab's render) in its own root, beside the main one.
  const mount = async entry => {
    const node = dom.window.document.createElement('div'); dom.window.document.body.appendChild(node)
    const paneRoot = createRoot(node)
    await act(async () => { paneRoot.render(entry.render()) })
    return { node, rerender: async () => { await act(async () => { paneRoot.render(entry.render()) }) }, close: async () => { await act(async () => { paneRoot.unmount() }); node.remove() } }
  }
  const checks = []
  const check = (name, fn) => { fn(); checks.push(name) }

  return {
    act, createRoot, dom, emit, host, plugin, scenario,
    registrations, intervals, ctx, page, root, render, text, heading, HOME, headings, click, nav, tab, currentTab,
    settle, button, typeInto, key, mount, checks, check,
    answered, notLoaded, cli, status, doctor, manifest, installAnswer, complete: completeStatus()
  }
}

// Query answers and backend replies.
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
// prints the failure and exits 1. Exits either way: turns never end in these scenarios, so the page's request
// polling would keep the process alive.
export async function runScenario(body) {
  const { work, loaded } = await load()
  let code = 0

  try {
    const env = environment(loaded)
    await body(env)
    console.log(JSON.stringify({ passed: true, checks: env.checks.length, names: env.checks }, null, 1))
  } catch (error) {
    console.error(error)
    code = 1
  } finally {
    rmSync(work, { recursive: true, force: true })
  }
  process.exit(code)
}
