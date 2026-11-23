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

/** A ROM result starts with its unique reference, even in Hermes's bounded event or spill preview. */
export function toolBuildRef(value, parsed) {
  if (typeof parsed?.buildRef === 'string' && parsed.buildRef) {
    return parsed.buildRef
  }

  const output = parsed?.truncated === true ? parsed.output : value
  const body = typeof output === 'string' && output.startsWith('<persisted-output>\n')
    ? output.split(/^Preview \(first [0-9]+ chars\):\n/m, 2)[1]
    : parsed?.truncated === true ? output : null

  return /^\{\s*"buildRef"\s*:\s*"([0-9a-f]{32})"\s*[,}]/.exec(body ?? '')?.[1] ?? null
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
