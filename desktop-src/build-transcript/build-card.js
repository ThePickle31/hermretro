// The build card: what changed, what was tested, next steps.
import { Button, Codicon, host, jsx, jsxs, useState } from '../sdk.js'
import { assetCache, useAsset } from '../build-assets/cache.js'
import { AssetThumb, SheetFrame } from '../build-assets/images.js'
import { injectBuildDraft } from '../build-chat/store.js'
import { callStudioOnly, describeRequestError } from '../core/backend.js'
import { AGENT } from '../core/ids.js'
import { baseName, isAbsolute, joinPath } from '../core/paths.js'
import { RPC_ASSET_RESTORE } from '../core/rpc.js'
import { timeOfDay } from '../core/time.js'
import { assetKind } from './step-words.js'
import { madeAssets } from './turns.js'

const CHANGE_MARK = { added: '+', changed: '~', removed: '\u2212' }

/** Forget the cached look of a file (it was put back), so every thumbnail fetches it again. */
function dropAsset(path) {
  for (const key of [...assetCache.keys()]) {
    if (key.startsWith(`${path}#`)) {
      assetCache.delete(key)
    }
  }
}

/** An edited picture as it was before the turn and as it is after, with Keep and Undo (Undo puts the
 *  earlier version back through the kept versions; the one there now is kept too, so it can be redone).
 *  Shows nothing when the file is new this turn (nothing earlier was kept). */
function BeforeAfter({ path, from, to, actions, onOpen, onSend }) {
  const before = useAsset(path, `reply:${from}`)
  const after = useAsset(path, to ? `reply:${to}` : null)
  const [state, setState] = useState(null)

  if (before.state !== 'ok' || !before.asset.earlier || after.state !== 'ok') {
    return null
  }

  const name = after.asset.sprite?.name || after.asset.name
  const undo = async () => {
    setState('busy')

    try {
      const answer = await callStudioOnly(RPC_ASSET_RESTORE, { path, version: before.asset.versionId }, 20_000)

      if (!answer?.ok) {
        throw new Error(answer?.error ?? 'It could not be put back.')
      }

      dropAsset(path)
      setState('undone')
    } catch (error) {
      setState(null)
      host.notify({ kind: 'error', message: `Could not undo ${name}: ${describeRequestError(error).message}` })
    }
  }
  const side = (loaded, label, now) =>
    jsxs('button', {
      'aria-label': `Look closer at ${label.toLowerCase()} version of ${name}`,
      className: now ? 'cs-b-ba-side now' : 'cs-b-ba-side',
      onClick: () => onOpen?.({ path, version: now ? (to ? `reply:${to}` : null) : `reply:${from}`, kind: assetKind(path), step: label }),
      type: 'button',
      children: [jsx('span', { className: 'cs-b-ba-img', children: jsx(SheetFrame, { loaded }) }), jsx('span', { className: 'cs-b-ba-cap', children: label })]
    })

  return jsxs('div', {
    className: 'cs-b-ba',
    children: [
      jsxs('div', {
        className: 'cs-b-ba-pair',
        children: [side(before.asset, 'Before', false), jsx('span', { 'aria-hidden': true, className: 'cs-b-ba-arrow', children: '\u2192' }), side(after.asset, 'After', true)]
      }),
      actions && state !== 'kept'
        ? jsxs('div', {
            className: 'cs-row cs-b-ba-acts',
            children:
              state === 'undone'
                ? [
                    jsx('span', { className: 'cs-small cs-grow', children: `Put back the earlier ${name}. Rebuild to see it in the game.` }, 't'),
                    jsx(Button, { onClick: () => onSend?.(`I put back the earlier version of ${baseName(path)}. Please build the game again.`), size: 'sm', children: 'Rebuild' }, 'r')
                  ]
                : [
                    jsx('span', { className: 'cs-faint cs-small cs-grow', children: name }, 't'),
                    jsx(Button, { disabled: state === 'busy', onClick: () => setState('kept'), size: 'sm', variant: 'outline', children: 'Keep' }, 'k'),
                    jsx(Button, { disabled: state === 'busy', onClick: () => void undo(), size: 'sm', variant: 'ghost', children: state === 'busy' ? 'Undoing…' : 'Undo' }, 'u')
                  ]
          })
        : null
    ]
  })
}

/** What changed, from the report (else the pictures the turn made): + added, ~ changed, − removed. */
function ChangeList({ changes, root, onOpen }) {
  return jsx('ul', {
    className: 'cs-b-bc-changes',
    children: changes.map((change, index) => {
      const path = change.asset ? (isAbsolute(change.asset) ? change.asset.replace(/^file:\/\//, '') : joinPath(root, change.asset)) : null

      return jsxs(
        'li',
        {
          'data-kind': change.kind,
          children: [
            jsx('span', { 'aria-hidden': true, className: 'cs-b-bc-mark', children: CHANGE_MARK[change.kind] ?? '~' }),
            path ? jsx(AssetThumb, { asset: { path, version: 'card', kind: assetKind(path), step: change.text }, onOpen, size: 'xs' }) : null,
            jsx('span', { children: change.text })
          ]
        },
        index
      )
    })
  })
}

export function BuildCard({ build, parts, report, root, took, at, live, isLast, chatBusy, onOpenAsset, onSend, play, playLabel }) {
  const [details, setDetails] = useState(false)
  const failed = build?.state === 'failed'
  const made = madeAssets(parts, root).filter(asset => asset.kind !== 'Image' || /cover\.png$/i.test(asset.path))
  const changes = report?.changes?.length ? report.changes : made.slice(0, 6).map(asset => ({ kind: 'changed', text: baseName(asset.path), asset: asset.path, made: true }))
  const edited = [...new Set([...(report?.changes ?? []).filter(change => change.kind === 'changed' && change.asset).map(change => (isAbsolute(change.asset) ? change.asset : joinPath(root, change.asset))), ...made.map(asset => asset.path)])]
    .filter(Boolean)
    .slice(0, 2)
  const tested = report?.tested ?? []
  const untested = report?.untested ?? []
  const notes = report?.notes ?? []
  const title = report?.title ?? (failed ? 'The build didn\u2019t finish' : build?.title ?? 'Done')
  const summary = report?.summary ?? (failed ? parts.buildFailed : null)
  const hasFoot = tested.length || untested.length || notes.length || failed

  return jsxs('div', {
    className: `cs-b-bc${failed ? ' bad' : ''}${live ? ' live' : ''}`,
    'data-build': build?.n ?? undefined,
    children: [
      jsxs('div', {
        className: 'cs-b-bc-head',
        children: [
          build ? jsx('span', { className: `cs-b-bn${failed ? ' bad' : live ? ' live' : ''}`, children: `#${build.n}` }) : null,
          jsx('b', { className: 'cs-b-bc-title', children: title }),
          jsx('span', { className: 'cs-faint cs-b-bc-meta', children: [took, at ? timeOfDay(at) : null].filter(Boolean).join(' · ') }),
          jsx('span', { className: 'cs-grow' }),
          playLabel
        ]
      }),
      summary ? jsx('p', { className: 'cs-b-bc-sum', children: summary }) : null,
      ...edited.map(path => jsx(BeforeAfter, { actions: isLast && !chatBusy, from: parts.startedAt, onOpen: onOpenAsset, onSend, path, to: parts.endedAt }, `ba:${path}`)),
      changes.length ? jsx(ChangeList, { changes, onOpen: onOpenAsset, root }) : null,
      play,
      hasFoot
        ? jsxs('div', {
            className: 'cs-b-bc-foot',
            children: [
              tested.length ? jsxs('span', { children: [jsx('span', { className: 'cs-b-ok', children: '\u2713' }), ` ${tested.length} play-tested`] }) : null,
              untested.length ? jsx('span', { className: 'cs-faint', children: `\u25CB ${untested.length} not tested` }) : null,
              notes.length ? jsx('span', { className: 'cs-faint', children: `\u26A0 ${notes.length} ${notes.length === 1 ? 'note' : 'notes'}` }) : null,
              failed && isLast && !chatBusy ? jsx(Button, { onClick: () => onSend?.('The build failed. Please fix it and build again.'), size: 'sm', children: `Ask ${AGENT} to fix it` }) : null,
              jsx('span', { className: 'cs-grow' }),
              jsxs('button', {
                'aria-expanded': details,
                className: 'cs-b-link',
                onClick: () => setDetails(!details),
                type: 'button',
                children: [failed && !tested.length ? 'What went wrong' : 'Details', jsx(Codicon, { name: details ? 'chevron-down' : 'chevron-right', size: 11 })]
              })
            ]
          })
        : null,
      details
        ? jsxs('div', {
            className: 'cs-b-bc-details',
            children: [
              tested.length ? jsxs('div', { children: [jsx('span', { className: 'cs-eyebrow', children: 'Play-tested' }), ...tested.map((line, index) => jsxs('p', { children: [jsx('span', { className: 'cs-b-ok', children: '\u2713 ' }), line] }, index))] }) : null,
              untested.length ? jsxs('div', { children: [jsx('span', { className: 'cs-eyebrow', children: 'Not tested' }), ...untested.map((line, index) => jsx('p', { className: 'cs-faint', children: `\u25CB ${line}` }, index))] }) : null,
              notes.length ? jsxs('div', { children: [jsx('span', { className: 'cs-eyebrow', children: 'You might notice' }), ...notes.map((line, index) => jsx('p', { children: line }, index))] }) : null,
              failed && parts.buildFailed ? jsxs('div', { children: [jsx('span', { className: 'cs-eyebrow', children: 'What went wrong' }), jsx('pre', { className: 'cs-b-cmd', children: parts.buildFailed })] }) : null
            ]
          })
        : null
    ]
  })
}

/** Next steps the reply suggested: each puts its words in the message box (never sends them). */
export function NextSteps({ stored, suggestions }) {
  if (!stored || !suggestions?.length) {
    return null
  }

  return jsx('div', {
    className: 'cs-b-next-steps',
    children: suggestions.map(text =>
      jsxs('button', { className: 'cs-b-sugg-chip', onClick: () => injectBuildDraft(stored, text), type: 'button', children: [jsx(Codicon, { name: 'arrow-small-right', size: 12 }), text] }, text)
    )
  })
}
