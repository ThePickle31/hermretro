// Sizes and paths, shortened for display.
export function formatBytes(bytes, approx = false) {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return ''
  }

  const mb = bytes / 1e6
  const text = mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : mb >= 100 ? `${Math.round(mb)} MB` : `${mb.toFixed(1)} MB`

  return approx ? `≈ ${text}` : text
}

/** The last few folders of a long path, so the end (the part that says where) stays readable. */
export function shortPath(path, keep = 4) {
  if (!path) {
    return null
  }

  const parts = String(path).split(/[\\/]/).filter(Boolean)

  return parts.length > keep ? `…/${parts.slice(-keep).join('/')}` : path
}
