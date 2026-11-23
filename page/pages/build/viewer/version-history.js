// The selected asset version, its history strip and Restore.
import { host, jsx, jsxs, useCallback, useMemo, useState } from '#sdk'
import { forgetAsset, useAsset } from '#pages/build/assets/cache.js'
import { SheetFrame } from '#pages/build/assets/images.js'
import { callStudioOnly } from '#app/backend.js'
import { RPC_ASSET_RESTORE } from '#app/rpc.js'
import { timeOfDay } from '#shared/ui/time.js'

const LIVE = Symbol('live image')

export function useVersionHistory({ path, original, info, onRefresh, root }) {
  const scope = useMemo(() => ({}), [root, path, original])
  const [selection, setSelection] = useState({ scope, picked: null })
  const [restoring, setRestoring] = useState(false)

  if (selection.scope !== scope) {
    setSelection({ scope, picked: null })
  }

  const setPicked = useCallback(picked => {
    setSelection(current => current.scope === scope ? { scope, picked } : current)
  }, [scope])
  const showLive = useCallback(() => setPicked(LIVE), [setPicked])
  const picked = selection.scope === scope ? selection.picked : null
  const { state, asset: loaded } = useAsset(path, picked === LIVE ? null : picked ? `kept:${picked}` : original)
  const versions = info?.versions ?? []
  const currentId = versions.find(entry => entry.current)?.id ?? null
  const shownId = (picked === LIVE ? null : picked) ?? loaded?.versionId ?? null
  const shownEntry = versions.find(entry => entry.id === shownId) ?? null
  const shownNumber = shownEntry ? versions.indexOf(shownEntry) + 1 : null
  const older = picked !== LIVE && Boolean(shownEntry && currentId && shownEntry.id !== currentId)

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
      showLive()
      host.notify({ kind: 'success', message: `v${shownNumber} is back in the game. Build again to play it.` })
      onRefresh()
    } catch (error) {
      host.notify({ kind: 'error', message: error instanceof Error ? error.message : String(error) })
    } finally {
      setRestoring(false)
    }
  }

  return { currentId, loaded, older, restore, restoring, setPicked, showLive, shownEntry, shownId, shownNumber, state, versions }
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
