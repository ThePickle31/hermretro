// A build in the conversation: one quiet line (its number, title, time), what changed under it, what was tested.
import { Button, Codicon, host, jsx, jsxs, useContext, useState } from '#sdk'
import { AssetGame, forgetAsset, useAssetPreview } from '#pages/build/assets/cache.js'
import { AssetThumb, SheetFrame } from '#pages/build/assets/images.js'
import { reportLines } from '#pages/build/chat/report.js'
import { injectBuildDraft } from '#pages/build/chat/store.js'
import { callStudioOnly, describeRequestError } from '#app/backend.js'
import { AGENT } from '#app/ids.js'
import { baseName, isAbsolute, joinPath } from '#app/paths.js'
import { RPC_ASSET_RESTORE } from '#app/rpc.js'
import { timeOfDay } from '#shared/ui/time.js'
import { assetKind } from './step-words.js'
import { madeAssets } from './turns.js'

const CHANGE_MARK = { added: '+', changed: '~', removed: '\u2212' }

function changeImage(change, root, version) {
  const raw = change.asset?.replace(/^file:\/\//, '')
  const path = raw && (isAbsolute(raw) ? raw : joinPath(root, raw))

  return path ? { path, version, kind: assetKind(path), step: change.text } : null
}

export function buildCardArt(parts, root) {
  const made = madeAssets(parts, root).filter(asset => asset.kind !== 'Image' || /cover\.png$/i.test(asset.path))
  const reported = parts.report?.changes
  const version = reported?.length && parts.reportAt ? `reply:${parts.reportAt}` : 'card'
  const rows = reported?.length ? reported : made.slice(0, 6).map(asset => ({ kind: 'changed', text: baseName(asset.path), asset: asset.path }))
  const changes = rows.map(change => ({ ...change, image: changeImage(change, root, version) }))
  const edited = [...new Set([
    ...changes.filter(change => change.kind === 'changed' && change.image).map(change => change.image.path),
    ...made.map(asset => asset.path)
  ])].slice(0, 2)

  const primary = reported?.length
    ? changes.find(change => change.kind !== 'removed' && /\.(png|gif|jpe?g|webp)$/i.test(change.image?.path ?? ''))?.image.path
    : null

  return { changes, edited, primary: primary ?? parts.assets.find(asset => !asset.looked && asset.kind !== 'Playtest frame')?.path ?? null }
}

/** An edited picture as it was before the turn and as it is after, with Keep and Undo (Undo puts the
 *  earlier version back through the kept versions; the one there now is kept too, so it can be redone).
 *  A new image shows its current version. */
function BeforeAfter({ path, from, to, actions, onOpen, onSend }) {
  const beforeVersion = from ? `reply:${from}` : null
  const afterVersion = to ? `reply:${to}` : null
  const before = useAssetPreview(from ? path : null, beforeVersion)
  const after = useAssetPreview(path, afterVersion)
  const root = useContext(AssetGame)
  const [state, setState] = useState(null)

  if (after.state !== 'ok') {
    return null
  }

  const compare = before.state === 'ok' && before.asset.earlier
  const name = after.asset.sprite?.name || after.asset.name
  const undo = async () => {
    setState('busy')

    try {
      const answer = await callStudioOnly(RPC_ASSET_RESTORE, { path, root, version: before.asset.versionId }, 20_000)

      if (!answer?.ok) {
        throw new Error(answer?.error ?? 'It could not be put back.')
      }

      forgetAsset(path, answer.path)
      setState('undone')
    } catch (error) {
      setState(null)
      host.notify({ kind: 'error', message: `Could not undo ${name}: ${describeRequestError(error).message}` })
    }
  }
  const side = (loaded, label, now) =>
    jsxs('button', {
      'aria-label': compare ? `Look closer at ${label.toLowerCase()} version of ${name}` : `Look closer at ${name}`,
      className: now ? 'cs-b-ba-side now' : 'cs-b-ba-side',
      onClick: event => onOpen?.({ path, version: now ? afterVersion : beforeVersion, kind: assetKind(path), step: label }, event.currentTarget),
      type: 'button',
      children: [jsx('span', { className: 'cs-b-ba-img', children: jsx(SheetFrame, { loaded }) }), jsx('span', { className: 'cs-b-ba-cap', children: label })]
    })

  return jsxs('div', {
    className: 'cs-b-ba',
    children: [
      jsxs('div', {
        className: 'cs-b-ba-pair',
        children: [
          compare ? side(before.asset, 'Before', false) : null,
          compare ? jsx('span', { 'aria-hidden': true, className: 'cs-b-ba-arrow', children: '\u2192' }) : null,
          side(after.asset, compare ? 'After' : name, true)
        ]
      }),
      compare && actions && state !== 'kept'
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
function ChangeList({ changes, onOpen }) {
  return jsx('ul', {
    className: 'cs-b-bc-changes',
    children: changes.map((change, index) => jsxs(
      'li',
      {
        'data-kind': change.kind,
        children: [
          jsx('span', { 'aria-hidden': true, className: 'cs-b-bc-mark', children: CHANGE_MARK[change.kind] ?? '~' }),
          change.image ? jsx(AssetThumb, { asset: change.image, onOpen, size: 'xs' }) : null,
          jsx('span', { children: change.text })
        ]
      },
      index
    ))
  })
}

export function BuildCard({ art, primary, replay, play, build, parts, report, took, at, live, isLast, chatBusy, onOpenAsset, onSend, playLabel }) {
  const [details, setDetails] = useState(false)
  const failed = build?.state === 'failed'
  const { changes, edited } = art
  const { tested, failed: failedChecks, untested } = reportLines(report)
  const notes = report?.notes ?? []
  const difficulty = report?.difficulty
  const unfinished = parts.unfinished
  const title = report?.title ?? (failed ? 'The build didn\u2019t finish' : build?.title ?? (primary ? baseName(primary) : 'Done'))
  const summary = (failed && parts.buildFailed) || report?.summary
  const extraArt = edited.filter(path => path !== primary)
  const hasFoot = changes.length || extraArt.length || tested.length || failedChecks.length || untested.length || notes.length || difficulty || unfinished || failed
  const compareArt = path => jsx(BeforeAfter, {
    actions: isLast && !chatBusy,
    from: parts.startedAt,
    onOpen: onOpenAsset,
    onSend,
    path,
    to: parts.endedAt
  }, path)

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
          build?.state === 'unknown' ? jsx('span', { className: 'cs-faint cs-small', children: 'Outcome unknown' }) : null,
          unfinished ? jsx('span', { className: 'cs-b-bc-unfinished', children: 'Unfinished' }) : null,
          playLabel
        ]
      }),
      summary ? jsx('p', { className: 'cs-b-bc-sum', children: summary }) : null,
      primary ? compareArt(primary) : replay,
      play,
      hasFoot
        ? jsxs('div', {
            className: 'cs-b-bc-foot',
            children: [
              tested.length ? jsxs('span', { children: [jsx('span', { className: 'cs-b-ok', children: '\u2713' }), ` ${tested.length} play-tested`] }) : null,
              failedChecks.length ? jsxs('span', { children: [jsx('span', { className: 'cs-b-bad', children: '\u2717' }), ` ${failedChecks.length} failed`] }) : null,
              untested.length ? jsx('span', { className: 'cs-faint', children: `\u25CB ${untested.length} not tested` }) : null,
              notes.length ? jsx('span', { className: 'cs-faint', children: `\u26A0 ${notes.length} ${notes.length === 1 ? 'note' : 'notes'}` }) : null,
              failed && isLast && !chatBusy ? jsx(Button, { onClick: () => onSend?.('The build failed. Please fix it and build again.'), size: 'sm', variant: 'outline', children: `Ask ${AGENT} to fix it` }) : null,
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
              unfinished
                ? jsxs('div', {
                    className: 'cs-b-bc-unfinished-why',
                    children: [
                      jsx('span', { className: 'cs-eyebrow', children: 'Unfinished' }),
                      ...[unfinished.reason, unfinished.notCurrent, ...unfinished.notVerified].filter(Boolean).map((line, index) => jsx('p', { children: line }, index))
                    ]
                  })
                : null,
              changes.length ? jsx(ChangeList, { changes, onOpen: onOpenAsset }) : null,
              ...extraArt.map(compareArt),
              tested.length ? jsxs('div', { children: [jsx('span', { className: 'cs-eyebrow', children: 'Play-tested' }), ...tested.map((line, index) => jsxs('p', { children: [jsx('span', { className: 'cs-b-ok', children: '\u2713 ' }), line] }, index))] }) : null,
              failedChecks.length ? jsxs('div', { children: [jsx('span', { className: 'cs-eyebrow', children: 'Failed' }), ...failedChecks.map((line, index) => jsxs('p', { children: [jsx('span', { className: 'cs-b-bad', children: '\u2717 ' }), line] }, index))] }) : null,
              untested.length ? jsxs('div', { children: [jsx('span', { className: 'cs-eyebrow', children: 'Not tested' }), ...untested.map((line, index) => jsx('p', { className: 'cs-faint', children: `\u25CB ${line}` }, index))] }) : null,
              difficulty ? jsxs('div', { children: [jsx('span', { className: 'cs-eyebrow', children: 'Difficulty' }), jsx('p', { children: difficulty })] }) : null,
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
