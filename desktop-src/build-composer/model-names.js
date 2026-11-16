// Model and effort names for display.
// Effort levels Hermes accepts (`hermes_constants.VALID_REASONING_EFFORTS`), in plain words.
export const EFFORTS = [
  ['none', 'Off', 'No extra thinking'],
  ['minimal', 'Minimal', 'Fastest. Fine for small tweaks'],
  ['low', 'Low', 'Quick edits: text, colours, timing'],
  ['medium', 'Medium', 'Most changes'],
  ['high', 'High', 'New mechanics, tricky bugs'],
  ['xhigh', 'X-high', 'Big features, whole levels'],
  ['max', 'Max', 'Slowest, uses the most of your plan']
]
export const effortLabel = value => EFFORTS.find(([key]) => key === value)?.[1] ?? (value === 'ultra' ? 'Ultra' : value ? value : 'Default')

/** A model id as people say it: `claude-opus-5-5[1m]` → "Claude Opus 5.5" (+ "1M"). */
export function modelName(id) {
  let raw = String(id ?? '').split('/').pop()
  const tags = []

  raw = raw.replace(/\[(\d+)m\]$/i, (_, size) => {
    tags.push(`${size}M`)

    return ''
  })
  raw = raw.replace(/-(\d+)k$/i, (_, size) => {
    tags.push(`${size}K`)

    return ''
  })
  raw = raw.replace(/-\d{8}$/, '')

  const words = []

  for (const part of raw.split('-').filter(Boolean)) {
    const last = words[words.length - 1]

    if (/^\d+$/.test(part) && last && /\d$/.test(last)) {
      words[words.length - 1] = `${last}.${part}`
    } else {
      words.push(part)
    }
  }

  const name = words
    .map(word => (/^gpt$/i.test(word) ? 'GPT' : /^[a-z]/.test(word) ? word[0].toUpperCase() + word.slice(1) : word))
    .join(' ')
    .replace(/^GPT (\d)/, 'GPT-$1')

  return { name: name || String(id ?? ''), tags }
}

export const providerMark = name => (String(name ?? '?').replace(/[^A-Za-z0-9]/g, '')[0] ?? '?').toUpperCase()
