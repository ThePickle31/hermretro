// A stored session's messages as conversation items.
import { reportOf } from './report.js'
import { stepArgs, stepInfo, toolFailed } from './steps.js'
import { unwrapCalls } from './tool-results.js'

/** A stored message's text: projected rows carry `text`, raw rows `content` (a string or parts). */
function messageText(message) {
  if (typeof message.text === 'string' && message.text) {
    return message.text
  }

  if (typeof message.content === 'string') {
    return message.content
  }

  return Array.isArray(message.content)
    ? message.content.map(part => (part?.type === 'text' && typeof part.text === 'string' ? part.text : '')).join('')
    : ''
}

/** The transcript as the gateway stores it, in the Build page's shape: turns end with an `end` item
 *  (from the timestamps, so "Worked for…" shows how long each one took). */
export function historyItems(messages, running = false) {
  const items = []
  const tools = new Map()
  let agentSinceUser = false
  let lastAt = null

  const closeTurn = () => {
    if (agentSinceUser) {
      const startedAt = [...items].reverse().find(item => item.kind === 'user')?.at ?? null

      items.push({ kind: 'end', status: 'complete', at: lastAt, startedAt, history: true })
    }

    agentSinceUser = false
  }

  const addTool = (call, at) => {
    if (call.id && tools.has(call.id)) {
      return
    }

    const tool = { id: call.id ?? `${items.length}`, name: call.name, args: stepArgs(call.args), report: reportOf(call.name, call.args), state: 'done', startedAt: at }
    const last = items[items.length - 1]

    if (call.id) {
      tools.set(call.id, tool)
    }

    if (last?.kind === 'tools') {
      last.tools.push(tool)
    } else {
      items.push({ kind: 'tools', tools: [tool] })
    }
  }

  for (const message of Array.isArray(messages) ? messages : []) {
    if (!message || message.display_kind === 'hidden') {
      continue
    }

    const text = messageText(message)
    const at = typeof message.timestamp === 'number' && message.timestamp > 0 ? message.timestamp * 1000 : null

    if (message.role === 'user') {
      if (!text.trim()) {
        continue
      }

      closeTurn()
      items.push({ kind: 'user', text, at })
    } else if (message.role === 'assistant') {
      agentSinceUser = true

      if (text.trim()) {
        items.push({ kind: 'assistant', open: false, text, at })
      }

      for (const call of Array.isArray(message.tool_calls) ? message.tool_calls : []) {
        for (const inner of unwrapCalls(call?.id ?? null, call?.function?.name ?? call?.name, call?.function?.arguments ?? call?.args)) {
          addTool(inner, at)
        }
      }
    } else if (message.role === 'tool') {
      agentSinceUser = true

      for (const inner of unwrapCalls(message.tool_call_id ?? null, message.name, message.args)) {
        // A deferred call's result row names only the outer tool_call: its one call is <id>:0.
        const known = inner.id && (tools.get(inner.id) ?? (inner.name === 'tool_call' ? tools.get(`${inner.id}:0`) : null))

        if (known) {
          // The result row's time is when the step finished.
          if (at && known.startedAt) {
            known.duration = Math.max(0, (at - known.startedAt) / 1000)
          }

          known.args = known.args ?? stepArgs(inner.args)
          // The result row says how the step went: a failed build stays failed after a reload.
          const result = text.trim().startsWith('{') ? text : null

          if (result) {
            known.info = stepInfo(known.name, result)

            if (toolFailed({ result })) {
              known.state = 'failed'
            }
          }
        } else {
          addTool(inner, at)
        }
      }
    }

    if (at) {
      lastAt = at
    }
  }

  if (!running) {
    closeTurn()
  }

  return items
}
