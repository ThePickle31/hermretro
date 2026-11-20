// Dev tool: call one gateway JSON-RPC method for a profile, as the desktop page does.
//   node tools/debug/gateway_rpc.mjs <profile|default> <method> [params-json]
// Needs Node 22 or newer (its built-in WebSocket) and a running gateway for the profile: `hermes -p <profile> gateway
// ensure` starts a local runtime without installing a service (`hermes gateway start` only starts an installed
// systemd/launchd service). Prints one JSON line; exit 0 with the answer, 1 on no gateway, a socket error or close,
// or no answer within 60 s.
// Output is cut to 1800 characters unless GATEWAY_RPC_FULL=1.
// Never prints the attach ticket.
import { execFileSync } from 'node:child_process'
const [profile, method, paramsJson] = process.argv.slice(2)
const args = (profile === 'default' ? [] : ['-p', profile]).concat(['gateway', 'attach', '--json'])
let attach
try {
  attach = JSON.parse(execFileSync('hermes', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }))
} catch (error) {
  const said = String(error.stderr || error.message || '').trim().slice(0, 600)
  console.log(JSON.stringify({ profile, error: `no gateway: ${said}` }))
  process.exit(1)
}
const ws = new WebSocket(attach.url, attach.protocols)
const timer = setTimeout(() => { console.log(JSON.stringify({ profile, error: 'timeout' })); process.exit(1) }, 60000)
ws.onopen = () => ws.send(JSON.stringify({ jsonrpc: '2.0', id: 1, method, params: JSON.parse(paramsJson || '{}') }))
ws.onmessage = event => {
  let message; try { message = JSON.parse(event.data) } catch { return }
  if (message.id !== 1) return
  clearTimeout(timer)
  const text = JSON.stringify({ profile, method, result: message.result, error: message.error })
  console.log(process.env.GATEWAY_RPC_FULL ? text : text.slice(0, 1800))
  ws.close(); process.exit(0)
}
ws.onerror = event => { clearTimeout(timer); console.log(JSON.stringify({ profile, error: 'socket error ' + (event.message || '') })); process.exit(1) }
ws.onclose = event => { clearTimeout(timer); console.log(JSON.stringify({ profile, closed: event.code, reason: event.reason })); process.exit(1) }
