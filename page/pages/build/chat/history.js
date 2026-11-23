// A stored session's messages as conversation items.
import { ROM_BUILD_TOOL } from '#app/tools.js'
import { reportOf } from './report.js'
import { stepArgs, stepInfo, toolFailed } from './steps.js'
import { toolResultObject, unwrapCalls } from './tool-results.js'

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

function matchingStep(occurrence, call, index, count) {
  if (!occurrence) {
    return null
  }

  const { steps, finished } = occurrence
  if (count === steps.length) {
    const step = steps[index]

    return !finished.has(step) && (step.name === call.name || call.name === 'tool') ? step : null
  }

  const unmatched = steps.filter(step => step.name === call.name && !finished.has(step))

  return unmatched.length === 1 ? unmatched[0] : null
}

/** The transcript as the gateway stores it, in the Build page's shape: turns end with an `end` item
 *  (from the timestamps, so "Worked for…" shows how long each one took). */
export function historyItems(messages, running = false) {
  const items = []
  const tools = new Map()
  let agentSinceUser = false
  let lastAt = null
  let stepCount = 0

  const closeTurn = () => {
    if (agentSinceUser) {
      const startedAt = items.findLast(item => item.kind === 'user' && !item.followup)?.at ?? null

      items.push({ kind: 'end', status: 'complete', at: lastAt, startedAt, history: true })
    }

    agentSinceUser = false
    tools.clear()
  }

  const addTool = (call, at) => {
    const tool = { id: `history-${stepCount++}`, name: call.name, args: stepArgs(call.args), report: reportOf(call.name, call.args), state: call.name === ROM_BUILD_TOOL ? 'unknown' : 'done', startedAt: at }
    const last = items[items.length - 1]

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
    const timestamp = Number.isFinite(message.timestamp) && message.timestamp > 0 ? message.timestamp : null
    const at = timestamp === null ? null : timestamp * 1000

    if (message.role === 'user') {
      if (!text.trim()) {
        continue
      }

      const followup = message.display_kind === 'steer'
      if (!followup) {
        closeTurn()
      }
      items.push({ kind: 'user', text, at, followup })
    } else if (message.role === 'assistant') {
      agentSinceUser = true

      if (text.trim()) {
        items.push({ kind: 'assistant', open: false, text, at })
      }

      for (const call of Array.isArray(message.tool_calls) ? message.tool_calls : []) {
        const id = call?.id ?? null
        const name = call?.function?.name ?? call?.name
        const steps = unwrapCalls(id, name, call?.function?.arguments ?? call?.args).map(inner => addTool(inner, at))

        if (id) {
          tools.set(id, { name, steps, finished: new Set() })
        }
      }
    } else if (message.role === 'tool') {
      agentSinceUser = true
      const id = message.tool_call_id ?? null
      const name = message.name ?? message.tool_name
      const pending = tools.get(id)
      const calls = unwrapCalls(id, name, message.args)
      const result = toolResultObject(text)
      const failed = toolFailed({ result })
      const exactCall = calls.length === 1 && (!pending || pending.steps.length === 1)
      // A raw result can retain the wrapper's name and omit its arguments, including on validation errors.
      const outerResult = pending?.name === 'tool_call' && calls.length === 1 && ['tool_call', 'tool'].includes(calls[0].name)
      let steps

      if (outerResult && (exactCall || failed)) {
        steps = pending.steps.filter(step => !pending.finished.has(step))
      } else {
        // A compact row can stand alone or describe a single member of the original batch.
        steps = calls.map((inner, index) => {
          const step = matchingStep(pending, inner, index, calls.length) ?? addTool(inner, at)

          step.args = step.args ?? stepArgs(inner.args)

          return step
        })
      }

      for (const step of steps) {
        if (at && step.startedAt) {
          step.duration = Math.max(0, (at - step.startedAt) / 1000)
        }

        if (exactCall && typeof id === 'string' && timestamp !== null) {
          step.resultCall = { id, timestamp }
        }

        if (text) {
          step.info = stepInfo(step.name, text, exactCall)

          if (failed) {
            step.state = 'failed'
          } else if (step.state === 'unknown' && (step.info?.buildRef || result?.ok === true || result?.structuredContent?.success === true)) {
            step.state = 'done'
          }
        }

        if (pending?.steps.includes(step)) {
          pending.finished.add(step)
        }
      }

      if (pending && (outerResult || pending.finished.size === pending.steps.length)) {
        tools.delete(id)
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
