// What the asset viewer loads about a file.
import { useContext, useEffect, useState } from '#sdk'
import { AssetGame, assetEntry, usePutBack } from '#pages/build/assets/cache.js'
import { callStudioOnly } from '#app/backend.js'
import { RPC_ASSET_INFO } from '#app/rpc.js'

export const VIEWER_KIND = { cover: 'Game cover', sprite: 'Sprite', background: 'Background', ui: 'Interface', frame: 'Playtest frame', capture: 'Capture', image: 'Image' }

export function useAssetInfo(path, refresh, edit) {
  const root = useContext(AssetGame)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!path) {
      setResult(null)

      return undefined
    }

    let live = true

    callStudioOnly(RPC_ASSET_INFO, { path, root }, 20_000)
      .then(answer => live && setResult(answer?.ok ? { path, root, answer } : null))
      .catch(() => live && setResult(null))

    return () => {
      live = false
    }
  }, [path, root, refresh, edit])

  return result && result.path === path && result.root === root ? result.answer : null
}

/** Images for several asset paths at once (a scene's background and its actors' sprites). */
export function useImages(paths, version) {
  const root = useContext(AssetGame)
  const putBack = usePutBack()
  const [images, setImages] = useState({})
  const key = paths.join('\n')

  useEffect(() => {
    let live = true

    setImages({})

    for (const path of paths) {
      void assetEntry(path, version, root).promise.then(answer => {
        if (!live || !answer?.dataUrl) {
          return
        }

        const element = document.createElement('img')

        element.onload = () => live && setImages(current => ({ ...current, [path]: element }))
        element.src = answer.dataUrl
      })
    }

    return () => {
      live = false
    }
  }, [key, version, root, putBack])

  return images
}
