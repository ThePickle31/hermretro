// Reading tool calls and their results.
/** A finished tool's result as an object (the gateway parses JSON results; a multimodal one keeps
 *  its text). */
export function toolResultObject(value) {
  if (value && typeof value === 'object') {
    return value._multimodal ? toolResultObject(value.text_summary ?? value.content?.[0]?.text) : value
  }

  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)

      return parsed && typeof parsed === 'object' ? parsed : null
    } catch {
      return null
    }
  }

  return null
}

function jsonValue(value) {
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)
    } catch {
      return null
    }
  }

  return value
}

function callArgs(value) {
  const parsed = jsonValue(value)

  return parsed && typeof parsed === 'object' ? parsed : null
}

/** Hermes keeps the outer id on a single deferred local call (live and in persisted tool rows). */
export function unwrapCalls(id, name, args) {
  const parsed = callArgs(args)

  if (name === 'tool_call') {
    const entries = jsonValue(parsed?.calls ?? (parsed?.name ? [parsed] : null))
    const calls = Array.isArray(entries) ? entries : entries && typeof entries === 'object' ? [entries] : []

    if (calls.length) {
      return calls.map((call, index) => ({
        id: id == null || calls.length === 1 ? id : `${id}:${index}`,
        name: String(call?.name ?? 'tool').trim(),
        args: callArgs(call?.arguments)
      }))
    }
  }

  return [{ id, name: String(name ?? 'tool'), args: parsed }]
}
