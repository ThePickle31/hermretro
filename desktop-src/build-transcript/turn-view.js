// One turn of the conversation.
import { Button, Codicon, jsx, jsxs, memo, useCallback, useRef } from '../sdk.js'
import { attachmentKey } from '../build-chat/attachments.js'
import { AttachmentChip } from '../build-composer/attachment-chip.js'
import { effortLabel, modelName } from '../build-composer/model-names.js'
import { InlinePlayer } from '../build-player/inline-player.js'
import { PlayCard } from '../build-player/play-card.js'
import { AGENT } from '../core/ids.js'
import { spanWords, timeOfDay } from '../core/time.js'
import { playableSha } from '../player/stage.js'
import { BuildCard, NextSteps } from './build-card.js'
import { BuildPromptCard } from './questions.js'
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
  // The viewer steps through the turn's images: the steps' first, then the ones its replies delivered.
  const viewerAssets = [...parts.assets]

  for (const asset of replyAssets([...parts.intro, ...parts.outro], root)) {
    if (!viewerAssets.some(entry => entry.path === asset.path && entry.version === asset.version)) {
      viewerAssets.push(asset)
    }
  }

  // The viewer quotes the message that asked for each picture.
  if (user?.text) {
    viewerAssets.forEach((asset, position) => {
      viewerAssets[position] = { ...asset, ask: user.text }
    })
  }

  const viewerRef = useRef(viewerAssets)

  viewerRef.current = viewerAssets

  // Stable, so the memoised replies do not re-render their markdown on every turn update.
  const openAsset = useCallback(asset => onOpenAsset(viewerRef.current, asset), [onOpenAsset])
  const playable = Boolean(game && game.webExport && playableSha(game))
  const frame = [...parts.assets].reverse().find(asset => asset.kind === 'Playtest frame') ?? null
  const report = parts.report
  // A finished turn that built the game, or reported what it did, ends in its build card.
  const carded = !live && (build || report)

  let play = null
  let playLabel = null

  if (latestBuild && game) {
    if (chatBusy) {
      play = carded ? null : jsx(PlayCard, { frame, game, onOpenAsset: openAsset, state: 'busy' })
      playLabel = jsx('span', { className: 'cs-faint cs-small', children: `Playable again when ${AGENT} finishes` })
    } else if (!playable) {
      play = carded ? null : jsx(PlayCard, { frame, game, onOpenAsset: openAsset, state: 'unplayable' })
      playLabel = jsx('span', { className: 'cs-faint cs-small', children: 'The playable copy is not ready yet' })
    } else if (playerOpen) {
      play = jsx(InlinePlayer, { build, ctx, game, note: parts.note, onClose: onClosePlayer, report, stored }, `player:${game.id}`)
    } else if (carded) {
      playLabel = jsxs(Button, { onClick: onPlay, size: 'sm', children: [jsx(Codicon, { name: 'play', size: 13 }), 'Play'] })
    } else {
      play = jsx(PlayCard, { frame, game, note: parts.note, onOpenAsset: openAsset, onPlay, state: 'ready' })
    }
  } else if (build?.state === 'built' && !live) {
    playLabel = jsx('span', { className: 'cs-faint cs-small', children: 'Earlier build' })
  }

  const took = startedAt && end?.at ? spanWords(end.at - startedAt) : null
  const card = carded
    ? jsx(BuildCard, {
        at: agentAt,
        build,
        chatBusy,
        isLast,
        onOpenAsset: openAsset,
        onSend,
        parts: { ...parts, startedAt: startedAt ?? null, endedAt: end?.at ?? null },
        play,
        playLabel,
        report,
        root,
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
              jsxs('div', {
                className: 'cs-b-who',
                children: [
                  AGENT,
                  jsx('span', {
                    children: `${live ? 'working now' : timeOfDay(agentAt ?? startedAt)}${
                      user?.model && previousModel && (user.model !== previousModel.model || (user.effort ?? '') !== (previousModel.effort ?? ''))
                        ? ` · ${modelName(user.model).name}${user.effort ? ` · ${effortLabel(user.effort)}` : ''}`
                        : ''
                    }`
                  })
                ]
              }),
              ...parts.intro.map((item, index) => jsx(AgentText, { item, onOpenAsset: openAsset, root }, `i${index}`)),
              showWorked
                ? jsx(Worked, { endedAt: end?.at ?? null, live, onOpenAsset: openAsset, parts, root, startedAt: live ? (turnStartedAt ?? startedAt ?? Date.now()) : startedAt, status: end?.status ?? null }, 'worked')
                : null,
              // With a report the card says it all and the reply is a line after it; without one the reply
              // is the words, and the card (a build) follows them.
              ...(report ? [card, ...outro] : [...outro, card]),
              ...parts.prompts.map(item => jsx(BuildPromptCard, { item, stored }, item.requestId ?? item.id ?? 'prompt')),
              ...parts.errors.map((item, index) =>
                jsxs(
                  'div',
                  {
                    className: 'cs-b-card bad',
                    children: [
                      jsxs('div', { className: 'cs-row', children: [jsx(Codicon, { name: 'error', size: 14 }), jsx('b', { children: 'Something went wrong' })] }),
                      jsx('p', { className: 'cs-small', children: item.text }),
                      isLast && !chatBusy && item.resend
                        ? jsx('div', { className: 'cs-row', children: jsx(Button, { onClick: () => onSend(item.resend.text, item.resend.shown, item.resend.attachments ?? []), size: 'sm', children: 'Try again' }) })
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
                        ? jsx('div', { className: 'cs-row', children: jsx(Button, { onClick: () => onSend('The build failed. Please fix it and build again.'), size: 'sm', children: `Ask ${AGENT} to fix it` }) })
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
