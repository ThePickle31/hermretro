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

/** Hermes's deferred-tool wrapper (`tool_call {calls: [...]}`) as the calls it made. */
export function unwrapCalls(id, name, args) {
  let parsed = args

  if (typeof parsed === 'string') {
    try {
      parsed = JSON.parse(parsed)
    } catch {
      parsed = null
    }
  }

  if (name === 'tool_call' && Array.isArray(parsed?.calls) && parsed.calls.length) {
    return parsed.calls.map((call, index) => {
      let inner = call?.arguments ?? null

      if (typeof inner === 'string') {
        try {
          inner = JSON.parse(inner)
        } catch {
          inner = null
        }
      }

      return { id: id == null ? null : `${id}:${index}`, name: String(call?.name ?? 'tool'), args: inner && typeof inner === 'object' ? inner : null }
    })
  }

  return [{ id, name: String(name ?? 'tool'), args: parsed && typeof parsed === 'object' ? parsed : null }]
}
