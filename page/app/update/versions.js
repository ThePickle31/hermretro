// hermretro's versions (`X.Y.Z`) and the releases between two of them (the releases RPC, newest first). No React.

function parts(version) {
  const match = /^v?(\d+)\.(\d+)\.(\d+)$/.exec(String(version ?? '').trim())

  return match ? match.slice(1).map(Number) : null
}

/** Whether `a` is a newer version than `b`; false when either is not `X.Y.Z`. */
export function isNewer(a, b) {
  const [x, y] = [parts(a), parts(b)]

  if (!x || !y) {
    return false
  }

  const index = x.findIndex((n, i) => n !== y[i])

  return index !== -1 && x[index] > y[index]
}

/** The releases newer than `from` and no newer than `to` (`to` null: every newer one), newest first. */
export function releasesBetween(releases, from, to = null) {
  return (Array.isArray(releases) ? releases : []).filter(release => isNewer(release.version, from) && (!to || !isNewer(release.version, to)))
}
