// The sandbox's browser: headless Chromium on the sandbox's Hermes Webapp, driven over loopback HTTP.
//   node tools/dev/studio_browser.mjs <sandbox dir> <Hermes Desktop source dir>
// Started by `python tools/dev studio up`, which passes HERMES_HOME (the sandbox's) and STUDIO_TOKEN in the
// environment. It signs in with a one-use link from `hermes webapp --no-open` (never a window: the browser is
// headless and nothing is opened on the desktop), turns the hermretro page on, opens it and writes its port to
// <sandbox>/browser.port. `python tools/dev ui <verb>` then posts {verb, ...} to /do with the token in
// x-studio-token. The pages' storage (the app's and the plugin's) is kept in <sandbox>/browser-state.json, so a
// restart opens on the same game.
import { execFile } from 'node:child_process'
import { existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs'
import http from 'node:http'
import { createRequire } from 'node:module'
import os from 'node:os'
import path from 'node:path'
import { promisify } from 'node:util'

const [sandbox, desktop] = process.argv.slice(2)
const token = process.env.STUDIO_TOKEN
const run = promisify(execFile)
const require = createRequire(path.join(desktop, 'package.json'))
const { chromium } = require('@playwright/test')
const STATE = path.join(sandbox, 'browser-state.json')
const SHOTS = path.join(sandbox, 'shots')
const ROUTE = '#/hermretro'
const VIEWPORT = { width: 1440, height: 900 }
// Hermes ships a package's desktop half switched off until the user turns it on (Capabilities > Plugins); this is
// that choice, made for the sandbox's page.
const DECISIONS = 'hermes.desktop.pluginDecisions.v2'
const errors = []

/** A Chromium Playwright can drive: its own download when present, else the newest one in its cache. */
function chromiumPath() {
  const own = chromium.executablePath()
  if (existsSync(own)) return own
  const cache = process.env.PLAYWRIGHT_BROWSERS_PATH || (process.platform === 'darwin' ? path.join(os.homedir(), 'Library', 'Caches', 'ms-playwright') : path.join(os.homedir(), '.cache', 'ms-playwright'))
  const inside = process.platform === 'darwin'
    ? ['chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing', 'chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing', 'chrome-mac/Chromium.app/Contents/MacOS/Chromium']
    : ['chrome-linux64/chrome', 'chrome-linux/chrome']
  const folders = existsSync(cache) ? readdirSync(cache).filter(name => /^chromium-\d+$/.test(name)).sort((a, b) => Number(b.slice(9)) - Number(a.slice(9))) : []
  for (const folder of folders) for (const file of inside) if (existsSync(path.join(cache, folder, file))) return path.join(cache, folder, file)
  throw new Error(`no Chromium for Playwright\nFIX: cd ${desktop} && npx playwright install chromium`)
}

async function signIn(page) {
  const { stdout } = await run('hermes', ['webapp', '--no-open', '--skip-build'], { env: process.env, encoding: 'utf8' })
  const link = stdout.match(/http:\/\/127\.0\.0\.1:\d+\/webapp\/launch#\S+/)?.[0]
  if (!link) throw new Error(`hermes webapp gave no sign-in link:\n${stdout.slice(-400)}`)
  await page.goto(link)
  await page.waitForURL(url => !url.pathname.startsWith('/webapp/launch'), { timeout: 30_000 })
  return new URL(page.url()).origin
}

const browser = await chromium.launch({ headless: true, executablePath: chromiumPath() })
const context = await browser.newContext({
  viewport: VIEWPORT,
  colorScheme: 'dark',
  storageState: existsSync(STATE) ? STATE : undefined
})
await context.addInitScript(key => {
  const decisions = JSON.parse(localStorage.getItem(key) || '{}')
  decisions.hermretro = true
  localStorage.setItem(key, JSON.stringify(decisions))
}, DECISIONS)
const page = await context.newPage()
page.on('console', message => {
  if (message.type() === 'error') errors.push(message.text().slice(0, 500))
})
page.on('pageerror', error => errors.push(String(error).slice(0, 500)))
const origin = await signIn(page)

// Through the sidebar's HermRetro row, as a user opens it (the app routes to its home screen while it boots).
async function openStudio() {
  if (!page.url().startsWith(origin)) await page.goto(origin)
  const nav = page.getByText('HermRetro', { exact: true }).first()
  await nav.waitFor({ timeout: 60_000 })
  await nav.click()
  await page.getByRole('button', { name: /^build$/i }).first().waitFor({ timeout: 30_000 })
}

await openStudio()

/** The first visible element `target` names: a CSS selector, a button or link's name, or text on the page. */
async function find(target) {
  const candidates = /^[.#[]|^[a-z]+[.#[:]/.test(target)
    ? [page.locator(target)]
    : [page.getByRole('button', { name: target, exact: true }), page.getByRole('link', { name: target, exact: true }), page.getByRole('tab', { name: target, exact: true }), page.getByText(target, { exact: true }), page.getByRole('button', { name: target }), page.getByText(target)]
  for (const locator of candidates) {
    const count = await locator.count()
    for (let index = 0; index < count; index += 1) if (await locator.nth(index).isVisible()) return locator.nth(index)
  }
  throw new Error(`nothing visible matches ${JSON.stringify(target)}`)
}

const busy = () => page.locator('.cs-b-pill.busy, button[aria-label="Stop"]').count()

/** Until no turn runs, seen twice in a row a second apart (a turn's steps leave short gaps between them). */
async function idle(timeout) {
  const end = Date.now() + timeout
  let quiet = 0
  while (quiet < 2) {
    if (Date.now() > end) throw new Error(`a turn was still running after ${timeout / 1000} s`)
    quiet = (await busy()) ? 0 : quiet + 1
    await page.waitForTimeout(1000)
  }
}

async function shot({ name, full, target }) {
  mkdirSync(SHOTS, { recursive: true })
  const file = path.join(SHOTS, `${(name || `shot-${Date.now()}`).replace(/[^\w.-]+/g, '-')}.png`)
  await page.waitForTimeout(300) // let a click's transition finish
  if (target) await (await find(target)).screenshot({ path: file })
  else await page.screenshot({ path: file, fullPage: Boolean(full) })
  return { file }
}

const VERBS = {
  shot,
  text: async ({ target }) => ({ text: await (target ? await find(target) : page.locator('body')).ariaSnapshot() }),
  go: async ({ page: name }) => {
    if (!page.url().includes(ROUTE)) await openStudio()
    await (await find(name[0].toUpperCase() + name.slice(1))).click()
    return {}
  },
  click: async ({ target }) => (await (await find(target)).click(), {}),
  type: async ({ text, target, submit }) => {
    const box = await find(target || 'textarea')
    await box.fill(text)
    if (submit) await box.press('Enter')
    return {}
  },
  // Send a message from the Build page's box (the New Game box when no game is open), then wait for the turn.
  say: async ({ text, wait = true, timeout = 600 }) => {
    const box = page.locator('textarea:visible').last()
    await box.fill(text)
    await box.press('Enter')
    if (wait) {
      await page.waitForTimeout(1500)
      await idle(timeout * 1000)
    }
    return {}
  },
  idle: async ({ timeout = 600 }) => (await idle(timeout * 1000), {}),
  wait: async ({ target, ms, timeout = 60 }) => {
    if (ms) await page.waitForTimeout(ms)
    if (target) await page.getByText(target).first().waitFor({ timeout: timeout * 1000 })
    return {}
  },
  eval: async ({ js }) => ({ value: await page.evaluate(js) }),
  resize: async ({ width, height }) => (await page.setViewportSize({ width, height: height || VIEWPORT.height }), {}),
  theme: async ({ mode }) => (await page.emulateMedia({ colorScheme: mode }), {}),
  reload: async () => {
    await page.reload()
    await openStudio()
    return {}
  },
  errors: async () => ({ errors: errors.splice(0) }),
  storage: async ({ key, value }) => {
    await page.evaluate(([name, data]) => localStorage.setItem(`hermes.plugin.hermretro.${name}`, JSON.stringify(data)), [key, value])
    return {}
  },
  save: async () => (await context.storageState({ path: STATE }), {}),
  url: async () => ({ url: page.url() })
}

let queue = Promise.resolve()
const server = http.createServer((request, response) => {
  const reply = (status, body) => {
    response.writeHead(status, { 'Content-Type': 'application/json' })
    response.end(JSON.stringify(body))
  }
  if (request.method !== 'POST' || request.url !== '/do' || request.headers['x-studio-token'] !== token) return reply(403, { error: 'forbidden' })
  let body = ''
  request.on('data', chunk => { body += chunk })
  request.on('end', () => {
    // One command at a time, in the order they came.
    queue = queue.then(async () => {
      try {
        const args = JSON.parse(body || '{}')
        const verb = VERBS[args.verb]
        if (!verb) return reply(400, { error: `unknown verb ${args.verb}; one of: ${Object.keys(VERBS).join(', ')}` })
        const result = await verb(args)
        await context.storageState({ path: STATE })
        reply(200, result)
      } catch (error) {
        reply(500, { error: String(error?.message ?? error).slice(0, 2000) })
      }
    })
  })
})

server.listen(0, '127.0.0.1', () => {
  writeFileSync(path.join(sandbox, 'browser.port'), String(server.address().port))
  console.log(`ready on ${origin}`)
})

const stop = async () => {
  try { await context.storageState({ path: STATE }) } catch {}
  await browser.close()
  process.exit(0)
}
process.on('SIGTERM', stop)
process.on('SIGINT', stop)
