// The selected asset version, its history strip and Restore.
import { host, jsx, jsxs, useEffect, useState } from '#sdk'
import { forgetAsset, useAsset } from '#pages/build/assets/cache.js'
import { SheetFrame } from '#pages/build/assets/images.js'
import { callStudioOnly } from '#app/backend.js'
import { RPC_ASSET_RESTORE } from '#app/rpc.js'
import { timeOfDay } from '#shared/ui/time.js'

export function useVersionHistory({ path, original, info, refresh, onRefresh, root }) {
  const [picked, setPicked] = useState(null)
  const [restoring, setRestoring] = useState(false)
  const { state, asset: loaded } = useAsset(path, picked ? `kept:${picked}` : original)
  const versions = info?.versions ?? []
  const currentId = versions.find(entry => entry.current)?.id ?? null
  const shownId = picked ?? loaded?.versionId ?? null
  const shownEntry = versions.find(entry => entry.id === shownId) ?? null
  const shownNumber = shownEntry ? versions.indexOf(shownEntry) + 1 : null
  const older = Boolean(shownEntry && currentId && shownEntry.id !== currentId)

  useEffect(() => setPicked(null), [path, original])

  // Once the new versions arrive after a change, show the one in the game.
  useEffect(() => {
    if (refresh && currentId) {
      setPicked(currentId)
    }
  }, [refresh, currentId])

  const restore = async () => {
    if (!shownEntry || restoring) {
      return
    }

    setRestoring(true)

    try {
      const answer = await callStudioOnly(RPC_ASSET_RESTORE, { path, root, version: shownEntry.id }, 20_000)

      if (!answer?.ok) {
        throw new Error(answer?.error ?? 'It could not be restored.')
      }

      forgetAsset(path, answer.path)
      host.notify({ kind: 'success', message: `v${shownNumber} is back in the game. Build again to play it.` })
      onRefresh()
    } catch (error) {
      host.notify({ kind: 'error', message: error instanceof Error ? error.message : String(error) })
    } finally {
      setRestoring(false)
    }
  }

  return { currentId, loaded, older, restore, restoring, setPicked, shownEntry, shownId, shownNumber, state, versions }
}

export function versionTime(entry) {
  return entry?.at ? timeOfDay(entry.at) : ''
}

/** A version's small picture in the strip. */
function VersionThumb({ path, entry, number, selected, onPick }) {
  const { state, asset: loaded } = useAsset(path, `kept:${entry.id}`)

  return jsxs('button', {
    'aria-label': `Version ${number}${entry.current ? ', in the game now' : ''}`,
    'aria-pressed': selected,
    className: `cs-v-ver${selected ? ' on' : ''}`,
    onClick: () => onPick(entry.id),
    title: `v${number} · ${versionTime(entry)}${entry.current ? ' · in the game now' : ''}`,
    type: 'button',
    children: [
      state === 'ok' ? jsx(SheetFrame, { loaded }) : jsx('span', { className: 'cs-v-ver-ph' }),
      jsx('b', { children: `v${number}` }),
      entry.current ? jsx('i', { 'aria-hidden': true, className: 'cs-v-now' }) : null
    ]
  })
}

export function VersionHistory({ path, version, working }) {
  const { versions, shownId, setPicked } = version

  return versions.length
    ? jsxs('div', {
        className: 'cs-v-vers',
        children: [
          jsx('span', { className: 'cs-eyebrow', children: 'Versions' }),
          ...versions.map((entry, position) => jsx(VersionThumb, { entry, number: position + 1, onPick: setPicked, path, selected: entry.id === shownId }, entry.id)),
          working ? jsxs('span', { className: 'cs-v-ver pending', title: 'Being made now', children: [jsx('span', { className: 'cs-b-spin' }), jsx('b', { children: `v${versions.length + 1}` })] }) : null
        ]
      })
    : null
}
