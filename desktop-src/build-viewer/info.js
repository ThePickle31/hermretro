// What the asset viewer loads about a file.
import { useEffect, useState } from '../sdk.js'
import { assetEntry } from '../build-assets/cache.js'
import { callStudio } from '../core/backend.js'
import { RPC_ASSET_INFO } from '../core/rpc.js'

export const VIEWER_KIND = { cover: 'Game cover', sprite: 'Sprite', background: 'Background', ui: 'Interface', frame: 'Playtest frame', capture: 'Capture', image: 'Image' }

export function useAssetInfo(path, refresh) {
  const [info, setInfo] = useState(null)

  useEffect(() => {
    if (!path) {
      setInfo(null)

      return undefined
    }

    let live = true

    callStudio(RPC_ASSET_INFO, { path }, 20_000)
      .then(answer => live && setInfo(answer?.ok ? answer : null))
      .catch(() => live && setInfo(null))

    return () => {
      live = false
    }
  }, [path, refresh])

  return info
}

/** Images for several asset paths at once (a scene's background and its actors' sprites). */
export function useImages(paths, version) {
  const [images, setImages] = useState({})
  const key = paths.join('\n')

  useEffect(() => {
    let live = true

    setImages({})

    for (const path of paths) {
      void assetEntry(path, version).promise.then(answer => {
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
  }, [key, version])

  return images
}
