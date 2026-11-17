// Project files (art) loaded through the `asset` RPC, cached per version.
import { useEffect, useState } from '#sdk'
import { callStudioOnly } from '#app/backend.js'
import { RPC_ASSET } from '#app/rpc.js'

export const assetCache = new Map()
const ASSET_CACHE_LIMIT = 200
const ASSET_RETRY_MS = 15_000
const assetQueue = []
let assetsLoading = 0

function pumpAssets() {
  while (assetsLoading < 4 && assetQueue.length) {
    const job = assetQueue.shift()

    assetsLoading += 1
    job().finally(() => {
      assetsLoading -= 1
      pumpAssets()
    })
  }
}

/** One image from the backend, fetched once per path and version (a step that rewrote the file is a
 *  new version) and at most four at a time. */
export function assetEntry(path, version) {
  const key = `${path}#${version ?? ''}`
  let entry = assetCache.get(key)

  // A failed load is retried after a while (the file may appear, or the backend may have been restarted).
  if (entry?.done && !entry.value && Date.now() - entry.failedAt > ASSET_RETRY_MS) {
    assetCache.delete(key)
    entry = null
  }

  if (!entry) {
    entry = { done: false, value: null }
    entry.promise = new Promise(resolve => {
      assetQueue.push(async () => {
        try {
          // A reply's image asks for the version the file had when the reply was written (cover.png
          // made again later must not change an earlier reply).
          const at = typeof version === 'string' && version.startsWith('reply:') ? Number(version.slice(6)) || null : null
          // The viewer's version strip asks for one kept version by id.
          const kept = typeof version === 'string' && version.startsWith('kept:') ? version.slice(5) : null
          const answer = await callStudioOnly(RPC_ASSET, kept ? { path, version: kept } : at ? { path, at } : { path }, 20_000)

          entry.value = answer?.ok && typeof answer.dataUrl === 'string' ? answer : null
        } catch {
          entry.value = null
        }

        entry.done = true
        entry.failedAt = entry.value ? 0 : Date.now()
        resolve(entry.value)
      })
      pumpAssets()
    })
    assetCache.set(key, entry)

    while (assetCache.size > ASSET_CACHE_LIMIT) {
      assetCache.delete(assetCache.keys().next().value)
    }
  }

  return entry
}

export function useAsset(path, version) {
  const entry = path ? assetEntry(path, version) : null
  const [, rerender] = useState(0)

  useEffect(() => {
    if (!entry || entry.done) {
      return undefined
    }

    let live = true

    void entry.promise.then(() => live && rerender(value => value + 1))

    return () => {
      live = false
    }
  }, [entry])

  if (!entry) {
    return { state: 'none' }
  }

  return entry.done ? (entry.value ? { state: 'ok', asset: entry.value } : { state: 'none' }) : { state: 'loading' }
}
