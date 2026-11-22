// Serves the page's browser preview on loopback and bridges its live mode to the real gateway:
//   node tools/dev/preview_server.mjs <preview dir> <Hermes Desktop dist/assets dir> <port>
// Started by `python tools/dev watch`. Prints one line: the live URL (its token guards the bridge).
//   /rpc     POST {profile, method, params, timeoutMs} -> {result} or {error}: one gateway JSON-RPC call
//   /routes  the profiles, as host.profileRoutes() answers them
//   /events  the gateways' events (server-sent), as host.onEvent hears them
//   /reload  a `reload` event whenever preview.js is rebuilt
// The bridge answers only requests that carry the token in an x-preview-token header (a page on another site cannot
// set one without a preflight, which this server never grants) and that name this server as their Host.
import { execFile } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { watch } from 'node:fs'
import { readdir, readFile, stat } from 'node:fs/promises'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { promisify } from 'node:util'

const [dir, assets, portText = '8790'] = process.argv.slice(2)
const root = path.resolve(dir)
const assetRoot = path.resolve(assets)
const port = Number(portText)
const token = randomBytes(18).toString('base64url')
const run = promisify(execFile)
const TYPES = {
  '.css': 'text/css', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.ttf': 'font/ttf', '.wasm': 'application/wasm', '.woff2': 'font/woff2'
}
const gateways = new Map()
const eventClients = new Set()
const reloadClients = new Set()

// One WebSocket per profile, opened on first use the way the app attaches (`hermes gateway attach`), reopened after
// it closes.
function gateway(profile) {
  if (gateways.has(profile)) return gateways.get(profile)
  const pending = new Map()
  let nextId = 1
  const ready = (async () => {
    const args = (profile === 'default' ? [] : ['-p', profile]).concat(['gateway', 'attach', '--json'])
    const { url, protocols } = JSON.parse((await run('hermes', args, { encoding: 'utf8' })).stdout)
    const ws = new WebSocket(url, protocols)
    await new Promise((resolve, reject) => {
      ws.onopen = resolve
      ws.onerror = () => reject(new Error(`no gateway socket for ${profile}`))
    })
    ws.onmessage = event => {
      let message
      try { message = JSON.parse(event.data) } catch { return }
      if (message.method === 'event') return send(eventClients, 'message', JSON.stringify(message.params))
      const call = pending.get(message.id)
      if (!call) return
      pending.delete(message.id)
      call.done(message)
    }
    ws.onclose = () => {
      gateways.delete(profile)
      for (const call of pending.values()) call.done({ error: { code: -32000, message: `the ${profile} gateway closed` } })
      pending.clear()
    }
    return ws
  })()
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
  ready.catch(() => gateways.delete(profile))
  gateways.set(profile, connection)
  return connection
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
  return names.map(profile => ({ connectionId: 'local', profile }))
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

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, `http://${request.headers.host}`)
  if (request.headers.host !== `127.0.0.1:${port}`) return json(response, 403, { error: 'wrong host' })
  if (url.pathname === '/reload') return stream(request, response, reloadClients)
  const bridged = ['/rpc', '/routes', '/events'].includes(url.pathname)
  if (!bridged) return serveFile(response, url.pathname === '/' ? '/index.html' : url.pathname)
  const given = url.pathname === '/events' ? url.searchParams.get('token') : request.headers['x-preview-token']
  if (given !== token) return json(response, 403, { error: 'no token' })
  if (url.pathname === '/events') return stream(request, response, eventClients)
  if (url.pathname === '/routes') return json(response, 200, await profiles())
  try {
    const { profile, method, params, timeoutMs } = await readBody(request)
    const answer = await gateway(profile || 'hermretro').call(method, params ?? {}, timeoutMs)
    json(response, 200, answer.error ? { error: answer.error } : { result: answer.result })
  } catch (error) {
    json(response, 200, { error: { code: -32000, message: String(error?.message ?? error) } })
  }
})

watch(root, (_event, name) => {
  if (name === 'preview.js') send(reloadClients, 'reload', '{}')
})

server.listen(port, '127.0.0.1', () => {
  console.log(`http://127.0.0.1:${port}/index.html?live=${token}&mode=dark&p=build`)
})
