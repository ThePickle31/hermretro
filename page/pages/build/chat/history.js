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
    tools.clear()
  }

  const addTool = (call, at) => {
    if (call.id && tools.has(call.id)) {
      return tools.get(call.id)
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

    return tool
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

      for (const inner of unwrapCalls(message.tool_call_id ?? null, message.name ?? message.tool_name, message.args)) {
        // Compact resume rows carry the name, arguments and call ID even when the result body is omitted.
        const first = inner.id === message.tool_call_id ? tools.get(`${inner.id}:0`) : null
        const step = first && (first.name === inner.name || inner.name === 'tool') ? first : addTool(inner, at)

        if (at && step.startedAt) {
          step.duration = Math.max(0, (at - step.startedAt) / 1000)
        }

        step.args = step.args ?? stepArgs(inner.args)
        step.resultSeen = typeof message.tool_call_id === 'string' && step.id === message.tool_call_id

        if (text) {
          step.info = stepInfo(step.name, text)

          if (toolFailed({ result: text })) {
            step.state = 'failed'
          }
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
