// Sizes and paths, shortened for display.

/** A size in bytes as the page shows it: the one bytes formatter every page uses.
 *  Default: decimal GB or MB (`2.4 GB`, `551 MB`, `18.1 MB`). `unit: 'MB'`: whole megabytes with the locale's
 *  separators (`2,400 MB`; missing counts as 0). `unit: 'KB'`: whole KiB, at least 1 (`256 KB`, a ROM's size).
 *  `approx` puts `≈ ` in front. Anything not a size, or negative, is ''. */
export function formatBytes(bytes, { approx = false, unit = null } = {}) {
  if (unit === 'MB') {
    bytes = bytes || 0
  }

  if (!Number.isFinite(bytes) || bytes < 0) {
    return ''
  }

  const mb = bytes / 1e6
  const text =
    unit === 'MB'
      ? `${Math.round(mb).toLocaleString()} MB`
      : unit === 'KB'
        ? `${Math.max(1, Math.round(bytes / 1024))} KB`
        : mb >= 1000
          ? `${(mb / 1000).toFixed(1)} GB`
          : mb >= 100
            ? `${Math.round(mb)} MB`
            : `${mb.toFixed(1)} MB`

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
