// Serves the page's browser preview on loopback and bridges its live mode to the real gateway:
//   node tools/dev/preview_server.mjs <preview dir> <Hermes Desktop dist/assets dir> [port]
// Started by `python tools/dev watch`. Prints one line: the live URL (its token guards the bridge). Port 0 (the
// default) takes a free one, so every run is its own browser origin.
//   /rpc     POST {profile, method, params, timeoutMs} -> {result} or {error}: one plugin.hermretro.* call
//   /routes  the profiles, as host.profileRoutes() answers them
//   /events  the studio gateway's events and its connection state (server-sent), as host.onEvent and
//            host.state.gateway see them
//   /reload  a `reload` event whenever preview.js is rebuilt
// The bridge answers only requests that carry the token in an x-preview-token header (a page on another site cannot
// set one without a preflight, which this server never grants) and that name this server as their Host, and only
// the plugin's own RPCs, in a profile that exists.
import { execFile } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { watch } from 'node:fs'
import { readdir, readFile, stat } from 'node:fs/promises'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { promisify } from 'node:util'

const [dir, assets, portText = '0'] = process.argv.slice(2)
const root = path.resolve(dir)
const assetRoot = path.resolve(assets)
const token = randomBytes(18).toString('base64url')
const run = promisify(execFile)
const STUDIO = 'hermretro'
const METHODS = 'plugin.hermretro.'
const TYPES = {
  '.css': 'text/css', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.ttf': 'font/ttf', '.wasm': 'application/wasm', '.woff2': 'font/woff2'
}
const gateways = new Map()
const eventClients = new Set()
const reloadClients = new Set()
let host = ''
let gatewayState = 'connecting'
let redialDelay = 1000

// One WebSocket per profile, opened on first use the way the app attaches (`hermes -p <profile> gateway attach`).
// The studio's is reopened while anyone listens to its events; the others on their next call.
function gateway(profile) {
  if (gateways.has(profile)) return gateways.get(profile)
  const pending = new Map()
  let nextId = 1
  const ready = (async () => {
    const attached = await run('hermes', ['-p', profile, 'gateway', 'attach', '--json'], { encoding: 'utf8' })
    const { url, protocols } = JSON.parse(attached.stdout)
    const ws = new WebSocket(url, protocols)
    await new Promise((resolve, reject) => {
      ws.onopen = resolve
      ws.onerror = () => reject(new Error(`no gateway socket for ${profile}`))
    })
    ws.onmessage = event => {
      let message
      try { message = JSON.parse(event.data) } catch { return }
      if (message.method === 'event') {
        if (profile === STUDIO) send(eventClients, 'message', JSON.stringify(message.params))
        return
      }
      const call = pending.get(message.id)
      if (!call) return
      pending.delete(message.id)
      call.done(message)
    }
    ws.onclose = () => {
      gateways.delete(profile)
      for (const call of pending.values()) call.done({ error: { code: -32000, message: `the ${profile} gateway closed` } })
      pending.clear()
      if (profile === STUDIO) studioLost()
    }
    if (profile === STUDIO) setGatewayState('open')
    return ws
  })()
  ready.catch(() => {
    gateways.delete(profile)
    if (profile === STUDIO) studioLost()
  })
  const connection = {
    async call(method, params, timeoutMs = 30_000) {
      const ws = await ready
      const id = nextId++
      return new Promise(resolve => {
        const timer = setTimeout(() => {
          pending.delete(id)
          resolve({ error: { code: -32000, message: `${method}: no answer in ${timeoutMs} ms` } })
        }, timeoutMs)
        pending.set(id, { done: message => { clearTimeout(timer); resolve(message) } })
        ws.send(JSON.stringify({ jsonrpc: '2.0', id, method, params }))
      })
    }
  }
  gateways.set(profile, connection)
  return connection
}

function setGatewayState(state) {
  if (state === 'open') redialDelay = 1000
  if (state === gatewayState) return
  gatewayState = state
  send(eventClients, 'gateway', JSON.stringify({ state }))
}

// The studio's socket closed or would not open: say so, and dial again (backing off to 30 s) while a page listens.
function studioLost() {
  setGatewayState('closed')
  if (!eventClients.size) return
  setTimeout(() => {
    if (eventClients.size && !gateways.has(STUDIO)) gateway(STUDIO)
  }, redialDelay)
  redialDelay = Math.min(redialDelay * 2, 30_000)
}

function send(clients, event, data) {
  for (const response of clients) response.write(`event: ${event}\ndata: ${data}\n\n`)
}

function stream(request, response, clients) {
  response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' })
  response.write(': open\n\n')
  clients.add(response)
  request.on('close', () => clients.delete(response))
}

async function profiles() {
  const names = ['default']
  try {
    for (const entry of await readdir(path.join(os.homedir(), '.hermes', 'profiles'), { withFileTypes: true })) {
      if (entry.isDirectory()) names.push(entry.name)
    }
  } catch {}
  return names
}

function json(response, status, body) {
  response.writeHead(status, { 'content-type': 'application/json' })
  response.end(JSON.stringify(body))
}

async function readBody(request) {
  const chunks = []
  for await (const chunk of request) chunks.push(chunk)
  return JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}')
}

async function serveFile(response, pathname) {
  const wanted = path.normalize(decodeURIComponent(pathname))
  // The build links the Desktop's stylesheets (and their fonts) by their absolute path.
  const file = wanted.startsWith(assetRoot + path.sep) ? wanted : path.join(root, wanted)
  if (!file.startsWith(root + path.sep) && !file.startsWith(assetRoot + path.sep)) return json(response, 404, {})
  try {
    if (!(await stat(file)).isFile()) return json(response, 404, {})
    response.writeHead(200, { 'content-type': TYPES[path.extname(file)] ?? 'application/octet-stream', 'cache-control': 'no-store' })
    response.end(await readFile(file))
  } catch {
    json(response, 404, {})
  }
}

async function bridge(request, response, url) {
  const given = url.pathname === '/events' ? url.searchParams.get('token') : request.headers['x-preview-token']
  if (given !== token) return json(response, 403, { error: 'no token' })
  if (url.pathname === '/routes') return json(response, 200, (await profiles()).map(profile => ({ connectionId: 'local', profile })))
  if (url.pathname === '/events') {
    stream(request, response, eventClients)
    response.write(`event: gateway\ndata: ${JSON.stringify({ state: gatewayState })}\n\n`)
    if (!gateways.has(STUDIO)) gateway(STUDIO)
    return
  }
  const { profile = STUDIO, method, params, timeoutMs } = await readBody(request)
  if (typeof method !== 'string' || !method.startsWith(METHODS)) {
    return json(response, 200, { error: { code: -32601, message: `the preview bridges only ${METHODS}* calls` } })
  }
  if (!(await profiles()).includes(profile)) return json(response, 200, { error: { code: -32602, message: `no profile ${profile}` } })
  try {
    const answer = await gateway(profile).call(method, params ?? {}, timeoutMs)
    json(response, 200, answer.error ? { error: answer.error } : { result: answer.result })
  } catch (error) {
    json(response, 200, { error: { code: -32000, message: String(error?.message ?? error) } })
  }
}

const server = http.createServer(async (request, response) => {
  try {
    if (request.headers.host !== host) return json(response, 403, { error: 'wrong host' })
    const url = new URL(request.url, `http://${host}`)
    if (url.pathname === '/reload') return stream(request, response, reloadClients)
    if (['/rpc', '/routes', '/events'].includes(url.pathname)) return await bridge(request, response, url)
    await serveFile(response, url.pathname === '/' ? '/index.html' : url.pathname)
  } catch {
    if (!response.headersSent) json(response, 400, { error: 'bad request' })
    else response.end()
  }
})

watch(root, (_event, name) => {
  if (name === 'preview.js') send(reloadClients, 'reload', '{}')
})

server.listen(Number(portText), '127.0.0.1', () => {
  host = `127.0.0.1:${server.address().port}`
  console.log(`http://${host}/index.html?live=${token}&mode=dark&p=build`)
})
