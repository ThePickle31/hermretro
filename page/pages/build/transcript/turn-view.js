// One turn of the conversation.
import { Button, Codicon, jsx, jsxs, memo, useCallback, useRef } from '#sdk'
import { attachmentKey } from '#pages/build/chat/attachments.js'
import { AttachmentChip } from '#pages/build/composer/attachment-chip.js'
import { effortLabel, modelName } from '#pages/build/composer/model-names.js'
import { InlinePlayer } from '#pages/build/player/inline-player.js'
import { PlayCard, playsBuild } from '#pages/build/player/play-card.js'
import { AGENT } from '#app/ids.js'
import { spanWords } from '#shared/ui/time.js'
import { playableSha } from '#app/player/stage.js'
import { BuildCard, buildCardArt, NextSteps } from './build-card.js'
import { AgentText, replyAssets } from './reply.js'
import { turnParts } from './turns.js'
import { Worked } from './worked.js'

function TurnView({ turn, live, turnStartedAt = null, previousModel = null, chatBusy, latestBuild, build = null, game, root, ctx, stored, playerOpen, onPlay, onClosePlayer, onOpenAsset, onSend, isLast }) {
  const parts = turnParts(turn, root)
  const user = turn.user
  const end = parts.end
  const agentAt = end?.at ?? null
  const hasAgent = live || turn.items.length > 0
  const startedAt = user?.at ?? end?.startedAt ?? null
  const showWorked = parts.entries.length > 0 || (live && !parts.intro.length)
  const report = parts.report
  // A finished turn that built the game, or reported what it did, ends in its build card.
  const carded = !live && (build || report)
  const art = carded ? buildCardArt(parts, root) : null
  // The viewer steps through work, reply, and build report images in the turn.
  const viewerAssets = [...parts.assets]

  for (const asset of [...replyAssets([...parts.intro, ...parts.outro], root), ...(art?.changes.map(change => change.image) ?? [])]) {
    if (asset && !viewerAssets.some(entry => entry.path === asset.path && entry.version === asset.version)) {
      viewerAssets.push(asset)
    }
  }

  // The viewer quotes the message that asked for each picture.
  if (user?.text) {
    viewerAssets.forEach((asset, position) => {
      viewerAssets[position] = { ...asset, ask: user.text }
    })
  }

  const viewerRef = useRef(null)

  viewerRef.current = { assets: viewerAssets, ask: user?.text }

  // Stable, so the memoised replies do not re-render their markdown on every turn update.
  const openAsset = useCallback((asset, opener) => {
    const { assets, ask } = viewerRef.current
    const index = assets.findIndex(entry => entry.path === asset.path && entry.version === asset.version)

    // Before/After can open a particular point in time that has no other thumbnail in the turn.
    if (index === -1) {
      onOpenAsset([...assets, { ...asset, ask }], assets.length, opener)
    } else {
      onOpenAsset(assets, index, opener)
    }
  }, [onOpenAsset])
  const playable = Boolean(game && game.webExport && playableSha(game))
  const frame = [...parts.assets].reverse().find(asset => asset.kind === 'Playtest frame') ?? null

  // The newest build plays in a frame under its line; while the agent works, only its line says so.
  let play = null
  let playLabel = null

  if (latestBuild && game) {
    if (chatBusy) {
      playLabel = carded ? jsx('span', { className: 'cs-faint cs-small', children: `Playable again when ${AGENT} finishes` }) : null
    } else if (!playable) {
      play = jsx(PlayCard, { frame, game, state: 'unplayable' })
    } else if (playerOpen) {
      play = jsx(InlinePlayer, { build, ctx, game, note: parts.note, onClose: onClosePlayer, report, stored }, `player:${game.id}`)
    } else {
      play = jsx(PlayCard, { build: playsBuild(game, build) ? build.n : null, frame, game, note: parts.note, onPlay, state: 'ready' })
    }
  } else if (build?.state === 'built' && !live) {
    playLabel = jsx('span', { className: 'cs-faint cs-small', children: 'Earlier build' })
  }

  const took = startedAt && end?.at ? spanWords(end.at - startedAt) : null
  const card = carded
    ? jsx(BuildCard, {
        art,
        at: agentAt,
        build,
        chatBusy,
        isLast,
        onOpenAsset: openAsset,
        onSend,
        parts: { ...parts, startedAt: startedAt ?? null, endedAt: end?.at ?? null },
        playLabel,
        report,
        took
      })
    : null
  const outro = parts.outro.map((item, index) => jsx(AgentText, { item, onOpenAsset: openAsset, root }, `o${index}`))

  return jsxs('section', {
    className: 'cs-b-turn',
    'data-live': live ? 'true' : undefined,
    'data-turn': turn.key,
    children: [
      user
        ? jsxs('div', {
            className: 'cs-b-user',
            children: [
              user.attachments?.length
                ? jsx('div', { className: 'cs-b-chips', children: user.attachments.map(item => jsx(AttachmentChip, { item }, attachmentKey(item))) })
                : null,
              jsx('span', { children: user.text })
            ]
          })
        : null,
      hasAgent
        ? jsxs('div', {
            className: 'cs-b-her',
            children: [
              // No name over the reply (it is the agent's thread); a line only where the model changed.
              user?.model && previousModel && (user.model !== previousModel.model || (user.effort ?? '') !== (previousModel.effort ?? ''))
                ? jsx('div', { className: 'cs-b-who', children: `${modelName(user.model).name}${user.effort ? ` · ${effortLabel(user.effort)}` : ''}` })
                : null,
              ...parts.intro.map((item, index) => jsx(AgentText, { item, onOpenAsset: openAsset, root }, `i${index}`)),
              showWorked
                ? jsx(Worked, { endedAt: end?.at ?? null, live, onOpenAsset: openAsset, parts, root, startedAt: live ? (turnStartedAt ?? startedAt ?? Date.now()) : startedAt, status: end?.status ?? null }, 'worked')
                : null,
              // With a report the card says it all and the reply is a line after it; without one the reply
              // is the words, and the card (a build) follows them.
              // Questions and approvals are asked in the message box, not here.
              ...(report ? [card, carded ? play : null, ...outro] : [...outro, card, carded ? play : null]),
              ...parts.errors.map((item, index) =>
                jsxs(
                  'div',
                  {
                    className: 'cs-b-card bad',
                    children: [
                      jsxs('div', { className: 'cs-row', children: [jsx(Codicon, { name: 'error', size: 14 }), jsx('b', { children: 'Something went wrong' })] }),
                      jsx('p', { className: 'cs-small', children: item.text }),
                      isLast && !chatBusy && item.resend
                        ? jsx('div', { className: 'cs-row', children: jsx(Button, { onClick: () => onSend(item.resend.text, item.resend.shown, item.resend.attachments ?? []), size: 'sm', variant: 'outline', children: 'Try again' }) })
                        : null
                    ]
                  },
                  `e${index}`
                )
              ),
              parts.buildFailed && !live && !carded
                ? jsxs('div', {
                    className: 'cs-b-card bad',
                    children: [
                      jsxs('div', { className: 'cs-row', children: [jsx(Codicon, { name: 'error', size: 14 }), jsx('b', { children: 'The build failed' })] }),
                      jsx('p', { className: 'cs-small', children: parts.buildFailed }),
                      isLast && !chatBusy
                        ? jsx('div', { className: 'cs-row', children: jsx(Button, { onClick: () => onSend('The build failed. Please fix it and build again.'), size: 'sm', variant: 'outline', children: `Ask ${AGENT} to fix it` }) })
                        : null
                    ]
                  })
                : null,
              end?.status === 'interrupted' && isLast && !chatBusy
                ? jsxs('div', {
                    className: 'cs-b-stopped',
                    children: [
                      jsx('span', { children: 'You stopped it here. Nothing is lost, and the last build still plays.' }),
                      jsx(Button, { onClick: () => onSend('Please carry on where you left off.'), size: 'sm', variant: 'outline', children: 'Carry on' })
                    ]
                  })
                : null,
              carded ? null : play,
              isLast && !chatBusy && !live ? jsx(NextSteps, { stored, suggestions: report?.suggestions }) : null
            ]
          })
        : null
    ]
  })
}

const sameItems = (a, b) => a.length === b.length && a.every((item, index) => item === b[index])

export const TurnMemo = memo(
  TurnView,
  (previous, next) =>
    sameItems(previous.turn.items, next.turn.items) &&
    previous.turn.user === next.turn.user &&
    previous.live === next.live &&
    previous.turnStartedAt === next.turnStartedAt &&
    previous.previousModel?.model === next.previousModel?.model &&
    previous.previousModel?.effort === next.previousModel?.effort &&
    previous.chatBusy === next.chatBusy &&
    previous.latestBuild === next.latestBuild &&
    previous.build === next.build &&
    previous.isLast === next.isLast &&
    previous.playerOpen === next.playerOpen &&
    previous.root === next.root &&
    previous.stored === next.stored &&
    (!next.latestBuild || previous.game === next.game) &&
    previous.onOpenAsset === next.onOpenAsset
)
